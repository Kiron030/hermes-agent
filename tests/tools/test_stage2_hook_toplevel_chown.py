"""Contract test: the s6-overlay stage2 hook reconciles ownership of every
top-level entry under $HERMES_HOME on every boot, using a DENYLIST rather
than an allowlist.

History:

- #19788 / PR #19795: a blanket `chown -R $HERMES_HOME` was replaced with a
  hand-maintained ALLOWLIST of "known hermes subdirs" (cron/, sessions/,
  logs/, ...), to avoid clobbering host-owned files in a bind-mounted
  $HERMES_HOME.
- #35098: the subdir allowlist missed top-level *files* (gateway.lock,
  state.db, auth.json, ...) living directly under $HERMES_HOME, so a second,
  separate allowlist was added for those.
- 2026-07-02 Railway incident, part 3 (see
  docs/powerunits_railway_bootstrap_v1.md): BOTH allowlists chronically
  drifted behind the dozens of `get_hermes_home() / "..."` call sites across
  the Python codebase (sessions/, pairing/, cache/, plugins/, checkpoints/,
  whatsapp/, dynamically-named per-provider/per-platform paths, ...), and the
  whole repair was additionally gated behind whether the TOP-LEVEL directory
  itself had the wrong owner — once fixed once, anything created afterwards
  with a stale owner (a file left over from a pre-migration volume, or a
  `docker exec <container> hermes ...` write as root) was never revisited on
  any later boot. Production symptom: `PermissionError` on
  `sessions/sessions.json` and `pairing/telegram-approved.json`, neither of
  which was in either allowlist and both created after the top-level
  directory had already been "fixed" once.

Both allowlists were replaced by a single unconditional, denylist-based
reconciliation loop that walks every top-level entry under $HERMES_HOME
(files and directories, including dotfiles) on every boot and chowns
whatever isn't already hermes-owned. The denylist
(`HERMES_DATA_DIR_CHOWN_EXCLUDE`) preserves the original #19788 intent for
the one legitimate remaining case: an operator who bind-mounts a host
directory that ALSO holds unrelated, non-hermes files at its top level.
"""
from __future__ import annotations

import re
import shutil
import subprocess
import tempfile
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[2]
STAGE2_HOOK = REPO_ROOT / "docker" / "stage2-hook.sh"


@pytest.fixture(scope="module")
def stage2_text() -> str:
    if not STAGE2_HOOK.exists():
        pytest.skip("docker/stage2-hook.sh not present in this checkout")
    return STAGE2_HOOK.read_text()


def _reconciliation_block(text: str) -> str:
    """Extract the unconditional top-level ownership-reconciliation block,
    from the helper functions through the closing `done` of the
    `for entry in ...` loop."""
    m = re.search(
        r"actual_hermes_uid=\$\(id -u hermes\)\n(?:.*\n)*?"
        r'^for entry in "\$HERMES_HOME"/\* "\$HERMES_HOME"/\.\[!\.\]\*; do\n'
        r"(?:.*\n)*?^done\n",
        text,
        re.MULTILINE,
    )
    assert m, "stage2-hook.sh must contain the ownership-reconciliation block"
    block = m.group(0)
    assert "for entry in" in block
    assert 'chown_hermes_tree "$entry"' in block
    assert "path_has_symlink_component" in block
    return block


def test_reconciliation_is_not_gated_by_toplevel_ownership(stage2_text: str) -> None:
    """The old `needs_chown` gate (checking only the top-level directory's
    owner) allowed subdirectories/files created after that top-level check
    already passed to stay permanently unrepaired. The new reconciliation
    must run unconditionally on every boot — i.e. the `needs_chown`
    variable itself (assignment or use) must be gone, not merely renamed."""
    assert not re.search(r"\bneeds_chown\s*=", stage2_text), (
        "the top-level-ownership gate variable must be gone — the "
        "reconciliation loop runs unconditionally on every boot "
        "(2026-07-02 incident part 3)"
    )
    assert "$needs_chown" not in stage2_text


def test_reconciliation_supports_operator_denylist(stage2_text: str) -> None:
    block = _reconciliation_block(stage2_text)
    assert "HERMES_DATA_DIR_CHOWN_EXCLUDE" in block, (
        "the reconciliation loop must support an opt-out denylist for the "
        "rare case of unrelated host files at the top level of a "
        "bind-mounted $HERMES_HOME (#19788)"
    )


def test_no_blanket_find_user_root_sweep(stage2_text: str) -> None:
    """Must not reintroduce a `find ... -user root` sweep — that was
    rejected in favor of stat-based per-entry comparison, which is
    tolerant of rootless/Podman UID mapping quirks that can make `-user
    root` matches unreliable."""
    assert not re.search(r"find\s+\"?\$\{?HERMES_HOME\}?\"?[^\n]*-user\s+root", stage2_text)


def _run_reconciliation(
    stage2_text: str,
    present: list[str],
    exclude: str = "",
) -> list[str]:
    """Run the extracted reconciliation block in a sandbox $HERMES_HOME, with
    `chown`/`id` stubbed so we can observe which top-level entries it
    selects without needing real root privileges or an actual `hermes`
    system user. Returns the basenames it attempted to chown."""
    bash = shutil.which("bash")
    if bash is None:
        pytest.skip("bash not available")
    block = _reconciliation_block(stage2_text)

    with tempfile.TemporaryDirectory() as d:
        dpath = Path(d)
        home = dpath / "home"
        home.mkdir()
        for rel in present:
            target = home / rel
            if rel.endswith("/"):
                target.mkdir(parents=True, exist_ok=True)
            else:
                target.parent.mkdir(parents=True, exist_ok=True)
                target.touch()

        # as_posix(): the harness script is interpreted by bash, which
        # expects forward slashes regardless of host OS (Windows dev
        # checkouts included).
        home_posix = home.as_posix()
        log_posix = (dpath / "chown.log").as_posix()

        # Stub `id -u hermes` (no real hermes system user in the test
        # sandbox) and `chown` (no real root privileges). Every real call in
        # the block is `chown [-R] hermes:hermes "$path"`, so the last
        # positional arg (basename-stripped) is always the top-level entry
        # name — same technique as the pre-existing chown-loop harness.
        script = (
            "set -e\n"
            f'HERMES_HOME="{home_posix}"\n'
            f'HERMES_DATA_DIR_CHOWN_EXCLUDE="{exclude}"\n'
            'id() { echo 10000; }\n'
            f'chown() {{ for a in "$@"; do :; done; echo "${{a##*/}}" >> "{log_posix}"; }}\n'
            + block
        )
        script_path = dpath / "harness.sh"
        script_path.write_text(script)

        proc = subprocess.run([bash, str(script_path)], capture_output=True, text=True)
        assert proc.returncode == 0, proc.stderr

        log = dpath / "chown.log"
        if not log.exists():
            return []
        touched = [ln for ln in log.read_text().splitlines() if ln]
        # Drop the entry for $HERMES_HOME itself (the unconditional
        # top-level chown that always fires first).
        home_name = home.name
        return [t for t in touched if t != home_name]


def test_reconciles_arbitrary_new_toplevel_dirs_without_an_allowlist(
    stage2_text: str,
) -> None:
    """The whole point of the fix: directories/files that were never on any
    hand-maintained list (a brand new feature's state dir, or the two paths
    that actually broke production — sessions/sessions.json and
    pairing/telegram-approved.json) must be reconciled by default."""
    touched = _run_reconciliation(
        stage2_text,
        present=[
            "sessions/sessions.json",
            "pairing/telegram-approved.json",
            "some_brand_new_feature_nobody_has_added_to_any_list/state.json",
            "cache/model_catalog.json",
            "config.yaml",
            ".env",
        ],
    )
    assert "sessions" in touched
    assert "pairing" in touched
    assert "some_brand_new_feature_nobody_has_added_to_any_list" in touched
    assert "cache" in touched
    assert "config.yaml" in touched
    assert ".env" in touched


def test_reconciliation_respects_operator_denylist(stage2_text: str) -> None:
    touched = _run_reconciliation(
        stage2_text,
        present=["sessions/sessions.json", "my-host-notes/todo.txt"],
        exclude="my-host-notes",
    )
    assert "sessions" in touched
    assert "my-host-notes" not in touched, (
        "an operator-denylisted top-level entry must never be chowned (#19788)"
    )


def test_reconciliation_does_not_choke_on_dotfiles_or_empty_dir(stage2_text: str) -> None:
    # An empty $HERMES_HOME (fresh volume, nothing seeded yet) and a
    # dotfile-only tree must not error out (unmatched glob patterns are a
    # classic POSIX sh footgun this must guard against).
    touched = _run_reconciliation(stage2_text, present=[])
    assert touched == []

    touched = _run_reconciliation(stage2_text, present=[".env"])
    assert ".env" in touched
