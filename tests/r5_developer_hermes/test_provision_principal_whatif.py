"""WhatIf / Windows PowerShell 5.1 contract for provision-principal.ps1."""

from __future__ import annotations

import re
import shutil
import subprocess
from pathlib import Path

import pytest

from r5_developer_hermes.harness import REPO_ROOT

PROVISION = (
    REPO_ROOT
    / "scripts"
    / "r5_developer_hermes"
    / "principal"
    / "provision-principal.ps1"
)
ACCOUNT_NAME = "hermes-dev"
SCOPE_ROOT = Path(r"W:\hermes-dev")
WINDOWS_POWERSHELL = shutil.which("powershell.exe")
# New-LocalUser -Description carries ValidateLength(0, 48) on this host.
WINDOWS_LOCALUSER_DESCRIPTION_LIMIT = 48
DESCRIPTION_LITERAL = re.compile(
    r"New-LocalUser[\s\S]*?-Description\s+'([^']*)'",
    re.MULTILINE,
)

requires_windows_powershell = pytest.mark.skipif(
    not WINDOWS_POWERSHELL,
    reason="Windows PowerShell 5.1 required",
)


def _powershell_code(path: Path) -> str:
    """Strip block and line comments so prohibitions are tested against code."""
    text = re.sub(r"<#.*?#>", "", path.read_text(encoding="utf-8"), flags=re.DOTALL)
    return "\n".join(line.split("#", 1)[0] for line in text.splitlines())


def _extract_function(source: str, name: str) -> str:
    marker = f"function {name}"
    start = source.index(marker)
    rest = source[start:]
    depth = 0
    started = False
    for index, char in enumerate(rest):
        if char == "{":
            depth += 1
            started = True
        elif char == "}":
            depth -= 1
            if started and depth == 0:
                return rest[: index + 1]
    raise AssertionError(f"could not extract {name}")


def _run_windows_powershell(*args: str, timeout: int = 60) -> subprocess.CompletedProcess[str]:
    assert WINDOWS_POWERSHELL
    return subprocess.run(
        [WINDOWS_POWERSHELL, "-NoProfile", "-ExecutionPolicy", "Bypass", *args],
        capture_output=True,
        text=True,
        timeout=timeout,
        check=False,
    )


def _local_user_exists(name: str) -> bool:
    result = _run_windows_powershell(
        "-Command",
        f"if (Get-LocalUser -Name '{name}' -ErrorAction SilentlyContinue) {{ 'YES' }} else {{ 'NO' }}",
    )
    return "YES" in result.stdout


def test_whatif_does_not_create_account_or_mutate_acls() -> None:
    """Mutations stay behind ShouldProcess; the SID-unavailable path grants nothing."""
    raw = PROVISION.read_text(encoding="utf-8")
    code = _powershell_code(PROVISION)
    assert "[CmdletBinding(SupportsShouldProcess = $true" in code

    should_create = code.index("Create standard local account")
    new_local = code.index("New-LocalUser")
    whatif_create = code.index("would create standard local account")
    assert should_create < new_local < whatif_create

    grant_block = raw[raw.index("if ($accountSid)") : raw.index("account SID unavailable")]
    assert "Grant-TraverseOnly" in grant_block
    assert "Grant-InheritedModify" in grant_block

    sid_unavailable = raw[
        raw.index("account SID unavailable") : raw.index("$SID_USERS_GROUP")
    ]
    assert "no ACL changes attempted" in sid_unavailable
    assert "Grant-TraverseOnly" not in sid_unavailable
    assert "Grant-InheritedModify" not in sid_unavailable
    assert "Set-Acl" not in sid_unavailable
    assert "New-LocalUser" not in sid_unavailable

    for fn_name in ("Grant-InheritedModify", "Grant-TraverseOnly"):
        start = code.index(f"function {fn_name}")
        nxt = code.find("\nfunction ", start + 1)
        body = code[start : nxt if nxt != -1 else None]
        assert "ShouldProcess" in body
        assert body.index("ShouldProcess") < body.index("Set-Acl")


def test_account_sid_unavailable_path_is_handled_cleanly() -> None:
    code = _powershell_code(PROVISION)
    assert "account SID unavailable (WhatIf run); no ACL changes attempted" in code
    assert "Add-Action 'acl' '-' 'account SID unavailable" in code


def test_read_execute_inspection_is_powershell_51_compatible() -> None:
    """The 5.1 failure was `(try { ... })` as a pipeline command inside Where-Object."""
    raw = PROVISION.read_text(encoding="utf-8")
    code = _powershell_code(PROVISION)
    assert "(try {" not in code
    assert "function Test-UsersGroupReadExecute" in code
    helper = _extract_function(code, "Test-UsersGroupReadExecute")
    assert "Where-Object" not in helper
    assert "$aceSid = try {" in helper
    assert "foreach ($ace in $Acl.Access)" in helper

    toolchain = raw[
        raw.index("$SID_USERS_GROUP") : raw.index("if ($DenyInWorkspaceSecrets -and $accountSid)")
    ]
    assert "Test-UsersGroupReadExecute" in toolchain
    assert "Where-Object" not in toolchain
    assert "Set-Acl" not in toolchain
    assert "AddAccessRule" not in toolchain


def test_failed_toolchain_verification_remains_fail_closed() -> None:
    raw = PROVISION.read_text(encoding="utf-8")
    code = _powershell_code(PROVISION)
    toolchain = raw[
        raw.index("$SID_USERS_GROUP") : raw.index("if ($DenyInWorkspaceSecrets -and $accountSid)")
    ]
    assert "does not widen toolchain ACLs" in toolchain
    assert "'FAILED'" in toolchain
    assert "toolchain_acls_changed = $false" in code
    helper = _extract_function(code, "Test-UsersGroupReadExecute")
    assert "catch { '' }" in helper
    assert "return $false" in helper


def _account_description() -> str:
    matches = DESCRIPTION_LITERAL.findall(_powershell_code(PROVISION))
    assert len(matches) == 1, "exactly one New-LocalUser Description is required"
    return matches[0]


def test_account_description_fits_windows_localuser_limit() -> None:
    description = _account_description()
    assert len(description) <= WINDOWS_LOCALUSER_DESCRIPTION_LIMIT
    assert description
    assert "\n" not in description


@requires_windows_powershell
def test_account_description_matches_host_new_localuser_contract() -> None:
    """The limit is the cmdlet ValidateLengthAttribute, not a guessed number."""
    result = _run_windows_powershell(
        "-Command",
        "$attr = (Get-Command New-LocalUser).Parameters['Description'].Attributes |"
        " Where-Object { $_ -is [System.Management.Automation.ValidateLengthAttribute] };"
        " if (-not $attr) { Write-Output 'NO_VALIDATE_LENGTH'; exit 1 };"
        " Write-Output ('MAX=' + $attr.MaxLength)",
    )
    assert result.returncode == 0, result.stdout + result.stderr
    assert result.stdout.strip() == f"MAX={WINDOWS_LOCALUSER_DESCRIPTION_LIMIT}"
    assert len(_account_description()) <= WINDOWS_LOCALUSER_DESCRIPTION_LIMIT


def test_existing_provisioning_semantics_remain_unchanged() -> None:
    code = _powershell_code(PROVISION)
    assert "AddAccessRule" in code
    assert "SetAccessRuleProtection" not in code
    assert "RemoveAccessRule" not in code
    assert "PurgeAccessRules" not in code
    assert "host_secret_root_granted = $false" in code
    assert "password_persisted = $false" in code
    assert "host_profile_touched = $false" in code
    assert "credential_stores_copied = $false" in code
    assert "/savecred" not in code.lower()
    assert code.count("New-LocalUser") == 1
    assert "$AccountName    = 'hermes-dev'" in code
    assert "Create standard local account" in code
    assert "is a member of Administrators" in code
    assert "will not silently change administrative group membership" in code
    assert "Add-LocalGroupMember -SID $SID_USERS" in code
    assert "Add-LocalGroupMember -SID $SID_ADMINISTRATORS" not in code
    assert "Read-Host -AsSecureString" in code
    assert "-Password $secret" in code


@requires_windows_powershell
def test_provision_script_parses_under_windows_powershell(tmp_path: Path) -> None:
    parser = tmp_path / "parse.ps1"
    parser.write_text(
        "param([string]$Path)\n"
        "$errors = $null\n"
        "$tokens = $null\n"
        "$null = [System.Management.Automation.Language.Parser]::ParseFile("
        "$Path, [ref]$tokens, [ref]$errors)\n"
        "if ($errors -and $errors.Count) {\n"
        "    $errors | ForEach-Object { $_.ToString() }\n"
        "    exit 1\n"
        "}\n"
        "Write-Output 'PARSE_OK'\n",
        encoding="ascii",
    )
    result = _run_windows_powershell("-File", str(parser), "-Path", str(PROVISION))
    assert result.returncode == 0, result.stdout + result.stderr
    assert "PARSE_OK" in result.stdout


@requires_windows_powershell
def test_acl_inspection_executes_on_windows_powershell_51(tmp_path: Path) -> None:
    helper = _extract_function(PROVISION.read_text(encoding="utf-8"), "Test-UsersGroupReadExecute")
    harness = tmp_path / "inspect.ps1"
    harness.write_text(
        "$ErrorActionPreference = 'Stop'\n"
        f"{helper}\n"
        "$SID = 'S-1-5-32-545'\n"
        "$empty = [pscustomobject]@{ Access = @() }\n"
        "if (Test-UsersGroupReadExecute -Acl $empty -Sid $SID) {\n"
        "    Write-Error 'empty ACL must be fail-closed'\n"
        "    exit 1\n"
        "}\n"
        "$badIdentity = New-Object psobject\n"
        "$badIdentity | Add-Member ScriptMethod Translate { param($t) throw 'unresolvable' }\n"
        "$badAce = [pscustomobject]@{\n"
        "    AccessControlType = 'Allow'\n"
        "    IdentityReference = $badIdentity\n"
        "    FileSystemRights = [System.Security.AccessControl.FileSystemRights]::ReadAndExecute\n"
        "}\n"
        "$badAcl = [pscustomobject]@{ Access = @($badAce) }\n"
        "if (Test-UsersGroupReadExecute -Acl $badAcl -Sid $SID) {\n"
        "    Write-Error 'unresolvable identity must not fail-open'\n"
        "    exit 1\n"
        "}\n"
        "$deny = New-Object System.Security.AccessControl.FileSystemAccessRule(\n"
        "    (New-Object System.Security.Principal.SecurityIdentifier($SID)),\n"
        "    [System.Security.AccessControl.FileSystemRights]::FullControl,\n"
        "    [System.Security.AccessControl.AccessControlType]::Deny)\n"
        "$denyAcl = [pscustomobject]@{ Access = @($deny) }\n"
        "if (Test-UsersGroupReadExecute -Acl $denyAcl -Sid $SID) {\n"
        "    Write-Error 'Deny ACE must not count as read/execute'\n"
        "    exit 1\n"
        "}\n"
        "$allow = New-Object System.Security.AccessControl.FileSystemAccessRule(\n"
        "    (New-Object System.Security.Principal.SecurityIdentifier($SID)),\n"
        "    [System.Security.AccessControl.FileSystemRights]::ReadAndExecute,\n"
        "    [System.Security.AccessControl.AccessControlType]::Allow)\n"
        "$allowAcl = [pscustomobject]@{ Access = @($allow) }\n"
        "if (-not (Test-UsersGroupReadExecute -Acl $allowAcl -Sid $SID)) {\n"
        "    Write-Error 'matching Users ReadAndExecute must be true'\n"
        "    exit 1\n"
        "}\n"
        "$real = Get-Acl -LiteralPath $env:SystemRoot\n"
        "$null = Test-UsersGroupReadExecute -Acl $real -Sid $SID\n"
        "Write-Output 'INSPECT_OK'\n",
        encoding="ascii",
    )
    result = _run_windows_powershell("-File", str(harness))
    combined = result.stdout + result.stderr
    assert "try" not in combined.lower() or "not recognized" not in combined.lower()
    assert "CommandNotFoundException" not in combined
    assert result.returncode == 0, combined
    assert "INSPECT_OK" in result.stdout


@requires_windows_powershell
def test_whatif_invocation_does_not_create_hermes_dev_or_fail_on_try(
    tmp_path: Path,
) -> None:
    """Never run without -WhatIf. Elevation may abort first; that is still mutation-free."""
    assert not _local_user_exists(ACCOUNT_NAME)
    assert not SCOPE_ROOT.exists()

    result = _run_windows_powershell(
        "-File",
        str(PROVISION),
        "-WhatIf",
        "-ArtifactPath",
        str(tmp_path / "principal_provision.json"),
    )
    combined = result.stdout + result.stderr
    lowered = combined.lower()
    assert "commandnotfoundexception" not in lowered
    assert "try' was not recognized" not in lowered
    assert 'try" was not recognized' not in lowered
    assert 'benennung "try"' not in lowered

    assert not _local_user_exists(ACCOUNT_NAME)
    assert not SCOPE_ROOT.exists()

    if re.search(r"must run\s+ELEVATED", combined) or (
        "WriteErrorException,provision-principal.ps1" in combined
        and result.returncode != 0
    ):
        assert result.returncode != 0
        return

    assert "would create standard local account" in combined
    assert "account SID unavailable" in combined
    assert "no ACL changes attempted" in combined
    assert not _local_user_exists(ACCOUNT_NAME)
    assert not SCOPE_ROOT.exists()
