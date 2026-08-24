"""Tell a proven-retired historical secret apart from a live or unknown one.

A secret-class file inside an approved workspace root is normally a hard
blocker: the dedicated principal must be able to write that tree, so nothing in
it can be hidden, and a credential that was ever committed stays readable from
git object storage no matter what the working-tree ACL says.

That rule is right for every case except one that can be *proven* dead. This
module is the narrow, evidence-driven exception, and it is deliberately hostile
to being widened:

* it matches one exact repository-relative path at a time, from a checked-in
  evidence file — there is no pattern, prefix or wildcard form,
* every element of the contract is verified against git metadata or the
  evidence file, so a stale claim cannot pass,
* anything unverifiable is LIVE_OR_UNKNOWN_SECRET_AUTHORITY, never retired.

No file content is ever opened. Sizes come from stat(); the historical blob is
never read, printed or logged.
"""

from __future__ import annotations

import json
import subprocess
from pathlib import Path
from typing import Any, Callable, Iterable, Sequence

EVIDENCE_PATH = Path(__file__).resolve().parent / "principal" / "retired_secret_authority.json"

LIVE_SECRET_PRESENT = "LIVE_SECRET_PRESENT"
LIVE_OR_UNKNOWN = "LIVE_OR_UNKNOWN_SECRET_AUTHORITY"
PROVEN_RETIRED = "PROVEN_RETIRED_SECRET_AUTHORITY"
NO_SECRET_MATERIAL = "NO_SECRET_MATERIAL"

REQUIRED_CHECKS = (
    "EXACT_PATH",
    "CANONICAL_MAIN_UNTRACKED",
    "LIVE_COPY_EMPTY",
    "RETIREMENT_COMMIT_IN_CANONICAL",
    "HUMAN_ATTESTATION",
)

GitRunner = Callable[[Path, Sequence[str]], "subprocess.CompletedProcess[str]"]


def _run_git(repo: Path, args: Sequence[str]) -> "subprocess.CompletedProcess[str]":
    return subprocess.run(
        ["git", "-C", str(repo), *args],
        capture_output=True,
        text=True,
        timeout=60,
        check=False,
    )


def load_evidence(path: Path | None = None) -> dict[str, Any]:
    """Absent or unparsable evidence yields no entries, so nothing can be retired."""
    target = path or EVIDENCE_PATH
    try:
        # utf-8-sig: a BOM must not silently disable the whole contract.
        raw = target.read_text(encoding="utf-8-sig")
    except OSError:
        return {"schema": None, "entries": []}
    try:
        parsed = json.loads(raw)
    except json.JSONDecodeError:
        return {"schema": None, "entries": []}
    if not isinstance(parsed, dict):
        return {"schema": None, "entries": []}
    entries = parsed.get("entries")
    if not isinstance(entries, list):
        parsed["entries"] = []
    return parsed


def _normalise(relative_path: str) -> str:
    return relative_path.replace("\\", "/").strip("/").lower()


def find_entry(evidence: dict[str, Any], repo_root: str, relative_path: str) -> dict[str, Any] | None:
    """Exact path match within the named repository. No prefixes, no globs."""
    wanted_path = _normalise(relative_path)
    wanted_repo = Path(repo_root).name.lower()
    for entry in evidence.get("entries", []):
        if not isinstance(entry, dict):
            continue
        if str(entry.get("repo", "")).lower() != wanted_repo:
            continue
        if _normalise(str(entry.get("relative_path", ""))) != wanted_path:
            continue
        return entry
    return None


def _check_exact_path(entry: dict[str, Any], finding: dict[str, Any]) -> tuple[bool, str]:
    declared = _normalise(str(entry.get("relative_path", "")))
    found = _normalise(str(finding.get("relative_path", "")))
    if not declared:
        return False, "evidence entry declares no relative_path"
    if declared != found:
        return False, f"evidence declares '{declared}', finding is '{found}'"
    return True, f"exact path match on '{found}'"


def _check_canonical_untracked(
    entry: dict[str, Any], finding: dict[str, Any], git: GitRunner
) -> tuple[bool, str]:
    repo = Path(str(finding.get("root", "")))
    ref = str(entry.get("canonical_ref", ""))
    path = str(entry.get("relative_path", ""))
    if not ref:
        return False, "evidence entry declares no canonical_ref"
    listed = git(repo, ["ls-tree", "-r", "--name-only", ref, "--", path])
    if listed.returncode != 0:
        return False, f"cannot read {ref} ({listed.stderr.strip()[:120] or 'git failed'})"
    if listed.stdout.strip():
        return False, f"{ref} still tracks {path}"
    return True, f"{ref} does not track {path}"


def _check_live_copy_empty(finding: dict[str, Any]) -> tuple[bool, str]:
    root = finding.get("root")
    relative = finding.get("relative_path")
    if not root or not relative:
        return False, "finding carries no path"
    target = Path(str(root)) / str(relative)
    if not target.exists():
        return True, "no live working-tree copy"
    try:
        size = target.stat().st_size
    except OSError as exc:
        return False, f"cannot stat live copy ({type(exc).__name__})"
    if size > 0:
        return False, f"live working-tree copy holds {size} bytes"
    return True, "live working-tree copy is empty"


def _check_retirement_commit(
    entry: dict[str, Any], finding: dict[str, Any], git: GitRunner
) -> tuple[bool, str]:
    repo = Path(str(finding.get("root", "")))
    sha = str(entry.get("retirement_commit", ""))
    ref = str(entry.get("canonical_ref", ""))
    path = str(entry.get("relative_path", ""))
    if len(sha) < 40:
        return False, "evidence entry declares no full retirement_commit sha"

    ancestry = git(repo, ["merge-base", "--is-ancestor", sha, ref])
    if ancestry.returncode != 0:
        return False, f"{sha[:9]} is not an ancestor of {ref}"

    # Proving the commit exists is not enough; it must be the commit that
    # removed this exact path.
    changed = git(repo, ["show", "--name-status", "--format=", sha, "--", path])
    if changed.returncode != 0:
        return False, f"cannot inspect {sha[:9]} ({changed.stderr.strip()[:120] or 'git failed'})"
    deleted = any(
        line.split("\t")[0].strip().upper().startswith("D")
        for line in changed.stdout.splitlines()
        if "\t" in line
    )
    if not deleted:
        return False, f"{sha[:9]} does not delete {path}"
    return True, f"{sha[:9]} is in {ref} and deletes {path}"


def _check_attestation(entry: dict[str, Any]) -> tuple[bool, str]:
    attestation = entry.get("human_attestation")
    if not isinstance(attestation, dict):
        return False, "no human_attestation block"
    if attestation.get("service_deleted") is not True:
        return False, "human_attestation.service_deleted is not true"
    for field in ("statement", "attested_by", "attested_utc"):
        if not str(attestation.get(field, "")).strip():
            return False, f"human_attestation.{field} is empty"
    return True, f"attested by {attestation.get('attested_by')} on {attestation.get('attested_utc')}"


def classify(
    finding: dict[str, Any],
    evidence: dict[str, Any] | None = None,
    git: GitRunner | None = None,
) -> dict[str, Any]:
    """Classify one secret-class finding. Fail-closed by construction."""
    evidence = evidence if evidence is not None else load_evidence()
    git = git or _run_git

    result: dict[str, Any] = {
        "root": finding.get("root"),
        "relative_path": finding.get("relative_path"),
        "size": finding.get("size"),
        "git_tracked": bool(finding.get("git_tracked")),
        "in_git_history": bool(finding.get("in_git_history")),
        "checks": [],
        "verdict": LIVE_OR_UNKNOWN,
        "blocking": True,
        "reason": None,
    }

    size = finding.get("size")
    if isinstance(size, (int, float)) and size > 0:
        result["verdict"] = LIVE_SECRET_PRESENT
        result["reason"] = "the working-tree file still holds content"
        return result

    if not result["git_tracked"] and not result["in_git_history"]:
        result["verdict"] = NO_SECRET_MATERIAL
        result["blocking"] = False
        result["reason"] = "empty, untracked and absent from history"
        return result

    entry = find_entry(evidence, str(finding.get("root", "")), str(finding.get("relative_path", "")))
    if entry is None:
        result["reason"] = "no retirement evidence declares this exact path"
        return result

    checks = [
        ("EXACT_PATH", *_check_exact_path(entry, finding)),
        ("CANONICAL_MAIN_UNTRACKED", *_check_canonical_untracked(entry, finding, git)),
        ("LIVE_COPY_EMPTY", *_check_live_copy_empty(finding)),
        ("RETIREMENT_COMMIT_IN_CANONICAL", *_check_retirement_commit(entry, finding, git)),
        ("HUMAN_ATTESTATION", *_check_attestation(entry)),
    ]
    result["checks"] = [
        {"id": check_id, "ok": ok, "detail": detail} for check_id, ok, detail in checks
    ]
    failed = [check_id for check_id, ok, _ in checks if not ok]

    if failed:
        result["reason"] = "retirement contract not satisfied: " + ", ".join(failed)
        return result

    result["verdict"] = PROVEN_RETIRED
    result["blocking"] = False
    result["reason"] = "retirement contract satisfied; historical authority is dead"
    result["authority_target"] = entry.get("authority_target")
    return result


def classify_all(
    findings: Iterable[dict[str, Any]],
    evidence: dict[str, Any] | None = None,
    git: GitRunner | None = None,
) -> dict[str, Any]:
    evidence = evidence if evidence is not None else load_evidence()
    entries = [classify(finding, evidence, git) for finding in findings]

    active = [e for e in entries if e["verdict"] == LIVE_SECRET_PRESENT]
    unresolved = [e for e in entries if e["verdict"] == LIVE_OR_UNKNOWN]
    retired = [e for e in entries if e["verdict"] == PROVEN_RETIRED]

    return {
        "schema": "r5.secret_authority_classification.v1",
        "entries": entries,
        "ACTIVE_WORKSPACE_SECRET_FILES": len(active),
        "UNRESOLVED_GIT_HISTORY_SECRET_AUTHORITY": len(unresolved),
        "HISTORICAL_DEAD_AUTHORITY": len(retired),
        "SECRET_AUTHORITY_BLOCKED": bool(active or unresolved),
    }


def main(argv: Sequence[str] | None = None) -> int:
    import argparse

    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--findings", required=True, help="JSON file holding a list of findings")
    parser.add_argument("--evidence", default=None, help="override the evidence file")
    parser.add_argument("--out", default=None, help="write the classification here")
    args = parser.parse_args(argv)

    payload = json.loads(Path(args.findings).read_text(encoding="utf-8-sig"))
    findings = payload
    if isinstance(payload, dict):
        # A preflight artifact may be passed whole, but an unrecognised object
        # must not silently degrade to "no findings" - that reads as clean.
        if "in_workspace_secret_files" not in payload:
            print("findings payload is an object without 'in_workspace_secret_files'", flush=True)
            return 2
        findings = payload["in_workspace_secret_files"]
    if not isinstance(findings, list):
        print(f"findings payload is {type(findings).__name__}, expected a list", flush=True)
        return 2
    if any(not isinstance(item, dict) for item in findings):
        print("findings payload holds a non-object entry", flush=True)
        return 2

    evidence = load_evidence(Path(args.evidence) if args.evidence else None)
    report = classify_all(findings, evidence)

    payload = json.dumps(report, indent=2)
    if args.out:
        Path(args.out).write_text(payload, encoding="utf-8")
    else:
        print(payload)
    return 1 if report["SECRET_AUTHORITY_BLOCKED"] else 0


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(main())
