"""Fork-local regressions for the MUSTPORT-5B lifecycle_guard port (v2026.9.7).

* AUTHORITY-NOT-WIDENED: every gateway-lifecycle command the pre-port guard blocked is still
  blocked by every entry point (pure scan and its hermes_cli.cron re-export, referenced-script
  walk, cron check for prompt / shell script / .py script, and terminal_tool inside the gateway).
  The table includes the shapes upstream v2026.9.7 would ALLOW but the fork keeps blocking
  because they are not provably inert (heredoc bodies, path-invoked CLI, ``skill``/``fkill``,
  data-sink arguments, expansion / continuation glue before ``hermes``).
* Strict differential against the pre-port Branch A: no inert exceptions.
* Hardening that must hold (each case fails against the pre-port guard).
* Explicit per-category cases: NUL padding, argv-list / execute_code, quote-aware segmentation,
  heredoc (kept blocking), privilege prefixes, self-restart.
* Accepted over-blocks (inert look-alikes), pinned so a reviewer sees the exact surface.
* Binary skip scoped by reference position; Ctrl-Z and symlink fail-closed reads (MUSTPORT-5B r3).

Paths are passed as POSIX strings: backslash is a shell escape to the tokenizer.
"""

import errno
import json
import os
import re
import shlex
import stat
import sys
from pathlib import Path

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


# MUSTPORT-5B r3 (M1-M4): each runs `hermes gateway restart|stop` although a character sits directly
# before `hermes` in the text; c75f256's lookbehind allowed all of them. The shell deletes the
# continuation (M1), `$-` is empty under dash `-c` (M2), the variable holds `hermes` (M3), zsh reads
# `$10` as the tenth parameter (M4).
R3_EXPANSION_GLUE = [
    "$\\\n1hermes gateway restart",
    "$\\\n-hermes gateway stop",
    "$-hermes gateway stop",
    "sh -c '$-hermes gateway stop'",
    "_hermes=hermes; $_hermes gateway restart",
    "MYHERMES=hermes; $MYHERMES gateway restart",
    "zsh -c '$10hermes gateway restart'",
]

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
    # Trailing boundary (upstream #92372 `\b` after the verb group).
    "echo after the hermes gateway restarted cleanly",
    "the hermes gateway stopped responding",
    # --- positional-parameter bypass (MUSTPORT-5B r1, F1) -----------------------------------
    # `$1`..`$9` expand to nothing under `bash -c`/cron, so `$1hermes gateway restart` runs the CLI.
    "$1hermes gateway restart",
    "true;$9hermes gateway stop",
    "env -u _HERMES_GATEWAY $1hermes gateway restart",
    "sh -c '$1hermes gateway restart'",
    # --- expansion / continuation glue (MUSTPORT-5B r3, M1-M4) ------------------------------
    *R3_EXPANSION_GLUE,
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

    def test_nul_first_line_cron_script_still_scanned(self, tmp_path):
        # The cron `script` read never skips: the pre-port guard decoded every cron script in full.
        script = tmp_path / "restart.sh"
        script.write_bytes(b"\x00\x01\x02 not a script\nhermes gateway restart\n")
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


class TestExpansionGlueEntryPoints:
    """M1-M4 (MUSTPORT-5B r3) through the entry points PRE_PORT_BLOCKED does not reach: a cron
    ``.py`` script body and ``execute_code`` with ``shell=True``. (Pure scan, walk, terminal with
    force=True, cron prompt and cron ``.sh`` run over PRE_PORT_BLOCKED, which includes them.)"""

    @staticmethod
    def _python_source(command: str) -> str:
        return f'import subprocess\nsubprocess.run(r"""{command}""", shell=True)\n'

    @pytest.mark.parametrize("command", R3_EXPANSION_GLUE)
    def test_cron_python_script_body_blocks(self, tmp_path, command):
        script = tmp_path / "job.py"
        script.write_text(self._python_source(command), encoding="utf-8")
        with pytest.raises(GatewayLifecycleBlocked):
            check_gateway_lifecycle("", script.as_posix())

    @pytest.mark.parametrize("command", R3_EXPANSION_GLUE)
    def test_execute_code_shell_true_blocks(self, monkeypatch, command):
        result = TestExecuteCodeLifecycleGuard()._run(monkeypatch, self._python_source(command))
        assert result is not None
        assert "Blocked" in result["error"]


class TestContinuationViews:
    """M1 (MUSTPORT-5B r3): every pattern pass sees backslash-newline continuations DELETED, as the
    shell does, and the pre-r3 space-substituted view is still scanned, so nothing it blocked
    becomes allowed. c75f256 handed the space-substituted text to the tokenizer, so its own
    continuation deletion never applied."""

    @pytest.mark.parametrize("command", [
        "her\\\nmes gateway restart",
        "hermes gateway re\\\nstart",
        "systemctl re\\\nstart hermes-gateway",
        "hermes gateway re'st'\\\nart",          # token pass over the deleted view
    ])
    def test_deleted_view_blocks(self, command):
        assert contains_gateway_lifecycle_command(command) is True
        assert contains_gateway_lifecycle_command_or_referenced_script(command) is True

    @pytest.mark.parametrize("command", [
        "hermes\\\ngateway re\"start\"",          # token pass over the spaced view (c75f256 verdict)
        "systemctl restart \\\r\n  hermes-gateway",  # `\` + CRLF: only the spaced view joins it
    ])
    def test_spaced_view_still_blocks(self, command):
        assert contains_gateway_lifecycle_command(command) is True
        assert contains_gateway_lifecycle_command_or_referenced_script(command) is True

    def test_referenced_script_path_split_by_continuation(self, tmp_path):
        (tmp_path / "restart.sh").write_text("#!/bin/sh\nhermes gateway restart\n", encoding="utf-8")
        command = f"bash {tmp_path.as_posix()}/re\\\nstart.sh"
        assert contains_gateway_lifecycle_command_or_referenced_script(command) is True


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


# Inert look-alikes the guard blocks ON PURPOSE (accepted over-blocking, MUSTPORT-5B r3): Branch A
# has no left anchor and no trailing boundary, exactly like the pre-port guard. c75f256 allowed
# these, but each sits next to an expansion form that does run the CLI (`$-hermes` under dash,
# `$_hermes` holding `hermes`, `$\<NL>1hermes`), and no lookbehind separates the two reliably.
ACCEPTED_OVER_BLOCKS = [
    "myhermes gateway restart",
    "x-hermes gateway stop",
    ".hermes gateway restart",
    "$_hermes gateway restart",
    "$__hermes gateway stop",
    "$-hermes gateway restart",
    "$10hermes gateway uninstall",
    "hermes gateway uninstaller --help",
    "echo after the hermes gateway restarted cleanly",
    "mylaunchctl stop foo; echo ai.hermes.gateway",
]


class TestAcceptedOverBlocks:
    @pytest.mark.parametrize("command", ACCEPTED_OVER_BLOCKS)
    def test_lookalikes_block(self, command):
        assert contains_gateway_lifecycle_command(command) is True
        assert contains_gateway_lifecycle_command_or_referenced_script(command) is True

    @pytest.mark.parametrize("command", [
        # c75f256's `(?:\b|(?<=\$\d))launchctl` missed both: no word boundary inside `_launchctl` /
        # `0launchctl`, and `$10` is not `$` + one digit.
        '_launchctl=launchctl; label=ai.hermes.gateway; $_launchctl bootout "gui/501/$label"',
        "label=ai.hermes.gateway; zsh -c '$10launchctl bootout \"gui/501/$label\"'",
    ])
    def test_launchctl_verbs_pass_has_no_left_anchor(self, command):
        assert contains_gateway_lifecycle_command(command) is True

    def test_unresolvable_cron_script_values_no_longer_crash(self, monkeypatch):
        # c8d48b8b13 / 863e313185: a NUL-bearing value cannot name a runnable script; the pre-port
        # guard raised a bare ValueError from read_bytes() instead of scanning nothing.
        check_gateway_lifecycle("nightly", "nul\x00byte.sh")


# The pre-port (base) Branch A pattern, copied verbatim from
# `git show 0bacb7fc84:cron/lifecycle_guard.py`. It has NO left-context lookbehind, so it blocks
# `hermes gateway restart|stop` wherever the substring appears — including behind any prefix.
_BASE_BRANCH_A = re.compile(r"(?i)" r"(?:hermes\s+gateway\s+(?:restart|stop))")

# Prefixes placed immediately before `hermes`: every printable ASCII char, positional and special
# parameters, variable-name tails, quotes, backslash, and continuation glue.
_DIFFERENTIAL_PREFIXES = sorted(set(
    [chr(code) for code in range(0x20, 0x7F)]
    + [f"${d}" for d in range(13)]
    + ["$-", "$_", "$__", "$X_", "$MY", "${x}", "$@", "$*", "$#", "$?", "$$", "$!"]
    + ["'", '"', "\\", "\\\n", "$\\\n1", "$\\\n-"]
))


class TestBaseBranchADifferential:
    """Strict differential (MUSTPORT-5B r3): wherever the pre-port Branch A blocked, the candidate
    blocks. NO inert exceptions — c75f256's `_INERT_LAST_CHARS` allow-list (`.`, `_`, `-`) let
    `$-hermes` (empty `$-` under dash) and `$_hermes` (a variable holding `hermes`) run the CLI."""

    @pytest.mark.parametrize("verb", ["restart", "stop", "uninstall"])
    @pytest.mark.parametrize("prefix", _DIFFERENTIAL_PREFIXES)
    def test_base_block_implies_candidate_block(self, prefix, verb):
        text = f"{prefix}hermes gateway {verb}"
        if not _BASE_BRANCH_A.search(text):
            return  # BASE did not block this shape (`uninstall` is not in its pattern)
        assert contains_gateway_lifecycle_command(text) is True, (prefix, verb)
        assert contains_gateway_lifecycle_command_or_referenced_script(text) is True, (prefix, verb)

    @pytest.mark.parametrize("prefix", _DIFFERENTIAL_PREFIXES)
    def test_differential_is_not_vacuous(self, prefix):
        assert _BASE_BRANCH_A.search(f"{prefix}hermes gateway restart")

    @pytest.mark.parametrize("verb", ["restart", "stop", "uninstall"])
    @pytest.mark.parametrize("d", list(range(13)))
    def test_every_positional_parameter_form_blocks(self, d, verb):
        # `$0`..`$9` glued to `hermes` expand away under bash; zsh also reads `$10`..`$12` as
        # parameters. All three verbs (base's pattern lacks `uninstall`, so asserted directly).
        text = f"${d}hermes gateway {verb}"
        assert contains_gateway_lifecycle_command(text) is True


class TestBinaryMagicReferencedScriptScanned:
    """F3: a referenced script whose bytes start with a binary magic but has no NUL in its first
    line is text the shell runs (bash runs what follows `MZ\\n`), so the walk scans it in every
    reference position — matching D5's cron `script` behaviour."""

    @pytest.mark.parametrize("payload", [
        b"MZ\nhermes gateway restart\n",
        b"\x7fELF\nsystemctl restart hermes-gateway\n",
        b"\x1f\x8b\nhermes gateway stop\n",
    ])
    @pytest.mark.parametrize("template", [
        "bash {path}", "{path}", "sh {path}", ". {path}", "source {path}",
    ])
    def test_binary_magic_referenced_shell_script_is_scanned(self, tmp_path, payload, template):
        script = tmp_path / "x.sh"
        script.write_bytes(payload)
        assert contains_gateway_lifecycle_command_or_referenced_script(
            template.format(path=script.as_posix())
        ) is True

    def test_genuine_binary_reference_without_command_stays_allowed(self, tmp_path):
        # A binary-magic file with no lifecycle command in it must still not false-positive.
        script = tmp_path / "tool.sh"
        script.write_bytes(b"MZ\nprintf hello\n")
        assert contains_gateway_lifecycle_command_or_referenced_script(
            f"bash {script.as_posix()}"
        ) is False


# Native-executable headers followed by shell text (MUSTPORT-5B r2 review): bash refuses these (a
# NUL in the first line), but dash (/bin/sh on Debian), `.`/`source` in bash and dash, busybox and
# the cron scheduler run the text after the header.
NATIVE_HEADER_TEXT = [
    pytest.param(b"MZ\x90\x00\x03\nhermes gateway restart\n", id="pe-header"),
    pytest.param(b"\x7fELF\x02\x01\x01\x00\x00\nhermes gateway restart\n", id="elf-header"),
]

# Reference positions that read the file as text: never skipped as binary.
NEVER_SKIP_TEMPLATES = [
    "sh {path}", "dash {path}", "ksh {path}", "zsh {path}", "ash {path}", "busybox sh {path}",
    ". {path}", "source {path}", "sudo sh {path}", "sh -e {path}",
]

# Reference positions where the executing program refuses a native executable as a script.
SKIP_TEMPLATES = ["{path}", "bash {path}", "bash -e {path}", "sudo {path}", "env FOO=1 {path}"]


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


class TestBinarySkipByReferencePosition:
    """M6 (MUSTPORT-5B r3): c75f256 read every referenced file, so any path-invoked binary larger
    than the remaining budget failed closed even with force (`/usr/bin/python3 -c ...`,
    `.venv/bin/python -m pytest`). The skip is now scoped by position, and a native executable is
    classified from its header before the size check."""

    def test_real_interpreter_by_path_is_allowed(self):
        interpreter = shlex.quote(Path(sys.executable).as_posix())
        for template in ('{exe} -c "print(1)"', "bash {exe}", "sudo {exe} -m pytest", "timeout 60 {exe} -V"):
            command = template.format(exe=interpreter)
            assert contains_gateway_lifecycle_command_or_referenced_script(command) is False, command

    def test_real_interpreter_via_symlink_is_allowed(self, tmp_path):
        if not _symlinks_available(tmp_path):
            pytest.skip("symlinks unavailable on this platform/privilege level")
        link = tmp_path / "python-link"
        link.symlink_to(Path(sys.executable))
        path = link.as_posix()
        for template in ('{path} -c "print(1)"', "bash {path}"):
            command = template.format(path=path)
            assert contains_gateway_lifecycle_command_or_referenced_script(command) is False, command

    def test_large_native_executable_is_classified_before_the_size_check(self, tmp_path):
        binary = tmp_path / "tool"
        binary.write_bytes(b"\x7fELF\x02\x01\x01\x00" + bytes(8) + b"\x90" * (2 * 1024 * 1024))
        path = binary.as_posix()
        for template in ("{path} --version", "bash {path}", "sudo {path}", "env FOO=1 {path} -x"):
            command = template.format(path=path)
            assert contains_gateway_lifecycle_command_or_referenced_script(command) is False, command
        # A skip wins over fail-closed even at a tiny cap: only the header is read.
        assert lifecycle_guard._read_referenced_script(binary, max_bytes=16) == (None, False, None)
        # Where it would be read as text it is never skipped, so the oversize fail-closed applies.
        assert contains_gateway_lifecycle_command_or_referenced_script(f"sh {path}") is True
        assert lifecycle_guard._read_referenced_script(binary, skip_binary=False) == (
            None, True, "scan-budget"
        )

    @pytest.mark.parametrize("name", ["bash", "ash", "sh"])
    def test_path_invoked_shell_named_script_is_scanned(self, tmp_path, name):
        # The shell operand is walked, and so is the executable when it is a local script.
        (tmp_path / name).write_text("#!/bin/sh\nhermes gateway restart\n", encoding="utf-8")
        (tmp_path / "x.sh").write_text("echo ok\n", encoding="utf-8")
        command = f"{(tmp_path / name).as_posix()} {(tmp_path / 'x.sh').as_posix()}"
        assert contains_gateway_lifecycle_command_or_referenced_script(command) is True

    @pytest.mark.parametrize("payload", NATIVE_HEADER_TEXT)
    @pytest.mark.parametrize("template", NEVER_SKIP_TEMPLATES)
    def test_native_header_text_blocked_where_read_as_text(self, tmp_path, payload, template):
        script = tmp_path / "x.sh"
        script.write_bytes(payload)
        assert contains_gateway_lifecycle_command_or_referenced_script(
            template.format(path=script.as_posix())
        ) is True

    @pytest.mark.parametrize("payload", NATIVE_HEADER_TEXT)
    @pytest.mark.parametrize("name", ["job.sh", "job"])
    def test_native_header_text_cron_script_blocked(self, tmp_path, payload, name):
        script = tmp_path / name
        script.write_bytes(payload)
        with pytest.raises(GatewayLifecycleBlocked):
            check_gateway_lifecycle("", script.as_posix())

    @pytest.mark.parametrize("payload", NATIVE_HEADER_TEXT)
    @pytest.mark.parametrize("template", [
        "{path}; sh {path}", "bash {path} && . {path}", "bash {path}; busybox sh {path}",
    ])
    def test_skipped_reference_does_not_hide_a_later_text_reference(self, tmp_path, payload, template):
        # A skip-eligible read of the same file must not mark it visited for a `sh X` / `. X` read.
        script = tmp_path / "x.sh"
        script.write_bytes(payload)
        assert contains_gateway_lifecycle_command_or_referenced_script(
            template.format(path=script.as_posix())
        ) is True

    @pytest.mark.parametrize("payload", NATIVE_HEADER_TEXT)
    @pytest.mark.parametrize("template", SKIP_TEMPLATES)
    def test_native_header_skipped_where_refused_as_binary(self, tmp_path, payload, template):
        # Pinned decision: bash refuses a NUL-first-line file both as `bash X` and on the ENOEXEC
        # fallback of a direct exec, so these are skipped like a real binary. Residual: a direct exec
        # whose fallback is /bin/sh (dash parent, a wrapper's execvp) would run the text. The
        # pre-port guard read no referenced file, so this does not widen it.
        script = tmp_path / "x.sh"
        script.write_bytes(payload)
        assert contains_gateway_lifecycle_command_or_referenced_script(
            template.format(path=script.as_posix())
        ) is False

    @pytest.mark.parametrize("template", SKIP_TEMPLATES)
    def test_nul_first_line_without_native_magic_is_scanned(self, tmp_path, template):
        # Narrower than bash's own refusal on purpose (accepted over-blocking): only a native
        # executable header is skipped.
        script = tmp_path / "blob.sh"
        script.write_bytes(b"\x00\x01\x02 not a script\nhermes gateway restart\n")
        assert contains_gateway_lifecycle_command_or_referenced_script(
            template.format(path=script.as_posix())
        ) is True

    @pytest.mark.parametrize("payload", [
        # A magic whose NUL follows the first newline: bash runs line 2.
        pytest.param(b"MZ\nhermes gateway restart\n\x00", id="magic-nul-after-first-newline"),
        # bash inspects only the first 80 bytes.
        pytest.param(b"MZ" + b"a" * 90 + b"\x00\nhermes gateway restart\n", id="magic-nul-beyond-80"),
        # A shebang hands the file to the named interpreter; dash strips NULs.
        pytest.param(b"#!/bin/sh\x00\nhermes gateway restart\n", id="shebang"),
        # A NUL after the first line: bash runs straight past it (#77927).
        pytest.param(b"echo ok\n\x00\nhermes gateway restart\n", id="nul-after-first-line"),
    ])
    @pytest.mark.parametrize("template", SKIP_TEMPLATES)
    def test_text_behind_a_header_is_scanned_in_skip_positions(self, tmp_path, payload, template):
        script = tmp_path / "x.sh"
        script.write_bytes(payload)
        assert contains_gateway_lifecycle_command_or_referenced_script(
            template.format(path=script.as_posix())
        ) is True


class TestCtrlZIsNotEndOfFile:
    """M5 (MUSTPORT-5B r3): scripts are opened with O_BINARY. In Windows' CRT text mode a read stops
    at the first 0x1A byte, so everything after `echo hi\\x1a` was invisible to the scan; the
    pre-port guard used `read_bytes()`, which is binary. Runs on every platform; on POSIX it guards
    against a regression."""

    PAYLOAD = b"echo hi\x1a\nhermes gateway restart\n"

    def test_cron_shell_script_blocks(self, tmp_path):
        script = tmp_path / "job.sh"
        script.write_bytes(self.PAYLOAD)
        with pytest.raises(GatewayLifecycleBlocked):
            check_gateway_lifecycle("nightly", script.as_posix())

    @pytest.mark.parametrize("template", ["bash {path}", "sh {path}", ". {path}", "{path}"])
    def test_referenced_script_blocks(self, tmp_path, template):
        script = tmp_path / "x.sh"
        script.write_bytes(self.PAYLOAD)
        assert contains_gateway_lifecycle_command_or_referenced_script(
            template.format(path=script.as_posix())
        ) is True

    def test_read_returns_text_after_ctrl_z(self, tmp_path):
        script = tmp_path / "x.sh"
        script.write_bytes(self.PAYLOAD)
        text, unsafe, _reason = lifecycle_guard._read_referenced_script(script)
        assert unsafe is False
        assert "hermes gateway restart" in text

    def test_open_requests_binary_mode(self, tmp_path, monkeypatch):
        script = tmp_path / "x.sh"
        script.write_bytes(self.PAYLOAD)
        flags_seen = []
        real_open = lifecycle_guard.os.open

        def _spy(path, flags, *args, **kwargs):
            flags_seen.append(flags)
            return real_open(path, flags, *args, **kwargs)

        monkeypatch.setattr(lifecycle_guard.os, "open", _spy)
        lifecycle_guard._read_referenced_script(script)
        binary = getattr(os, "O_BINARY", 0)
        assert flags_seen
        assert all(flags & binary == binary for flags in flags_seen)


class TestSymlinkLoopFailsClosed:
    """F4 / M7: a cyclic or dangling symlink referenced as a script fails closed and never aborts
    the whole walk. Windows 11 reports a loop as a plain ENOENT from `os.open`/`os.stat` (no ELOOP,
    no RuntimeError), while `os.lstat` still succeeds, so the guard keys on the link itself."""

    def test_symlink_loop_referenced_script_is_blocked(self, tmp_path):
        if not _symlinks_available(tmp_path):
            pytest.skip("symlinks unavailable on this platform/privilege level")
        a = tmp_path / "a.sh"
        b = tmp_path / "b.sh"
        a.symlink_to(b)
        b.symlink_to(a)
        for template in ("bash {path}", "{path}", ". {path}"):
            assert contains_gateway_lifecycle_command_or_referenced_script(
                template.format(path=a.as_posix())
            ) is True, template
        with pytest.raises(GatewayLifecycleBlocked):
            check_gateway_lifecycle("nightly", a.as_posix())

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

    def test_symlink_loop_in_an_ancestor_directory_is_blocked(self, tmp_path):
        if not _symlinks_available(tmp_path):
            pytest.skip("symlinks unavailable on this platform/privilege level")
        dir_a = tmp_path / "dir-a"
        dir_b = tmp_path / "dir-b"
        dir_a.symlink_to(dir_b, target_is_directory=True)
        dir_b.symlink_to(dir_a, target_is_directory=True)
        assert contains_gateway_lifecycle_command_or_referenced_script(
            f"bash {(dir_a / 'x.sh').as_posix()}"
        ) is True

    def test_dangling_symlink_is_blocked(self, tmp_path):
        # Accepted over-blocking: a dangling link cannot be told apart from a Windows loop.
        if not _symlinks_available(tmp_path):
            pytest.skip("symlinks unavailable on this platform/privilege level")
        link = tmp_path / "gone.sh"
        link.symlink_to(tmp_path / "missing-target.sh")
        for template in ("bash {path}", "{path}", ". {path}"):
            assert contains_gateway_lifecycle_command_or_referenced_script(
                template.format(path=link.as_posix())
            ) is True, template
        assert lifecycle_guard._read_referenced_script(link) == (None, True, "device-or-fifo")
        with pytest.raises(GatewayLifecycleBlocked):
            check_gateway_lifecycle("nightly", link.as_posix())

    def test_plain_missing_script_is_nothing_to_scan(self, tmp_path):
        missing = tmp_path / "missing.sh"
        assert lifecycle_guard._read_referenced_script(missing) == (None, False, None)
        assert contains_gateway_lifecycle_command_or_referenced_script(
            f"bash {missing.as_posix()}"
        ) is False
        check_gateway_lifecycle("nightly", missing.as_posix())

    @pytest.mark.parametrize("is_link,expected", [
        (True, (None, True, "device-or-fifo")),
        (False, (None, False, None)),
    ], ids=["link", "plain-missing"])
    def test_windows_loop_shape_is_keyed_on_the_link(self, tmp_path, monkeypatch, is_link, expected):
        # Portable M7 simulation (no symlink privilege needed): os.open and os.stat fail with a plain
        # ENOENT while os.lstat reports a symlink — exactly what Windows 11 returns for a loop.
        script = tmp_path / "loop.sh"
        target = os.fspath(script)
        real_open = os.open
        real_lstat = os.lstat

        def _open(path, flags, *args, **kwargs):
            if os.fspath(path) == target:
                raise FileNotFoundError(errno.ENOENT, "No such file or directory")
            return real_open(path, flags, *args, **kwargs)

        def _lstat(path, *args, **kwargs):
            if is_link and os.fspath(path) == target:
                return os.stat_result((stat.S_IFLNK | 0o777, 0, 0, 1, 0, 0, 0, 0, 0, 0))
            return real_lstat(path, *args, **kwargs)

        with monkeypatch.context() as patch:
            patch.setattr(lifecycle_guard.os, "open", _open)
            patch.setattr(lifecycle_guard.os, "lstat", _lstat)
            result = lifecycle_guard._read_referenced_script(script)
        assert result == expected


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

    def test_unresolvable_symlink_message(self, monkeypatch, tmp_path):
        if not _symlinks_available(tmp_path):
            pytest.skip("symlinks unavailable on this platform/privilege level")
        import tools.terminal_tool as tt
        link = tmp_path / "gone.sh"
        link.symlink_to(tmp_path / "missing-target.sh")
        self._patch_env(monkeypatch)

        result = json.loads(tt.terminal_tool(command=f"bash {link.as_posix()}", background=True))

        assert result["exit_code"] == 1
        assert "unresolvable" in result["error"]
