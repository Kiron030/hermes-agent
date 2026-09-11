"""Fork-local regressions for the MUSTPORT-5B lifecycle_guard port (v2026.9.7).

* AUTHORITY-NOT-WIDENED: every gateway-lifecycle command the pre-port guard blocked is still
  blocked by every entry point (pure scan and its hermes_cli.cron re-export, referenced-script
  walk, cron check for prompt / shell script / .py script, and terminal_tool inside the gateway).
  The table includes the shapes upstream v2026.9.7 would ALLOW but the fork keeps blocking
  because they are not provably inert (heredoc bodies, path-invoked CLI, ``skill``/``fkill``,
  data-sink arguments).
* Hardening that must hold (each case fails against the pre-port guard).
* Explicit per-category cases: NUL padding, argv-list / execute_code, quote-aware segmentation,
  heredoc (kept blocking), privilege prefixes, self-restart.
* The only allow-less shapes, pinned so a reviewer sees the exact surface.

Paths are passed as POSIX strings: backslash is a shell escape to the tokenizer.
"""

import json
import re
import string

import pytest

import cron.lifecycle_guard as lifecycle_guard
from cron.lifecycle_guard import (
    GatewayLifecycleBlocked,
    check_gateway_lifecycle,
    contains_gateway_lifecycle_command,
    contains_gateway_lifecycle_command_or_referenced_script,
)
from hermes_cli.cron import _contains_gateway_lifecycle_command


@pytest.fixture(autouse=True)
def _pin_profile_identity(monkeypatch):
    monkeypatch.setenv("HERMES_PROFILE", "zeus")
    monkeypatch.delenv("HERMES_PROFILE_NAME", raising=False)


# Commands the pre-port guard (blob 6c70c1af) blocked. Derived from the pre-port tests and its
# four regex branches; the second half lists the shapes v2026.9.7 would let through.
PRE_PORT_BLOCKED = [
    # Branch A
    "hermes gateway restart",
    "hermes gateway stop",
    "hermes  gateway  restart",
    "HERMES GATEWAY RESTART",
    "please run hermes gateway restart",
    "Upgrade hermes then run hermes gateway restart",
    "true && hermes gateway restart",
    "echo $(hermes gateway restart)",
    "sh -c 'hermes gateway restart'",
    # Branch A behind privilege prefixes / wrappers
    "sudo hermes gateway restart",
    "sudo -u hermes hermes gateway stop",
    "doas hermes gateway restart",
    "nohup hermes gateway restart &",
    "env HERMES_HOME=/srv/h hermes gateway restart",
    "timeout 60 hermes gateway stop",
    # Branch B (pre-port verbs)
    "launchctl kickstart gui/501/ai.hermes.gateway",
    "launchctl kickstart -k gui/501/ai.hermes.gateway",
    "Run launchctl kickstart -k gui/501/ai.hermes.gateway",
    "launchctl unload ~/Library/LaunchAgents/ai.hermes.gateway.plist",
    "launchctl load ~/Library/LaunchAgents/ai.hermes.gateway.plist",
    "launchctl stop ai.hermes.gateway",
    "launchctl restart hermes-gateway",
    "sudo launchctl kickstart -k system/ai.hermes.gateway",
    # Branch C
    "systemctl restart hermes-gateway",
    "systemctl --user restart hermes-gateway",
    "systemctl stop hermes-gateway.service",
    "systemctl start hermes-gateway",
    "sudo systemctl stop hermes-gateway",
    "sudo -u deploy systemctl --user restart hermes.gateway",
    # Branch D
    "kill hermes gateway process",
    "pkill -f hermes.*gateway",
    "pkill -f gateway.*hermes",
    "sudo pkill -f 'hermes gateway'",
    # --- upstream v2026.9.7 allows these; the fork keeps blocking ---------------------------
    # Path-invoked CLI (upstream Branch A lookbehind excludes a preceding `/`).
    "/usr/local/bin/hermes gateway restart",
    "./venv/bin/hermes gateway stop",
    "~/.local/bin/hermes gateway restart",
    "sudo /opt/hermes/.venv/bin/hermes gateway restart",
    "cat '/docs/hermes gateway restart-notes.md'",
    # Process killers ending in "kill" (upstream Branch D leading \b).
    "skill -KILL hermes gateway",
    "fkill hermes gateway",
    "hermes skill view gateway-notes && echo hermes gateway docs",
    # Heredoc bodies (upstream masks quoted-delimiter bodies fed to python/osascript/cat).
    "cat > /tmp/runbook.md <<'EOF'\nIf wedged, a human can run: hermes gateway restart\nEOF",
    "python3 <<'EOF'\nimport os\nos.system(\"hermes gateway restart\")\nEOF",
    "osascript <<'EOF'\ndo shell script \"hermes gateway restart\"\nEOF",
    "cat > /tmp/r.sh <<'EOF'\nhermes gateway restart\nEOF\nbash /tmp/r.sh",
    "/tmp/cat <<'EOF'\nsystemctl restart hermes-gateway\nEOF",
    # Data-sink arguments (upstream masks grep/rg/ag/ack/journalctl/sqlite3/psql arguments).
    "grep -o 'hermes gateway restart' notes.txt",
    "$(grep -o 'hermes gateway restart' notes.txt)",
    "rg 'hermes gateway restart' ./logs",
    "psql -c '\\o |hermes gateway restart' -c 'select 1'",
    "ag --pager 'hermes gateway restart' needle .",
    "sqlite3 db \"select edit('', 'hermes gateway restart;')\"",
    "journalctl -u hermes-gateway --grep 'systemctl restart hermes-gateway'",
    # --- positional-parameter bypass (MUSTPORT-5B r1, F1) -----------------------------------
    # The port added Branch A's `(?<![\w.\-])` lookbehind, which treats the word char a bash
    # expansion leaves before `hermes` as an inert word tail. `$1`..`$9` expand to nothing under
    # `bash -c`/cron, so `$1hermes gateway restart` runs the CLI. The pre-port guard (no lookbehind)
    # blocked these as substrings; the fork must keep blocking them.
    "$1hermes gateway restart",
    "true;$9hermes gateway stop",
    "env -u _HERMES_GATEWAY $1hermes gateway restart",
    "sh -c '$1hermes gateway restart'",
]


class TestAuthorityNotWidened:
    @pytest.mark.parametrize("command", PRE_PORT_BLOCKED)
    def test_pure_scan_and_reexport_still_block(self, command):
        assert contains_gateway_lifecycle_command(command) is True
        assert _contains_gateway_lifecycle_command(command) is True

    @pytest.mark.parametrize("command", PRE_PORT_BLOCKED)
    def test_referenced_script_walk_still_blocks(self, command, tmp_path):
        assert contains_gateway_lifecycle_command_or_referenced_script(
            command, cwd=tmp_path.as_posix()
        ) is True

    @pytest.mark.parametrize("command", PRE_PORT_BLOCKED)
    def test_cron_prompt_still_blocks(self, command):
        with pytest.raises(GatewayLifecycleBlocked):
            check_gateway_lifecycle(command, None)

    @pytest.mark.parametrize("command", PRE_PORT_BLOCKED)
    def test_cron_shell_script_still_blocks(self, command, tmp_path):
        script = tmp_path / "job.sh"
        script.write_text(f"#!/bin/bash\n{command}\n", encoding="utf-8")
        with pytest.raises(GatewayLifecycleBlocked):
            check_gateway_lifecycle("nightly job", script.as_posix())

    @pytest.mark.parametrize("command", PRE_PORT_BLOCKED)
    def test_cron_prompt_with_python_script_still_blocks(self, command, tmp_path):
        script = tmp_path / "report.py"
        script.write_text("print('nightly report')\n", encoding="utf-8")
        with pytest.raises(GatewayLifecycleBlocked):
            check_gateway_lifecycle(command, script.as_posix())

    @pytest.mark.parametrize("name,payload", [
        # The scheduler runs .sh through bash and anything else through python: bash executes
        # text behind a magic prefix, python runs a zipapp. The pre-port guard scanned these.
        ("restart.sh", b"MZ\nhermes gateway restart\n"),
        ("restart.sh", b"\x7fELF\nsystemctl restart hermes-gateway\n"),
        ("blob.sh", b"\x1f\x8b\nhermes gateway stop\n"),
        ("job.pyz", b"PK\x03\x04" + bytes(26) + b'import os; os.system("hermes gateway restart")\n'),
    ])
    def test_binary_magic_cron_script_still_scanned(self, tmp_path, name, payload):
        script = tmp_path / name
        script.write_bytes(payload)
        with pytest.raises(GatewayLifecycleBlocked):
            check_gateway_lifecycle("", script.as_posix())

    def test_non_utf8_cron_script_still_blocks(self, tmp_path):
        script = tmp_path / "weird.bin"
        script.write_bytes(b"\xfehermes gateway restart\xff")
        with pytest.raises(GatewayLifecycleBlocked):
            check_gateway_lifecycle("", script.as_posix())

    def test_positional_param_python_script_content_blocks(self, tmp_path):
        # F1: the lifecycle command lives in a .py cron script's body, using a positional
        # parameter that expands to nothing (`$1hermes gateway stop` == `hermes gateway stop`).
        # The .py branch scans the full text with the direct regex, which must block it.
        script = tmp_path / "job.py"
        script.write_text("import os\nos.system('$1hermes gateway stop')\n", encoding="utf-8")
        with pytest.raises(GatewayLifecycleBlocked):
            check_gateway_lifecycle("", script.as_posix())


class TestTerminalToolAuthorityNotWidened:
    """The in-gateway terminal hard block (`_HERMES_GATEWAY=1`, force-proof) covers the table."""

    def _patch_env(self, monkeypatch, fake_env, *, inside_gateway: bool):
        import tools.terminal_tool as tt
        eid = "default"
        monkeypatch.setattr(tt, "_active_environments", {eid: fake_env})
        monkeypatch.setattr(tt, "_last_activity", {eid: 0.0})
        monkeypatch.setattr(tt, "_task_env_overrides", {})
        monkeypatch.setattr(
            tt, "_get_env_config",
            lambda: {"env_type": "local", "cwd": "/tmp", "timeout": 60, "lifetime_seconds": 3600},
        )
        if inside_gateway:
            monkeypatch.setenv("_HERMES_GATEWAY", "1")
        else:
            monkeypatch.delenv("_HERMES_GATEWAY", raising=False)

    def _unreachable_env(self):
        class _FakeEnv:
            env = {}
            def execute(self, command, **kwargs):  # pragma: no cover
                raise AssertionError("execute must not be reached")
        return _FakeEnv()

    @pytest.mark.parametrize("command", PRE_PORT_BLOCKED)
    def test_terminal_blocks_inside_gateway_even_with_force(self, monkeypatch, command):
        import tools.terminal_tool as tt
        from tools.process_registry import process_registry

        def _never_spawn(*_args, **_kwargs):  # pragma: no cover
            raise AssertionError("background spawn must not be reached")

        # background=True skips the foreground nohup/`&` guidance, so the lifecycle guard is the
        # only gate exercised; the spawn is stubbed so a regression can never run the command.
        monkeypatch.setattr(process_registry, "spawn_local", _never_spawn)
        self._patch_env(monkeypatch, self._unreachable_env(), inside_gateway=True)

        result = json.loads(tt.terminal_tool(command=command, force=True, background=True))

        assert result["exit_code"] == 1
        assert "Blocked" in result["error"]

    def test_wrapped_referenced_script_blocked_in_terminal(self, monkeypatch, tmp_path):
        import tools.terminal_tool as tt
        helper = tmp_path / "helper.sh"
        helper.write_text("#!/bin/sh\nhermes gateway restart\n", encoding="utf-8")
        self._patch_env(monkeypatch, self._unreachable_env(), inside_gateway=True)

        result = json.loads(tt.terminal_tool(command=f"sudo bash {helper.as_posix()}"))

        assert result["exit_code"] == 1
        assert "referenced script" in result["error"]

    def test_relative_script_resolves_against_workdir(self, monkeypatch, tmp_path):
        import tools.terminal_tool as tt
        (tmp_path / "relative.sh").write_text("#!/bin/bash\nhermes gateway stop\n", encoding="utf-8")
        self._patch_env(monkeypatch, self._unreachable_env(), inside_gateway=True)

        result = json.loads(tt.terminal_tool(
            command="env FOO=1 bash relative.sh", workdir=tmp_path.as_posix()
        ))

        assert result["exit_code"] == 1

    def test_neutral_label_submit_blocked_in_terminal(self, monkeypatch):
        import tools.terminal_tool as tt
        self._patch_env(monkeypatch, self._unreachable_env(), inside_gateway=True)

        result = json.loads(tt.terminal_tool(
            command="sudo launchctl submit -l com.example.neutral -- /usr/bin/true"
        ))

        assert result["exit_code"] == 1
        assert "KeepAlive" in result["error"]

    def test_benign_referenced_script_still_runs(self, monkeypatch, tmp_path):
        import tools.terminal_tool as tt
        calls = []
        script = tmp_path / "health.sh"
        script.write_text("#!/bin/bash\nprintf 'healthy\\n'\n", encoding="utf-8")

        class _FakeEnv:
            env = {}
            def execute(self, command, **kwargs):
                calls.append(command)
                return {"output": "healthy", "returncode": 0}

        self._patch_env(monkeypatch, _FakeEnv(), inside_gateway=True)
        monkeypatch.setattr(tt, "_check_all_guards", lambda cmd, env, **kwargs: {"approved": True})
        command = f"bash {script.as_posix()}"

        result = json.loads(tt.terminal_tool(command=command))

        assert result["exit_code"] == 0
        assert calls == [command]


# Each case is NOT blocked by the pre-port guard and must be blocked now.
HARDENING_BLOCKED = [
    # SELF_RESTART
    "hermes gateway uninstall",                                          # 1c791cbfe6
    "launchctl bootout gui/501/ai.hermes.gateway",                       # 320d884d88
    "launchctl remove ai.hermes.gateway",                                # 320d884d88
    "launchctl disable gui/501/ai.hermes.gateway",                       # 320d884d88
    "launchctl submit -l ai.hermes.gateway-once -- /bin/sh helper.sh",   # 56cf87432b
    "launchctl bootstrap gui/501 ~/Library/LaunchAgents/ai.hermes.gateway.plist",  # 56cf87432b
    "label=ai.hermes.gateway; launchctl stop \"$label\"",                # 679e07a074
    "launchctl kickstart \\\n  -k gui/501/ai.hermes.gateway",            # #62891 continuation
    "hermes -p zeus gateway restart",                                    # c595d3564a
    "hermes --profile=zeus gateway stop",                                # c595d3564a
    "hermes -v --profile 'zeus' gateway restart",                        # c595d3564a
    # QUOTE_SEGMENTATION
    "launchctl kick\"start\" -k gui/501/ai.hermes.gateway",              # 6d501c2958
    "launchctl kick\\start -k gui/501/ai.hermes.gateway",                # 6d501c2958
    "systemctl re\"start\" hermes-gateway",                              # 6d501c2958
    "hermes gateway re\"start\"",                                        # 6d501c2958
    "hermes gateway re'st'art",                                          # a74eb2dd41
    # ARGV_EXECUTE_CODE
    'subprocess.run(["hermes", "gateway", "restart"])',                  # b34edd6b01
    'subprocess.run(["launchctl", "bootout", "gui/501/ai.hermes.gateway"])',  # b34edd6b01
    'subprocess.call(["systemctl", "restart", "hermes-gateway"])',       # b34edd6b01
]

# Label-independent and referenced-script shapes: only the walk / cron check / terminal see these.
HARDENING_BLOCKED_WALK_ONLY = [
    "launchctl submit -l com.example.neutral -- /usr/bin/true",          # 56cf87432b
    "launchctl bootstrap gui/501 /tmp/com.example.plist",                # 56cf87432b
    "sudo launchctl submit -l com.example.neutral -- /usr/bin/true",     # 5921ba8c06
    "env FOO=1 nohup launchctl bootstrap gui/501 /tmp/x.plist",          # 5921ba8c06
]


class TestHardeningHolds:
    @pytest.mark.parametrize("command", HARDENING_BLOCKED)
    def test_pure_scan_blocks(self, command):
        assert contains_gateway_lifecycle_command(command) is True

    @pytest.mark.parametrize("command", HARDENING_BLOCKED + HARDENING_BLOCKED_WALK_ONLY)
    def test_walk_and_cron_block(self, command):
        assert contains_gateway_lifecycle_command_or_referenced_script(command) is True
        with pytest.raises(GatewayLifecycleBlocked):
            check_gateway_lifecycle(command, None)

    def test_sibling_profile_restart_stays_allowed(self):
        # Not blocked before the port either: only the self-targeting profile form is new.
        assert contains_gateway_lifecycle_command("hermes -p venus gateway restart") is False


class TestNulPadding:
    """92edb861be / 037825c1f2 / a9e46229b2."""

    def test_nul_inside_verb_in_cron_script_is_stripped_and_blocked(self, tmp_path):
        script = tmp_path / "padded.sh"
        script.write_bytes(b"#!/bin/bash\n# pad\x00\nhermes gateway re\x00start\n")
        with pytest.raises(GatewayLifecycleBlocked):
            check_gateway_lifecycle("nightly", script.as_posix())

    def test_nul_padded_referenced_script_is_scanned(self, tmp_path):
        script = tmp_path / "padded.sh"
        script.write_bytes(b"# ok\n# pad\x00\nsystemctl re\x00start hermes-gateway\n")
        assert contains_gateway_lifecycle_command_or_referenced_script(
            f"bash {script.as_posix()}"
        ) is True

    def test_oversized_nul_bearing_script_fails_closed(self, tmp_path):
        script = tmp_path / "huge.sh"
        script.write_bytes(b"#!/bin/bash\n\x00" * 8 + b"x" * (1024 * 1024) + b"\n")
        assert contains_gateway_lifecycle_command_or_referenced_script(
            f"bash {script.as_posix()}"
        ) is True
        with pytest.raises(GatewayLifecycleBlocked):
            check_gateway_lifecycle("", script.as_posix())


class TestExecuteCodeLifecycleGuard:
    """b34edd6b01: execute_code no longer bypasses the in-gateway hard block."""

    class _Reached(Exception):
        pass

    def _run(self, monkeypatch, code, *, inside_gateway=True):
        import tools.code_execution_tool as cet
        import tools.terminal_tool as tt

        monkeypatch.setattr(cet, "SANDBOX_AVAILABLE", True)
        if inside_gateway:
            monkeypatch.setenv("_HERMES_GATEWAY", "1")
        else:
            monkeypatch.delenv("_HERMES_GATEWAY", raising=False)

        def _dispatch_reached(*_args, **_kwargs):
            raise self._Reached()

        # First call after the guard: reaching it means the guard let the code through.
        monkeypatch.setattr(tt, "_get_env_config", _dispatch_reached)
        try:
            return json.loads(cet.execute_code(code=code, task_id="lifecycle-test"))
        except self._Reached:
            return None

    @pytest.mark.parametrize("code", [
        'import os\nos.system("hermes gateway restart")\n',
        'import subprocess\nsubprocess.run(["launchctl", "bootout", "gui/501/ai.hermes.gateway"])\n',
        'import subprocess\nsubprocess.run(["systemctl", "--user", "stop", "hermes-gateway"])\n',
        'import os\nos.system("/usr/local/bin/hermes gateway stop")\n',
        # F1: positional parameter unsets the gateway marker word char at runtime.
        'import subprocess\n'
        'subprocess.run("env -u _HERMES_GATEWAY $1hermes gateway restart", shell=True)\n',
    ])
    def test_lifecycle_code_blocked_inside_gateway(self, monkeypatch, code):
        result = self._run(monkeypatch, code)
        assert result is not None
        assert "Blocked" in result["error"]

    def test_benign_code_reaches_dispatch(self, monkeypatch):
        assert self._run(monkeypatch, "print('gateway restart docs')\n") is None

    def test_guard_inactive_outside_gateway(self, monkeypatch):
        assert self._run(
            monkeypatch, 'import os\nos.system("hermes gateway restart")\n', inside_gateway=False
        ) is None

    def test_oversized_code_refused_before_tokenizing(self, monkeypatch):
        monkeypatch.setattr(lifecycle_guard, "_MAX_LIFECYCLE_SCAN_LINE_BYTES", 8)

        def _explode(*_args, **_kwargs):
            raise AssertionError("over-budget code reached shlex")

        monkeypatch.setattr(lifecycle_guard.shlex, "shlex", _explode)
        result = self._run(monkeypatch, "print(123456789)\n")
        assert result is not None
        assert "Blocked" in result["error"]


class TestHeredocKeptBlocking:
    """9aa0721b23 (#88336) NOT ported: heredoc bodies are scanned like any other text."""

    @pytest.mark.parametrize("command", [
        "cat > /tmp/runbook.md <<'EOF'\nhermes gateway restart\nEOF",
        "cat <<'EOF'\nlaunchctl bootout gui/501/ai.hermes.gateway\nEOF",
        "python3 <<'EOF'\nimport subprocess\nsubprocess.run(['hermes', 'gateway', 'stop'])\nEOF",
        "env python <<\"EOF\"\nimport os; os.system('systemctl restart hermes-gateway')\nEOF",
    ])
    def test_quoted_delimiter_heredoc_bodies_still_block(self, command):
        assert contains_gateway_lifecycle_command(command) is True
        assert contains_gateway_lifecycle_command_or_referenced_script(command) is True


class TestPrivilegePrefixTraversal:
    """6b3a7af73d / 5921ba8c06 through the cron entry point."""

    @pytest.mark.parametrize("prefix", [
        "sudo", "sudo -u root --", "doas", "pkexec --user root", "runuser -u root --",
        "setpriv --reuid=0 --", "systemd-run --scope", "nsenter -t 1 -m", "unshare -r",
        "env FOO=1", "nohup", "timeout -k 5 60", "nice -n 5", "stdbuf -o0",
    ])
    def test_wrapped_script_in_cron_script_is_scanned(self, tmp_path, prefix):
        (tmp_path / "inner.sh").write_text("#!/bin/sh\nhermes gateway restart\n", encoding="utf-8")
        outer = tmp_path / "outer.sh"
        outer.write_text(f"#!/bin/sh\n{prefix} bash inner.sh\n", encoding="utf-8")
        with pytest.raises(GatewayLifecycleBlocked):
            check_gateway_lifecycle("nightly", outer.as_posix())

    @pytest.mark.parametrize("template", [
        "env -S 'bash {path}'",
        "su -c 'bash {path}'",
        "runuser -u root -c 'bash {path}'",
    ])
    def test_command_string_options_in_cron_prompt_are_rescanned(self, tmp_path, template):
        helper = tmp_path / "helper.sh"
        helper.write_text("#!/bin/sh\nsystemctl stop hermes-gateway\n", encoding="utf-8")
        with pytest.raises(GatewayLifecycleBlocked):
            check_gateway_lifecycle(template.format(path=helper.as_posix()), None)


# The only shapes the port lets through that the pre-port guard blocked. Each is inert because bash
# reads a genuinely *longer command word* (`myhermes`, `.hermes`, `x-hermes`) or a *different word*
# (`restarted`) — a LEXICAL word tail, present verbatim in the string that runs. A word char before
# `hermes` is NOT by itself proof of inertness: a bash expansion can leave a word char that vanishes
# at runtime (`$1hermes` -> `hermes`). Those are covered by NOT_INERT_LOOKALIKES below, which MUST
# block. Keep this list to shapes where the preceding word char is literal and survives to exec.
ALLOWS_ADDED = [
    "echo after the hermes gateway restarted cleanly",    # a74eb2dd41: trailing \b (#92372)
    "the hermes gateway stopped responding",              # a74eb2dd41: trailing \b (#92372)
    "myhermes gateway restart",                           # 180f981125/20e308fea7: word tail
    "x-hermes gateway stop",                              # 180f981125/20e308fea7: word tail
    ".hermes gateway restart",                            # 180f981125/20e308fea7: dotfile name
]

# Look like a word tail (a word char sits before `hermes`) but bash EXPANDS the prefix away, leaving
# the bare `hermes` CLI. The pre-port guard blocked these as substrings; the fork must NOT enshrine
# "any word char before hermes is inert" and let them through. See F1 (MUSTPORT-5B r1).
NOT_INERT_LOOKALIKES = [
    "$1hermes gateway restart",
    "$9hermes gateway stop",
    "$0hermes gateway uninstall",
    "env -u _HERMES_GATEWAY $1hermes gateway restart",
]


class TestAllowsAddedAreExactlyTheInertOnes:
    @pytest.mark.parametrize("command", ALLOWS_ADDED)
    def test_inert_shapes_allowed(self, command):
        assert contains_gateway_lifecycle_command_or_referenced_script(command) is False

    @pytest.mark.parametrize("command", NOT_INERT_LOOKALIKES)
    def test_positional_parameter_lookalikes_still_block(self, command):
        # Regression against e1bd3b3: these were allowed (word char before hermes). They must block.
        assert contains_gateway_lifecycle_command(command) is True
        assert contains_gateway_lifecycle_command_or_referenced_script(command) is True

    def test_unresolvable_cron_script_values_no_longer_crash(self, monkeypatch):
        # c8d48b8b13 / 863e313185: a NUL-bearing value cannot name a runnable script; the pre-port
        # guard raised a bare ValueError from read_bytes() instead of scanning nothing.
        check_gateway_lifecycle("nightly", "nul\x00byte.sh")


# The pre-port (base) Branch A pattern, copied verbatim from
# `git show 0bacb7fc84:cron/lifecycle_guard.py`. It has NO left-context lookbehind, so it blocks
# `hermes gateway restart|stop` wherever the substring appears — including behind any prefix.
_BASE_BRANCH_A = re.compile(r"(?i)hermes\s+gateway\s+(?:restart|stop)")

# Prefixes placed immediately before `hermes`. Every printable ASCII punctuation char, plus the
# shell special/positional parameters called out in the F1 brief.
_DIFFERENTIAL_PREFIXES = sorted(set(
    list(string.punctuation)
    + [f"${d}" for d in range(10)]
    + ["${x}", "$@", "$*", "$#", "$?", "$$", "$!", "$-", "$_", "'", '"', "\\"]
))

# The ONLY documented inert allow-list: bash reads a genuinely longer command word or a variable
# name, so the CLI never runs. Keyed on the char immediately before `hermes`:
#   `.`  -> `.hermes` dotfile command      `-` -> `-hermes` / `x-hermes` word tail
#   `_`  -> `_hermes` word tail, and `$_hermes` (bash expands variable *named* `_hermes`)
#   `$-` -> `$-` (shell flags) is never empty, so `$-hermes` == `<flags>hermes`, a different command
# Everything else that the base pattern blocks MUST be blocked by the candidate too.
_INERT_LAST_CHARS = "._-"


class TestPositionalParameterDifferential:
    """F1 differential: wherever the pre-port Branch A pattern blocked, the candidate must block —
    except the small, commented inert allow-list. This FAILS against commit e1bd3b3 for the
    `$0`..`$9` prefixes (base blocks the substring; e1bd3b3's `(?<![\\w.\\-])` lookbehind treats the
    digit as an inert word tail and ALLOWS)."""

    @pytest.mark.parametrize("command", ["hermes gateway restart", "hermes gateway stop"])
    @pytest.mark.parametrize("prefix", _DIFFERENTIAL_PREFIXES)
    def test_base_block_implies_candidate_block(self, prefix, command):
        text = prefix + command
        if not _BASE_BRANCH_A.search(text):
            return  # base did not block this shape; nothing to enforce
        if prefix[-1] in _INERT_LAST_CHARS:
            # Documented inert allow-list: bash reads a longer word / a variable name, so allowing
            # is correct. (`.hermes`, `-hermes`, `_hermes`, `$_hermes`, `$-hermes`.)
            assert contains_gateway_lifecycle_command(text) is False, (prefix, command)
            return
        assert contains_gateway_lifecycle_command(text) is True, (prefix, command)

    @pytest.mark.parametrize("verb", ["restart", "stop", "uninstall"])
    @pytest.mark.parametrize("d", list(range(10)))
    def test_every_positional_parameter_form_blocks(self, d, verb):
        # `$0`..`$9` glued to `hermes` expand away, leaving the bare CLI — for all three verbs
        # (base's pattern lacks `uninstall`, so this is asserted directly against the candidate).
        text = f"${d}hermes gateway {verb}"
        assert contains_gateway_lifecycle_command(text) is True

    def test_dollar_underscore_reads_as_variable_name(self):
        # `$_hermes` -> bash expands the variable *named* `_hermes` (unset), never `$_` + `hermes`.
        assert contains_gateway_lifecycle_command("$_hermes gateway restart") is False

    def test_dollar_dash_is_never_empty(self):
        # `$-` (shell option flags) is non-empty under `bash -c`, so `$-hermes` == `<flags>hermes`.
        assert contains_gateway_lifecycle_command("$-hermes gateway restart") is False


class TestBinaryMagicReferencedScriptScanned:
    """F3: a referenced script whose bytes start with a binary magic is still executed by the shell
    (bash runs the text behind the `MZ`/ELF prefix), so the walk must scan it — matching D5's cron
    `script` behaviour instead of skipping it. FAILS against e1bd3b3 (walk used skip_binary=True)."""

    @pytest.mark.parametrize("payload", [
        b"MZ\nhermes gateway restart\n",
        b"\x7fELF\nsystemctl restart hermes-gateway\n",
        b"\x1f\x8b\nhermes gateway stop\n",
    ])
    def test_binary_magic_referenced_shell_script_is_scanned(self, tmp_path, payload):
        script = tmp_path / "x.sh"
        script.write_bytes(payload)
        assert contains_gateway_lifecycle_command_or_referenced_script(
            f"bash {script.as_posix()}"
        ) is True

    def test_genuine_binary_reference_without_command_stays_allowed(self, tmp_path):
        # A binary-magic file with no lifecycle command in it must still not false-positive.
        script = tmp_path / "tool.sh"
        script.write_bytes(b"MZ\nprintf hello\n")
        assert contains_gateway_lifecycle_command_or_referenced_script(
            f"bash {script.as_posix()}"
        ) is False


def _symlinks_available(tmp_path) -> bool:
    probe = tmp_path / "_probe_link"
    try:
        probe.symlink_to(tmp_path / "_probe_target")
    except (OSError, NotImplementedError):
        return False
    finally:
        try:
            probe.unlink()
        except OSError:
            pass
    return True


class TestSymlinkLoopFailsClosed:
    """F4: a cyclic symlink referenced as a script must fail closed, not abort the whole walk (on
    Python <= 3.12 `resolve()` raised RuntimeError, which fell back to the direct scan only)."""

    def test_symlink_loop_referenced_script_is_blocked(self, tmp_path):
        if not _symlinks_available(tmp_path):
            pytest.skip("symlinks unavailable on this platform/privilege level")
        a = tmp_path / "a.sh"
        b = tmp_path / "b.sh"
        a.symlink_to(b)
        b.symlink_to(a)
        assert contains_gateway_lifecycle_command_or_referenced_script(
            f"bash {a.as_posix()}"
        ) is True

    def test_symlink_loop_does_not_hide_a_sibling_lifecycle_script(self, tmp_path):
        # The core F4 concern: a loop must not abort the walk and let a sibling evil script slip.
        if not _symlinks_available(tmp_path):
            pytest.skip("symlinks unavailable on this platform/privilege level")
        a = tmp_path / "loop.sh"
        b = tmp_path / "loop2.sh"
        a.symlink_to(b)
        b.symlink_to(a)
        evil = tmp_path / "evil.sh"
        evil.write_text("#!/bin/sh\nhermes gateway restart\n", encoding="utf-8")
        command = f"bash {a.as_posix()}; bash {evil.as_posix()}"
        assert contains_gateway_lifecycle_command_or_referenced_script(command) is True


class TestTerminalRefusalMessages:
    """F2: the in-gateway hard block returns a distinct, accurate message when it fires on a
    fail-closed scan-budget or device/FIFO refusal instead of a detected lifecycle command."""

    def _patch_env(self, monkeypatch):
        import tools.terminal_tool as tt
        eid = "default"

        class _FakeEnv:
            env = {}
            def execute(self, command, **kwargs):  # pragma: no cover
                raise AssertionError("execute must not be reached")

        monkeypatch.setattr(tt, "_active_environments", {eid: _FakeEnv()})
        monkeypatch.setattr(tt, "_last_activity", {eid: 0.0})
        monkeypatch.setattr(tt, "_task_env_overrides", {})
        monkeypatch.setattr(
            tt, "_get_env_config",
            lambda: {"env_type": "local", "cwd": "/tmp", "timeout": 60, "lifetime_seconds": 3600},
        )
        monkeypatch.setenv("_HERMES_GATEWAY", "1")

    def test_reason_codes(self, monkeypatch, tmp_path):
        # Direct unit check of the reason channel the message maps from.
        assert lifecycle_guard.gateway_lifecycle_block_reason("hermes gateway restart") == (
            "lifecycle-command"
        )
        assert lifecycle_guard.gateway_lifecycle_block_reason("echo hi") is None
        monkeypatch.setattr(lifecycle_guard, "_MAX_LIFECYCLE_SCAN_LINE_BYTES", 8)
        assert lifecycle_guard.gateway_lifecycle_block_reason("echo " + "x" * 40) == "scan-budget"

    def test_scan_budget_message(self, monkeypatch):
        import tools.terminal_tool as tt
        self._patch_env(monkeypatch)
        monkeypatch.setattr(lifecycle_guard, "_MAX_LIFECYCLE_SCAN_LINE_BYTES", 8)

        result = json.loads(tt.terminal_tool(command="echo " + "x" * 60, background=True))

        assert result["exit_code"] == 1
        assert "scan budget" in result["error"]

    def test_device_or_fifo_message(self, monkeypatch):
        import os as _os
        if _os.name == "nt":
            pytest.skip("no /dev/null device on Windows")
        import tools.terminal_tool as tt
        self._patch_env(monkeypatch)

        result = json.loads(tt.terminal_tool(command="bash /dev/null", background=True))

        assert result["exit_code"] == 1
        assert "device" in result["error"]
