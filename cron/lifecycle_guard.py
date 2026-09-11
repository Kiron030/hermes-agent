"""Gateway lifecycle guard for cron job creation.

A cron job that restarts/stops the gateway from inside the gateway (``hermes gateway restart``,
``launchctl kickstart ai.hermes.gateway``, ``systemctl restart hermes-gateway``) kills the process,
the supervisor revives it, auto-resume re-runs the turn: a SIGTERM-respawn loop.
``cron.jobs.create_job`` rejects such specs on every creation path. Patterns are command-shaped —
anchored on concrete command identifiers — so they cannot fire on prose. Defence-in-depth layer.

Ported from upstream release tag v2026.9.7 (MUSTPORT-5B). Fork-local deviations keep the pre-port
(blocking) behaviour wherever the upstream change would ALLOW content that is not provably inert:

* no heredoc-body masking (upstream ``tools.shell_heredoc``): its consumer allowlist includes
  ``python``/``osascript`` (which execute the body) and path-prefixed ``cat``, and a masked
  ``cat > file`` body can be executed later in the same text;
* Branch A and the order-independent launchctl pass keep the pre-port LEFT-UNANCHORED form (no
  lookbehind before ``hermes``/``launchctl``), and Branch A has no trailing boundary. A character
  glued in front of ``hermes`` is not proof of an inert word — shell expansions vanish at runtime —
  so inert look-alikes (``myhermes gateway restart``, ``.hermes …``, ``hermes gateway restarted``)
  are blocked on purpose, as is a path-invoked CLI (``/usr/local/bin/hermes gateway restart``);
* Branch D keeps no leading word boundary, so ``skill``/``fkill`` process killers still match;
* no data-sink argument exemption: ``psql \\o |cmd``, ``ag --pager``, sqlite3 ``edit()`` and
  ``$(grep -o ...)`` turn "data" arguments into execution;
* the binary skip is scoped by reference position: only a native executable referenced where the
  executing program refuses to run it as a script (a direct-exec path, a ``bash X`` operand) is
  skipped. ``sh``/``dash``/``ksh``/``zsh``/``ash``/``busybox sh X``, ``.``/``source X`` and the cron
  ``script`` read never skip: those run a magic-prefixed or NUL-bearing file as text.
"""

from __future__ import annotations

import errno
import logging
import os
import re
import shlex
import stat
from itertools import chain, islice
from pathlib import Path
from typing import Callable, Iterator, Optional

logger = logging.getLogger(__name__)


class GatewayLifecycleBlocked(ValueError):
    """Raised when a cron job spec contains a gateway-lifecycle command."""


# Shell-level command shapes that target the gateway lifecycle; each branch is anchored on a
# concrete command identifier so it fires only on command-shaped strings, never prose.
_GATEWAY_LIFECYCLE_PATTERN = re.compile(
    r"(?i)"
    # Branch A: destructive `hermes gateway` ops. `start` is excluded: starting from inside a
    # gateway is benign and a job may legitimately start a sibling profile.
    # Fork deviation: the pre-port LEFT-UNANCHORED form — no lookbehind of any kind before `hermes`.
    # Upstream's command-position lookbehind (#77173) treats the character before `hermes` as proof
    # of an inert word tail, but a shell expansion can put a character there that vanishes at
    # runtime: `$1hermes` and `zsh -c '$10hermes'` (empty positional parameters), `$-hermes` (`$-` is
    # EMPTY under dash `-c` and dash/busybox script files), `$\<NL>1hermes` (the shell deletes the
    # continuation), `$_hermes` / `$MYHERMES` (a variable holding `hermes`). Every lookbehind patch
    # left another such form open (MUSTPORT-5B r1-r3), so there is no left anchor at all.
    # Accepted over-blocking: inert look-alikes (`myhermes gateway restart`, `.hermes …`,
    # `x-hermes …`), a path-invoked CLI (`/usr/local/bin/hermes gateway restart`, which is real) and
    # a path such as `/docs/hermes gateway restart-notes.md` all block, as they did before the port.
    # No trailing boundary either: upstream's `\b` (#92372) allows `hermes gateway restarted`, which
    # the pre-port guard blocked. `uninstall` is an upstream addition.
    r"(?:hermes\s+gateway\s+(?:restart|stop|uninstall))"
    # Branch B: launchctl ops anchored on a hermes-gateway label so unrelated hermes services stay
    # unblocked. `submit`/`bootstrap` register a NEW keepalive job wrapping an arbitrary helper (a
    # laundered restart); neutral-label submissions are caught by
    # `contains_launchctl_submit_command`. `bootout`/`remove`/`disable` are the
    # modern/legacy/durable forms of `unload`.
    # `submit` and `bootstrap` are included alongside the direct verbs (kickstart/etc.): `launchctl submit
    # -l ai.hermes.gateway-<suffix> -- <helper-script>` (or `launchctl bootstrap gui/<uid> <plist>`) creates
    # a NEW keepalive job wrapping an arbitrary helper, which is how a blocked direct restart/kill gets
    # laundered into a persistent restart loop instead (#62891) — same foot-gun, indirect shape.
    # Neutral-label submissions that dodge this text anchor are caught separately by
    # `contains_launchctl_submit_command` (execution-aware, label-independent). `bootout`/`remove`/`disable`
    # sit alongside `unload`: Apple deprecated load/unload in favour of bootstrap/bootout, so `bootout` is
    # the modern spelling of an already-listed verb, `remove` is its legacy sibling, and `disable` is what
    # makes an unload durable across boots. Omitting them left the bypassable approval layer
    # (tools/approval.py, skipped on force=True) as the only cover, while this hard block — documented as
    # "force=True cannot help here" — let them through (#80260).
    r"|(?:launchctl\s+(?:kickstart|unload|load|stop|restart|submit|bootstrap|bootout|remove|disable)\b[^\n]*\bhermes[.\-]?gateway)"
    # Branch C: systemctl ops on a hermes-gateway unit.
    r"|(?:systemctl\s+(?:-\S+\s+)*(?:restart|stop|start)\b[^\n]*\bhermes[.\-]?gateway)"
    # Branch D: pkill/kill of the gateway process, both token orders.
    # Fork deviation: upstream adds a leading \b so prose "skill" does not match. That also
    # allows real process killers whose name ends in "kill" (procps `skill`, `fkill`), so the
    # pre-port unanchored form is kept.
    r"|(?:p?kill\b[^\n]*\bhermes\b[^\n]*\bgateway)"
    r"|(?:p?kill\b[^\n]*\bgateway\b[^\n]*\bhermes)"
)

# Every branch uses `[^\n]*` between its verb and the gateway identifier so a match cannot span
# unrelated lines of a longer cron prompt/script, but a real multi-line invocation split across
# backslash-newline continuations (`launchctl submit \` / `  -l ai.hermes.gateway-... \`, the exact
# reported shape in #62891) must still match. Continuations are therefore normalized before matching
# rather than loosening `[^\n]*`. This is the legacy space-substituted view (it also covers `\` +
# CRLF); `contains_gateway_lifecycle_command` additionally scans the view with continuations DELETED,
# which is what the shell does.
_SHELL_LINE_CONTINUATION = re.compile(r"\\\r?\n[ \t]*")

# Python argv-list punctuation (`subprocess.run(["launchctl", "bootout", ...])`) separates exec'd
# words with brackets/commas. Stripped only for the token-join re-scan, never from raw text.
# See #68289.
_ARGV_LIST_PUNCTUATION = re.compile(r"[\[\],]+")

# Branch A2: `hermes -p <profile> gateway restart|stop` (also `--profile <name>` /
# `--profile=<name>`). The selector breaks Branch A's adjacency. A sibling-profile restart is a
# legitimate fleet operation, so the profile name is captured and blocked only when it equals the
# profile running the guard. `start` stays excluded as in Branch A.
# Unlike Branch A this form is NOT unconditionally self-targeting: issued from inside gateway `zeus`,
# `hermes -p venus gateway restart` operates on a sibling profile's gateway and is a legitimate fleet
# operation. The pattern captures the named profile so `contains_gateway_lifecycle_command` can block only
# the self-targeting shape (named profile == the profile running the guard). See #78028.
_PROFILE_FLAG_LIFECYCLE_PATTERN = re.compile(
    r"(?i)"
    r"hermes\s+"
    # Any global flags before the profile selector (each may carry a value).
    r"(?:-{1,2}\S+(?:\s+\S+)?\s+)*"
    # The selector: exactly the shapes the CLI's `_apply_profile_override` accepts.
    r"(?:--profile=([^\s]+)|(?:-p|--profile)\s+([^\s]+))"
    # Any global flags between the selector and the subcommand.
    r"(?:\s+-{1,2}\S+(?:\s+\S+)?)*"
    r"\s+gateway\s+(?:restart|stop)"
)

# Branch B needs the label AFTER the verb in one `[^\n]*` span; a loop that builds the label in an
# EARLIER `;`-segment (`label=${item%%:*}; launchctl bootout "gui/$uid/$label"`) leaves only
# `$label` next to the verb. These verbs act on an EXISTING job, so the hermes-gateway label anchor
# stays correct, but the check is "verb anywhere AND label anywhere".
# No profile identity available: cannot prove self-targeting, so do not block — sibling restarts must stay
# allowed (#78028).
# Left-unanchored like Branch A and Branch B: no `\b` or lookbehind before `launchctl`, so an
# expansion glued in front (`$1launchctl`, `$_launchctl`, `zsh -c '$10launchctl …'`) cannot hide the
# verb (MUSTPORT-5B r3). Accepted over-blocking: a `mylaunchctl stop …` next to a gateway label.
_LAUNCHCTL_LIFECYCLE_VERBS_RE = re.compile(
    r"(?i)launchctl\s+(?:kickstart|unload|load|stop|restart|bootout|kill|disable|remove)\b"
)
_HERMES_GATEWAY_LABEL_RE = re.compile(r"(?i)\bhermes[.\-]?gateway\b")

_SHELL_EXECUTABLES = frozenset({"sh", "bash", "dash", "ksh", "zsh", "ash"})
# Shells that refuse a binary file given as their script operand (bash `check_binary_file`: a NUL in
# the first line). dash/ksh/zsh/ash strip NULs or run straight through them.
_BINARY_REFUSING_SHELLS = frozenset({"bash"})
# `busybox <applet> X`: every busybox shell applet (its `bash` is an ash/hush alias) runs X as text.
_BUSYBOX_SHELL_APPLETS = frozenset({"sh", "ash", "hush", "bash"})
_SHELL_OPTIONS_WITH_VALUES = frozenset({"-O", "+O", "-o", "+o"})
_SHELL_COMMAND_FLAGS = {"-c", "--command"}
_MAX_REFERENCED_SCRIPT_BYTES = 1024 * 1024
_MAX_REFERENCED_SCRIPT_DEPTH = 8
_CONTROL_CHARS = frozenset(";&|()")

# Directory names directly under `Library` that mark a FileProvider-backed subtree: `Mobile
# Documents` is iCloud Drive; `CloudStorage` hosts third-party providers (Dropbox, OneDrive, Google
# Drive, ...).
_CLOUD_PLACEHOLDER_MARKERS = frozenset({"Mobile Documents", "CloudStorage"})

# Header bytes read to classify a referenced file BEFORE its size is checked (see
# _is_native_executable_header); must cover _BINARY_FIRST_LINE_BYTES.
_BINARY_SNIFF_BYTES = 256

# bash's check_binary_file() inspects this many leading bytes for a NUL in the first line.
_BINARY_FIRST_LINE_BYTES = 80

_NATIVE_EXECUTABLE_MAGICS = (
    b"\x7fELF",              # ELF — Linux/BSD executables and shared objects
    b"MZ",                   # PE/COFF — Windows .exe/.dll
    b"\xfe\xed\xfa\xce",     # Mach-O 32-bit
    b"\xfe\xed\xfa\xcf",     # Mach-O 64-bit
    b"\xce\xfa\xed\xfe",     # Mach-O 32-bit, byte-swapped
    b"\xcf\xfa\xed\xfe",     # Mach-O 64-bit, byte-swapped
    b"\xca\xfe\xba\xbe",     # Mach-O universal ("fat") binary
    b"\xca\xfe\xba\xbf",     # Mach-O universal 64-bit
)

# Ancestors `_unfollowable_link` inspects: one failed open must not turn a pathological path token
# into thousands of lstat() calls.
_MAX_LINK_ANCESTORS = 64

# Windows `st_reparse_tag` bit marking a name-surrogate reparse point (symlink, junction). An app
# execution alias (WindowsApps\python.exe) is not one and stays nothing-to-scan.
_REPARSE_TAG_NAME_SURROGATE = 0x20000000

_ReadRemoteScriptFn = Callable[[str], Optional[str]]

# Wrappers that hand execution to their argument tail: the real command sits further right, so a
# first-token-only guard would let `sudo bash ~/restart.sh` / `sudo launchctl submit ...` walk past.
# A guard that reads only the first token sees `sudo`/`env`/`nohup` and never inspects what they run, so
# `sudo bash ~/restart.sh` walked past the same walk that stops `bash ~/restart.sh`, and `sudo launchctl
# submit ...` past the label-independent submit block (#62891).
_TRANSPARENT_COMMAND_PREFIXES = frozenset({
    "sudo", "doas", "env", "nohup", "setsid", "nice", "ionice", "stdbuf",
    "timeout", "exec", "command", "builtin", "eatmydata",
    # Privilege and namespace wrappers: options, then the command they run.
    "pkexec", "su", "runuser", "setpriv", "systemd-run", "nsenter", "unshare",
})

# Wrapper options that consume the NEXT token, so a value is never mistaken for the command.
_TRANSPARENT_PREFIX_VALUE_OPTIONS = {
    "sudo": {"-u", "-g", "-U", "-C", "-p", "-r", "-t", "-T", "--user", "--group", "--prompt"},
    "doas": {"-u", "-C"},
    "env": {"-u", "--unset", "-S", "--split-string", "-C", "--chdir"},
    "nice": {"-n", "--adjustment"},
    "ionice": {"-c", "-n", "-p", "--class", "--classdata"},
    "stdbuf": {"-i", "-o", "-e", "--input", "--output", "--error"},
    "timeout": {"-s", "-k", "--signal", "--kill-after"},
    "pkexec": {"--user"},
    "su": {"-s", "--shell", "-g", "--group", "-G", "--supp-group"},
    "runuser": {"-u", "--user", "-s", "--shell", "-g", "--group", "-G", "--supp-group"},
    "setpriv": {"--reuid", "--regid", "--groups", "--inh-caps", "--ambient-caps", "--bounding-set",
                "--selinux-label", "--apparmor-profile"},
    "systemd-run": {"-u", "--unit", "-p", "--property", "-E", "--setenv", "--slice",
                    "--description", "--uid", "--gid", "--on-calendar", "--service-type"},
    "nsenter": {"-t", "--target", "-S", "--setuid", "-G", "--setgid", "-r", "--root", "-w", "--wd"},
    "unshare": {"--map-user", "--map-group", "--setgroups", "-R", "--root", "-w", "--wd"},
}

# Wrapper options carrying a COMMAND STRING (shell source, re-scanned like `sh -c`); treating it as
# an opaque value would hide whatever it runs (`env -S 'bash ~/restart.sh'`).
_STRING_COMMAND_OPTIONS = {
    "env": ("-S", "--split-string"),
    "su": ("-c", "--command"),
    "runuser": ("-c", "--command"),
}

# Wrappers whose first non-option operand is a VALUE, not the command (`timeout 60 bash x.sh`).
_TRANSPARENT_PREFIX_OPERANDS = {"timeout": 1}

_ENV_ASSIGNMENT = re.compile(r"^[A-Za-z_][A-Za-z0-9_]*=")

# Bound the walk: a pathological token run must not spin here.
_MAX_PREFIX_PEELS = 8


# --- profile identity -------------------------------------------------------------------------

def _current_profile_name() -> Optional[str]:
    """Profile running the guard: ``HERMES_PROFILE_NAME``/``HERMES_PROFILE`` env first, then
    ``hermes_cli.profiles.get_active_profile_name`` (from ``HERMES_HOME``); ``None`` if neither."""
    for env_name in ("HERMES_PROFILE_NAME", "HERMES_PROFILE"):
        value = os.environ.get(env_name)
        if value and value.strip():
            return value.strip()
    try:
        from hermes_cli.profiles import get_active_profile_name

        return get_active_profile_name() or None
    except Exception:
        return None


def _named_profile_is_current(named: str) -> bool:
    """True when *named* is the profile executing the guard. Without a profile identity
    self-targeting cannot be proven, so nothing is blocked (sibling restarts stay allowed)."""
    current = _current_profile_name()
    return bool(current) and named.strip().casefold() == current.strip().casefold()


# --- direct string scans ----------------------------------------------------------------------

def _contains_launchctl_gateway_lifecycle(normalized_text: str) -> bool:
    """Order-independent companion to Branch B — see the verbs regex comment."""
    return bool(_LAUNCHCTL_LIFECYCLE_VERBS_RE.search(normalized_text)) and bool(
        _HERMES_GATEWAY_LABEL_RE.search(normalized_text)
    )


def contains_gateway_lifecycle_command(text: str) -> bool:
    """Return True if *text* contains a gateway lifecycle command pattern.

    Passes, in order: raw-text regex (the only pass that fires on inputs shlex cannot tokenize, e.g.
    Python source); profile-flag form; the same regex on each shell-tokenized segment with quotes/
    escapes resolved (closes splice bypasses like ``kick"start"`` / ``kick\\start``);
    order-independent launchctl pass. Single choke point for every recursion level of
    ``_contains_unsafe_gateway_action``.

    That second pass exists because a real shell resolves quote-splicing (``kick"start"``) and
    backslash-escaping (``kick\\start``) into one literal word — ``kickstart`` — before the command ever
    runs. The raw text still has the quote or backslash sitting between the verb's two halves, so the first
    pass alone lets a spliced verb reach ``launchctl``/``systemctl`` untouched while still executing as the
    blocked lifecycle command (#80269, reported against #80260's bootout parity fix). Tokenizing closes that
    gap while keeping the same gateway-label anchoring (``_GATEWAY_LIFECYCLE_PATTERN`` still requires a
    ``hermes``/``gateway`` token) — this function is the single choke point
    ``_contains_unsafe_gateway_action`` calls at every recursion level, so referenced-script and ``sh -c``
    payload scanning inherit the fix automatically.

    Every pass runs over two views of backslash-newline continuations and blocks if EITHER matches
    (MUSTPORT-5B r3, M1): continuations DELETED, as the shell does (``$\\<NL>1hermes`` runs as
    ``$1hermes``, ``her\\<NL>mes`` as ``hermes``), and the pre-r3 space-substituted view, kept so no
    form it blocked becomes allowed.

    Not budgeted: callers holding untrusted, possibly huge text gate on
    ``lifecycle_scan_root_within_budget`` first (the tokenizer passes are quadratic on a giant token).
    """
    if not text:
        return False
    # Fork deviation: upstream masks "inert" heredoc bodies here (#88336). Not ported — see the
    # module docstring — so heredoc bodies are scanned like any other text.
    joined = text.replace("\\\n", "")
    spaced = _SHELL_LINE_CONTINUATION.sub(" ", text)
    views = (joined,) if spaced == joined else (joined, spaced)
    if any(_GATEWAY_LIFECYCLE_PATTERN.search(view) for view in views):
        return True
    # Profile-flag form: blocked only when the named profile IS the one running the guard.
    # Profile-flag form (#78028): `hermes -p <profile> gateway restart|stop` bypasses Branch A because the
    # selector sits between `hermes` and `gateway`. It is only the same foot-gun when the named profile IS
    # the profile running the guard — sibling-profile restarts are legitimate fleet operations and stay
    # allowed.
    for view in views:
        profile_match = _PROFILE_FLAG_LIFECYCLE_PATTERN.search(view)
        if profile_match:
            named = profile_match.group(1) or profile_match.group(2)
            # Profile ids cannot contain quotes (`^[a-z0-9][a-z0-9_-]{0,63}$`), so a shell-quoted
            # `-p 'zeus'` compares equal to the bare name.
            if named and _named_profile_is_current(named.strip().strip("\"'")):
                return True
    # Token-aware pass. Tokens are also re-joined with Python argv-list punctuation stripped, since
    # `subprocess.run(["launchctl", "bootout", ...])` separates argv words with commas/brackets.
    # Token-aware second pass (#80269): re-run the pattern on shell-tokenized segments where quotes/escapes
    # are resolved, closing splice bypasses like `kick"start"`. Runs after the profile-flag check so both
    # passes apply independently.
    # `_iter_command_segments` deletes continuations itself, so it gets the RAW text (deleted exactly
    # once, never an already-normalized view — M1) plus, when it differs, the spaced view (which has no
    # continuation left to delete).
    for source in ((text,) if spaced == joined else (text, spaced)):
        for segment in _iter_command_segments(source):
            joined_segment = " ".join(segment)
            if joined_segment and _GATEWAY_LIFECYCLE_PATTERN.search(joined_segment):
                return True
            stripped = _ARGV_LIST_PUNCTUATION.sub(" ", joined_segment)
            if stripped != joined_segment and _GATEWAY_LIFECYCLE_PATTERN.search(stripped):
                return True
    # The label may be built in an earlier `;`-segment, so no pass above sees verb + label together.
    # Order-independent launchctl pass (#77083): a shell loop can build the gateway label from a variable
    # defined in an earlier `;`-separated segment (`label=${item%%:*}; launchctl bootout
    # "gui/$uid/$label"`), so neither the same-span regex nor same-segment tokenization sees verb and label
    # together. Check "verb anywhere AND label anywhere" instead.
    return any(_contains_launchctl_gateway_lifecycle(view) for view in views)


# Whole-walk work limits. The per-file cap and depth bound above limit one read, not the walk: a
# command can reference arbitrarily many scripts, and the pure-Python shlex pass (quadratic on a
# giant token) once held the GIL for minutes. These caps bound one whole walk and are charged
# BEFORE any text reaches shlex. Exhaustion fails closed (an unscanned script could hide a
# lifecycle command) and is logged at WARNING so an operator can tell it from a real block. Sizes
# sit well above any legitimate wrapper graph; remote reads are a backend roundtrip each, so they
# get a far tighter cap.
# See #78398.
_MAX_LIFECYCLE_SCAN_BYTES = _MAX_REFERENCED_SCRIPT_BYTES  # 1 MiB across the walk
_MAX_LIFECYCLE_SCAN_LINES = 16384
_MAX_LIFECYCLE_SCAN_LINE_BYTES = 64 * 1024
_MAX_LIFECYCLE_SCAN_PATHS = 1024
_MAX_LIFECYCLE_SCAN_REMOTE_READS = 64


class _LifecycleScanBudget:
    """Shared work budget for one complete referenced-script walk."""

    __slots__ = ("bytes_remaining", "lines_remaining", "paths_remaining", "remote_reads_remaining")

    def __init__(self) -> None:
        # Read the module constants at construction so tests/operators can lower them at runtime.
        self.bytes_remaining = _MAX_LIFECYCLE_SCAN_BYTES
        self.lines_remaining = _MAX_LIFECYCLE_SCAN_LINES
        self.paths_remaining = _MAX_LIFECYCLE_SCAN_PATHS
        self.remote_reads_remaining = _MAX_LIFECYCLE_SCAN_REMOTE_READS

    def charge_text(self, text: str) -> bool:
        """Charge *text* before tokenization; False when it does not fit."""
        # UTF-8 is >= one byte per code point, so the char count is a free lower bound.
        if len(text) > self.bytes_remaining:
            return False
        encoded = len(text.encode("utf-8", errors="replace"))
        if encoded > self.bytes_remaining:
            return False
        lines = text.count("\n") + 1
        if lines > self.lines_remaining:
            return False
        # One huge token is the quadratic shlex case; bound the longest physical line (chars, a
        # lower bound on bytes — tight enough for a DoS bound without a per-line encode).
        longest = max((len(line) for line in text.split("\n")), default=0)
        if longest > _MAX_LIFECYCLE_SCAN_LINE_BYTES:
            return False
        self.bytes_remaining -= encoded
        self.lines_remaining -= lines
        return True

    def charge_path(self) -> bool:
        """Charge one unique referenced path before any local/remote read."""
        if self.paths_remaining <= 0:
            return False
        self.paths_remaining -= 1
        return True

    def charge_remote_read(self) -> bool:
        """Charge one remote-backend read (a network roundtrip each)."""
        if self.remote_reads_remaining <= 0:
            return False
        self.remote_reads_remaining -= 1
        return True


def _capped_read_limit(max_bytes: Optional[int]) -> int:
    """Per-read byte cap: never above the per-file cap, never negative. One definition so local and
    remote reads cannot diverge.

    See #76762, #77703.
    """
    if max_bytes is None:
        return _MAX_REFERENCED_SCRIPT_BYTES
    return min(_MAX_REFERENCED_SCRIPT_BYTES, max(0, int(max_bytes)))


def lifecycle_scan_root_within_budget(text: str) -> bool:
    """Whether *text* may safely enter an optional tokenizer pass (``tools/terminal_tool.py`` gates
    its launchctl pre-scan on this). A FRESH budget, independent of the full guard's walk: the
    pre-scan may pass while the walk later exhausts, still fail-closed — only the friendlier
    launchctl diagnostic is lost. ``False`` is not a verdict: callers must still run the full guard."""
    try:
        return _LifecycleScanBudget().charge_text(text)
    except Exception:
        return False


def _budget_exhausted(what: str, depth: int) -> bool:
    logger.warning(
        "lifecycle guard scan budget exhausted (%s at depth %d); "
        "failing closed — see _MAX_LIFECYCLE_SCAN_* in cron/lifecycle_guard.py",
        what, depth,
    )
    return True


# --- shell tokenization -----------------------------------------------------------------------

def _split_logical_lines(text: str) -> list[str]:
    """Split on newlines outside quotes (a quoted newline is data, not a separator); honors
    escapes."""
    lines: list[str] = []
    current: list[str] = []
    in_single = in_double = escape = False
    for ch in text:
        if escape:
            escape = False
        elif ch == "\\":
            escape = True
        elif ch == "'" and not in_double:
            in_single = not in_single
        elif ch == '"' and not in_single:
            in_double = not in_double
        elif ch == "\n" and not in_single and not in_double:
            lines.append("".join(current))
            current = []
            continue
        current.append(ch)
    if current:
        lines.append("".join(current))
    return lines


def _shlex_tokens(line: str) -> list[str]:
    """POSIX-tokenize one shell line, honoring quotes and `#` comments; raises ValueError."""
    lexer = shlex.shlex(line, posix=True, punctuation_chars=";&|()")
    lexer.whitespace_split = True
    lexer.commenters = "#"
    return list(lexer)


def _split_segments(tokens: list[str], *, keep_controls: bool = False) -> Iterator[list[str]]:
    """Yield non-empty runs of *tokens* between control-operator tokens; with *keep_controls* each
    control token is also yielded as its own segment so the line can be rebuilt in order."""
    segment: list[str] = []
    for token in tokens:
        if token and set(token) <= _CONTROL_CHARS:
            if segment:
                yield segment
                segment = []
            if keep_controls:
                yield [token]
            continue
        segment.append(token)
    if segment:
        yield segment


def _iter_command_segments(command: str) -> Iterator[list[str]]:
    """Yield shell-tokenized command segments per logical line; a line shlex rejects (unbalanced
    quotes) falls back to per-physical-line tokenization. Backslash-newline continuations are
    deleted here, once — callers pass raw text."""
    for line in _split_logical_lines(command.replace("\\\n", "")):
        try:
            tokens = _shlex_tokens(line)
        except ValueError:
            for physical_line in line.splitlines():
                try:
                    yield from _split_segments(_shlex_tokens(physical_line))
                except ValueError:
                    continue
            continue
        yield from _split_segments(tokens)


def _executable_name(token: str) -> str:
    """Command name of an executable token. ``Path(token).name`` is "" for ``.``, ``..`` and ``/``;
    the POSIX dot-source builtin is spelled ``.``, so fall back to the raw token or ``.
    ./helper.sh`` would escape the sourced-script scan."""
    return Path(token).name or token


def _peel_transparent_prefixes(segment: list[str], index: int) -> int:
    """Index of the command a wrapper chain actually executes. Unchanged if not a wrapper; may be
    ``len(segment)`` when a wrapper has no operand — callers must bounds-check."""
    for _ in range(_MAX_PREFIX_PEELS):
        if index >= len(segment):
            return index
        name = _executable_name(segment[index])
        if name not in _TRANSPARENT_COMMAND_PREFIXES:
            return index
        value_options = _TRANSPARENT_PREFIX_VALUE_OPTIONS.get(name, frozenset())
        index += 1
        while index < len(segment):
            token = segment[index]
            if token == "--":
                # POSIX end-of-options: the command starts at the next token.
                index += 1
                break
            if token in value_options:
                index += 2
                continue
            if token.startswith("-") or _ENV_ASSIGNMENT.match(token):
                index += 1
                continue
            break
        for _ in range(_TRANSPARENT_PREFIX_OPERANDS.get(name, 0)):
            if index < len(segment) and not segment[index].startswith("-"):
                index += 1
    return index


def _command_token_index(segment: list[str]) -> Optional[int]:
    """Return the executable token index after simple env assignments."""
    return next((i for i, token in enumerate(segment) if not _ENV_ASSIGNMENT.match(token)), None)


def _executed_command_index(segment: list[str]) -> Optional[int]:
    """Index of the command a segment actually executes (env assignments and wrappers peeled)."""
    index = _command_token_index(segment)
    if index is None:
        return None
    index = _peel_transparent_prefixes(segment, index)
    return index if index < len(segment) else None


def _is_busybox_shell(segment: list[str], index: int) -> bool:
    """True for ``busybox <shell applet> ...`` at *index*."""
    return (
        _executable_name(segment[index]) == "busybox"
        and index + 1 < len(segment)
        and segment[index + 1] in _BUSYBOX_SHELL_APPLETS
    )


def contains_launchctl_submit_command(command: str) -> bool:
    """Detect an executed ``launchctl submit``/``bootstrap``, not quoted text.

    Label-independent by design: a NEW job's label is attacker-chosen, so a neutral name defeats any
    label-anchored regex. Both verbs register a persistent launchd job — never safe in the gateway.

    See #62891.
    """
    for segment in _iter_command_segments(command):
        index = _executed_command_index(segment)
        if index is not None and _executable_name(segment[index]) == "launchctl":
            arguments = segment[index + 1 :]
            if arguments and arguments[0].lower() in {"submit", "bootstrap"}:
                return True
    return False


def _direct_lifecycle_scan(command: str) -> bool:
    """Pure-string direct scans: lifecycle regex + submit.

    Fork deviation: upstream exempts lifecycle text inside data-sink arguments
    (grep/rg/ag/ack/journalctl/sqlite3/psql). Not ported — see the module docstring."""
    return contains_gateway_lifecycle_command(command) or contains_launchctl_submit_command(command)


# --- path handling ----------------------------------------------------------------------------

def _resolve_lenient(path: Path) -> Path:
    """``path.resolve(strict=False)``, falling back to *path* on OSError (unreadable/long),
    ValueError (embedded NUL from decoded binary tokenized as a path), or RuntimeError — never
    crash the guard.

    RuntimeError is the symlink-loop case: on Python <= 3.12 ``resolve(strict=False)`` raises
    ``RuntimeError("Symlink loop ...")`` on a cyclic symlink. Uncaught it aborts the ENTIRE
    referenced-script walk (the top-level guard then falls back to the direct scan only, so a
    sibling `hermes gateway restart` script in the same command slips through). Falling back to the
    unresolved *path* keeps the walk going; the subsequent ``os.open`` on the cyclic path fails
    closed in ``_read_referenced_script`` (ELOOP on POSIX; on Windows, where the open reports a plain
    ENOENT, via ``_unfollowable_link``). See F4 (MUSTPORT-5B r1), M7 (r3)."""
    try:
        return path.resolve(strict=False)
    except (OSError, ValueError, RuntimeError):
        return path


def _is_cloud_placeholder_path(path: Path) -> bool:
    """True for paths inside a macOS FileProvider-backed subtree. ``O_NONBLOCK`` does not make
    regular-file reads non-blocking, so opening an evicted placeholder can wait indefinitely for
    hydration before any command timeout starts: identify the boundary from the path alone."""
    parts = path.parts
    return any(
        parts[index - 1] == "Library" and part in _CLOUD_PLACEHOLDER_MARKERS
        for index, part in enumerate(parts)
        if index
    )


def _on_cloud_path(path: Path) -> bool:
    """Lexical OR resolved cloud check: covers direct cloud paths and local symlinks into one."""
    return _is_cloud_placeholder_path(path) or _is_cloud_placeholder_path(_resolve_lenient(path))


def _expand_candidate_path(candidate: str) -> Optional[Path]:
    """Sanitize a tokenized path candidate at the ingestion boundary. Tokens from shlex-splitting
    arbitrary (possibly binary-decoded) text can carry NUL or junk that each downstream ``Path`` op
    rejects differently (ValueError, RuntimeError when HOME is unset under launchd, OSError); reject
    once here. ``None`` = not a real path, nothing to scan.

    Every OS-facing ``Path`` operation downstream (``expanduser``, ``os.open``, ``resolve``) raises a
    *different* exception for the same junk (``ValueError: embedded null byte``, ``RuntimeError: Could not
    determine home directory`` when HOME is unset under launchd, OSError for over-long paths). Rejecting
    here — once, before any OS call — is the whole-class fix; catching per-syscall was the whack-a-mole that
    produced #76762, #77703, #77780, and #78256.
    """
    if not candidate or "\x00" in candidate:
        return None
    try:
        return Path(candidate).expanduser()
    except (ValueError, RuntimeError, OSError):
        return None


def _resolved_or_nothing(candidate: str, cwd: Optional[str]) -> Iterator[Path]:
    """Yield *candidate* anchored on *cwd* (or the process cwd) when it is a real path."""
    path = _expand_candidate_path(candidate)
    if path is None:
        return
    if not path.is_absolute():
        try:
            path = Path(cwd or Path.cwd()) / path
        except OSError:
            # Path.cwd() can raise when the process cwd was deleted.
            return
    yield path


def _resolve_script_path(script_path: str) -> Optional[Path]:
    """Resolve a cron ``script`` value the way ``cron.scheduler`` does (relative paths live under
    ``<HERMES_HOME>/scripts/``) so the guard scans the file that will actually run."""
    from hermes_constants import get_hermes_home

    raw = _expand_candidate_path(script_path)
    if raw is None:
        return None
    if raw.is_absolute():
        return raw
    try:
        return get_hermes_home() / "scripts" / raw
    except (RuntimeError, OSError):
        # get_hermes_home() falls back to Path.home(), which raises when neither HERMES_HOME nor
        # HOME is resolvable (launchd/systemd) — same ingestion contract: nothing to scan.
        return None


def _resolve_script_directory(script_path: str) -> Optional[str]:
    """Return the directory *script_path* resolves to, handling relative names."""
    try:
        path = _resolve_script_path(script_path)
        if path is not None and path.is_absolute():
            return str(path.parent)
    except Exception:
        pass
    return None


# --- referenced-script discovery --------------------------------------------------------------

def _iter_option_values(segment: list[str], start: int, option: str) -> Iterator[str]:
    """Yield values given to *option*, in both ``--opt v`` and ``--opt=v`` form."""
    prefix = option + "="
    for position in range(start + 1, len(segment)):
        token = segment[position]
        if token == option and position + 1 < len(segment):
            yield segment[position + 1]
        elif token.startswith(prefix):
            yield token[len(prefix):]


def _shell_operand_references(
    arguments: list[str], cwd: Optional[str], *, skip_binary: bool
) -> Iterator[tuple[Path, bool]]:
    """Yield the script operand of a shell invocation; *arguments* follow the shell name."""
    arg_index = 0
    while arg_index < len(arguments):
        argument = arguments[arg_index]
        if argument == "--":
            arg_index += 1
            break
        if argument in _SHELL_COMMAND_FLAGS:
            break
        if argument in _SHELL_OPTIONS_WITH_VALUES:
            arg_index += 2
            continue
        # `+x` style options unset a flag; they are never the script operand.
        if argument.startswith(("-", "+")):
            arg_index += 1
            continue
        break
    if arg_index < len(arguments) and arguments[arg_index] not in _SHELL_COMMAND_FLAGS:
        for path in _resolved_or_nothing(arguments[arg_index], cwd):
            yield path, skip_binary


def _references_at(
    segment: list[str], index: int, cwd: Optional[str]
) -> Iterator[tuple[Path, bool]]:
    """Yield ``(script, skip_binary)`` for each script the token at *index* executes.

    *skip_binary* records the reference position (MUSTPORT-5B r3, M6). True only where the program
    running the file refuses a native executable as a script: a direct-exec path (the kernel loads a
    real binary; bash — which runs terminal commands and cron ``.sh`` jobs — refuses a NUL-first-line
    file on the ENOEXEC fallback) and a ``bash X`` operand. False for ``.``/``source X`` and
    ``sh|dash|ksh|zsh|ash|busybox sh X``, which read the file as text whatever its header.
    Residual: a direct exec whose ENOEXEC fallback is ``/bin/sh`` (a dash parent, or a wrapper's
    ``execvp``) runs a crafted native-header text file; the pre-port guard read no referenced file at
    all, so this never widens it."""
    if index >= len(segment):
        return
    executable = segment[index]
    executable_name = _executable_name(executable)

    if executable_name in {".", "source"}:
        if len(segment) > index + 1:
            for path in _resolved_or_nothing(segment[index + 1], cwd):
                yield path, False
        return

    if executable_name in _SHELL_EXECUTABLES:
        yield from _shell_operand_references(
            segment[index + 1 :], cwd, skip_binary=executable_name in _BINARY_REFUSING_SHELLS
        )
    elif _is_busybox_shell(segment, index):
        yield from _shell_operand_references(segment[index + 2 :], cwd, skip_binary=False)

    # The executable itself when invoked by path — a local `./bash x.sh` or `./ash x.sh` is a script
    # too; a real `/bin/sh` is a native executable and skipped from its header.
    # A bare "/" is pathlib's division operator in Python sources, not an executable; resolving it
    # hits the filesystem root and fails the regular-file check, hard-blocking innocent .py scripts.
    if executable.strip("/") and ("/" in executable or executable.endswith((".sh", ".bash", ".zsh"))):
        for path in _resolved_or_nothing(executable, cwd):
            yield path, True


def _iter_referenced_shell_scripts(
    command: str, *, cwd: Optional[str] = None
) -> Iterator[tuple[Path, bool]]:
    """Yield ``(script, skip_binary)`` for scripts executed directly or through a POSIX shell (see
    ``_references_at``). Each segment is read at the original token AND at the peeled wrapper target
    — additive on purpose: peeling must never REMOVE a reference (a local ``./timeout`` is a script,
    not the coreutils wrapper)."""
    for segment in _iter_command_segments(command):
        index = _command_token_index(segment)
        if index is None:
            continue
        yield from _references_at(segment, index, cwd)
        peeled = _peel_transparent_prefixes(segment, index)
        if peeled != index:
            yield from _references_at(segment, peeled, cwd)


def _iter_shell_command_payloads(command: str) -> Iterator[str]:
    """Yield code passed through ``sh|bash|... -c`` (also ``busybox sh -c``, ``su -c``,
    ``env -S``) for recursive scanning."""
    for segment in _iter_command_segments(command):
        index = _command_token_index(segment)
        if index is None:
            continue
        # Read at the ORIGINAL token: peeling past `su`/`env` would discard the command option.
        for option in _STRING_COMMAND_OPTIONS.get(_executable_name(segment[index]), ()):
            yield from _iter_option_values(segment, index, option)
        index = _executed_command_index(segment)
        if index is None:
            continue
        if _is_busybox_shell(segment, index):
            index += 1
        elif _executable_name(segment[index]) not in _SHELL_EXECUTABLES:
            continue
        arguments = segment[index + 1 :]
        for arg_index, argument in enumerate(arguments[:-1]):
            if argument in _SHELL_COMMAND_FLAGS:
                yield arguments[arg_index + 1]
                break


# --- block-reason attribution -----------------------------------------------------------------

# Why the guard refused, surfaced so a caller (terminal_tool) can render an accurate refusal
# instead of always implying a detected lifecycle command. F2 (MUSTPORT-5B r1). These change no
# rule — a refusal stays a refusal; only the message differs.
_BLOCK_REASON_COMMAND = "lifecycle-command"   # a lifecycle/submit command was detected
_BLOCK_REASON_BUDGET = "scan-budget"          # scan budget exhausted / referenced file oversized
_BLOCK_REASON_DEVICE = "device-or-fifo"       # device/FIFO/socket, or a cyclic/dangling symlink
_BLOCK_REASON_CLOUD = "cloud-path"            # referenced path is a cloud-synced FileProvider path


# --- referenced-script reading ----------------------------------------------------------------

def _is_native_executable_header(header: bytes) -> bool:
    """True when *header* (a file's leading bytes) is a compiled executable: a native magic (ELF /
    PE / Mach-O) AND a NUL before the first newline within the first ``_BINARY_FIRST_LINE_BYTES``.
    Every real ELF, PE and Mach-O header satisfies both.

    Requiring both keeps the skip inside what bash itself refuses as "cannot execute binary file"
    (``check_binary_file``: a NUL in the first line, in every version including macOS /bin/bash
    3.2). A bare magic followed by a newline (``MZ\\nhermes gateway restart``) is text bash runs, so
    it is scanned (F3); a NUL-first-line file without a native magic is scanned too (accepted
    over-blocking). A shebang file never starts with a magic. Only consulted for skip-eligible
    reference positions — see ``_references_at``."""
    if not header.startswith(_NATIVE_EXECUTABLE_MAGICS):
        return False
    return b"\x00" in header[:_BINARY_FIRST_LINE_BYTES].split(b"\n", 1)[0]


def _is_link_metadata(metadata: os.stat_result) -> bool:
    """A POSIX symlink, or a Windows name-surrogate reparse point (symlink / junction)."""
    reparse_tag = getattr(metadata, "st_reparse_tag", 0) or 0
    return stat.S_ISLNK(metadata.st_mode) or bool(reparse_tag & _REPARSE_TAG_NAME_SURROGATE)


def _unfollowable_link(path: Path) -> bool:
    """True when *path* — whose open just failed — is, or sits under, a link the guard cannot follow.

    Windows 11 reports a symlink loop as a plain ENOENT from ``os.open`` and ``os.stat`` (no ELOOP,
    no RuntimeError, no loop-specific winerror) while ``os.lstat`` still succeeds, so this keys on
    the link itself rather than on an error code (M7, MUSTPORT-5B r3):

    * *path* is a link → fail closed (cyclic, dangling, or an unopenable target), except a link that
      resolves to a directory (not a script, #86753 parity);
    * an ancestor is a link ``os.stat`` cannot follow (cyclic or dangling) → fail closed.

    A plain missing path with no such link stays nothing-to-scan. Refusing a dangling link is
    accepted over-blocking."""
    candidates = chain((path,), islice(path.parents, _MAX_LINK_ANCESTORS))
    for position, candidate in enumerate(candidates):
        try:
            if not _is_link_metadata(os.lstat(candidate)):
                continue
        except (OSError, ValueError):
            continue
        try:
            target = os.stat(candidate)
        except (OSError, ValueError):
            return True
        if position == 0 and not stat.S_ISDIR(target.st_mode):
            return True
    return False


def _read_at_most(descriptor: int, data: bytes, size: int) -> bytes:
    """Extend *data* from *descriptor* until it holds *size* bytes or EOF (os.read may return
    short)."""
    while len(data) < size:
        chunk = os.read(descriptor, size - len(data))
        if not chunk:
            break
        data += chunk
    return data


def _read_referenced_script(
    path: Path, *, max_bytes: Optional[int] = None, skip_binary: bool = True
) -> tuple[Optional[str], bool, Optional[str]]:
    """Return ``(text, unsafe, reason)`` using bounded, regular-file-only reads.

    *reason* is one of the ``_BLOCK_REASON_*`` codes when ``unsafe`` is True (so a caller can
    attribute the refusal), else ``None``.

    Shared choke point for every local script read, so the cloud-placeholder refusal lives here: a
    FileProvider path is never opened — not even to check hydration — because an evicted
    placeholder's ``open()`` can hang preflight. Lexical check: direct paths; resolved: symlinks.
    ``max_bytes`` lowers the per-file cap to what the calling walk can still afford.
    ``skip_binary=True`` (direct-exec and ``bash X`` references) returns nothing-to-scan for a native
    executable (``_is_native_executable_header``), classified from a small header BEFORE the size
    check so a multi-MiB interpreter never fails closed (M6). ``skip_binary=False`` (``sh X``,
    ``. X``, cron ``script`` reads) skips nothing: NULs are stripped and the text is scanned.

    See #88052.
    """
    byte_limit = _capped_read_limit(max_bytes)
    if _on_cloud_path(path):
        return None, True, _BLOCK_REASON_CLOUD
    # O_BINARY: in Windows' CRT text mode a read stops at the first 0x1A (Ctrl-Z), hiding the rest of
    # the file from the scan (M5, MUSTPORT-5B r3); the pre-port guard used read_bytes().
    flags = os.O_RDONLY | getattr(os, "O_BINARY", 0) | getattr(os, "O_NONBLOCK", 0)
    try:
        descriptor = os.open(path, flags)
    except ValueError:
        # Embedded NUL in *path* — a binary's decoded bytes tokenized into a bogus script path by
        # the recursion (#77703). Nothing to scan; never crash the guard.
        return None, False, None
    except OSError as exc:
        # A cyclic or dangling symlink is not "missing": fail closed rather than treating it as
        # nothing to scan. On Python <= 3.12 a loop already raised RuntimeError in `_resolve_lenient`
        # (caught there so the walk survives); here the open fails with ELOOP on POSIX, and with a
        # plain ENOENT on Windows, where only the link probe tells it apart. See F4 (r1), M7 (r3).
        if exc.errno == errno.ELOOP or _unfollowable_link(path):
            return None, True, _BLOCK_REASON_DEVICE
        # Otherwise unreadable/missing/over-long — nothing to scan.
        return None, False, None
    try:
        metadata = os.fstat(descriptor)
        # Directories are not scripts. Docker Desktop writes ``fpath=(~/.docker/completions …)`` into
        # ``~/.zshrc``; the walk then treats that dir as a referenced script and used to fail-closed,
        # blocking ``source ~/.zshrc`` (#86753). Devices/sockets stay fail-closed.
        if not stat.S_ISREG(metadata.st_mode):
            # Directories are not scripts (`fpath=(~/.docker/completions …)` in ~/.zshrc must not
            # block `source ~/.zshrc`). Devices/sockets stay fail-closed.
            if stat.S_ISDIR(metadata.st_mode):
                return None, False, None
            return None, True, _BLOCK_REASON_DEVICE
        # Classify from a small header first: a native executable in a skip-eligible position is
        # skipped WITHOUT reading the rest and BEFORE the size check (a real interpreter is MiBs and
        # must not fail closed, M6), and without feeding decoded machine code into the recursion.
        data = _read_at_most(descriptor, b"", _BINARY_SNIFF_BYTES)
        if skip_binary and _is_native_executable_header(data):
            return None, False, None
        # A regular file whose size already exceeds the cap fails closed without reading it (the
        # walk budget can be far below 1 MiB).
        if metadata.st_size > byte_limit:
            return None, True, _BLOCK_REASON_BUDGET
        data = _read_at_most(descriptor, data, byte_limit + 1)
    except OSError:
        return None, False, None
    finally:
        os.close(descriptor)
    # Size check BEFORE NUL stripping: stripping shrinks the buffer and would let an oversized file
    # slip under the threshold past this fail-closed branch.
    if len(data) > byte_limit:
        return None, True, _BLOCK_REASON_BUDGET
    # Deliberately NOT a binary signal (#77927): bash runs a text script straight past an embedded
    # NUL and dash strips them, so NUL-bearing text is stripped and scanned.
    if b"\x00" in data:
        data = data.replace(b"\x00", b"")
    return data.decode("utf-8", errors="replace"), False, None


def _sanitize_remote_script_text(
    text: Optional[str], *, max_bytes: Optional[int] = None
) -> tuple[Optional[str], bool]:
    """Apply the local-read contract to text from an untrusted ``read_remote_script`` callback: NUL
    means binary (nothing to scan, checked first); oversized fails closed. Size compares re-encoded
    *bytes* (matching the ``head -c`` wire bound): a >1 MiB multibyte file truncated at the byte cap
    decodes to fewer chars, and a char count would scan instead of failing.

    The recursion boundary must not trust its callbacks: any backend (SSH, Modal, Daytona, or a future one)
    can hand back raw binary bytes decoded as text, or arbitrarily large output. Enforced here rather than
    inside each callback so the guarantee holds for every callback, not just the ones we hardened. See
    #76762, #77703.
    """
    if not text or "\x00" in text:
        return None, False
    byte_limit = _capped_read_limit(max_bytes)
    if len(text) > byte_limit:
        return None, True  # chars <= bytes: over the cap without encoding
    if len(text.encode("utf-8", errors="replace")) > byte_limit:
        return None, True
    return text, False


def _read_script_for_scanning(script_path: str) -> str:
    """Read a cron script with the bounded scanner. Non-regular/oversized inputs fail closed via a
    lifecycle-shaped sentinel; missing/unreadable paths stay empty so scheduler validation reports
    them. Nothing is skipped as binary (fork deviation): the scheduler hands any script to bash or
    python, dash/busybox run a native-header text file, and the pre-port guard decoded every cron
    script in full."""
    resolved = _resolve_script_path(script_path)
    if resolved is None:
        return ""
    script_text, unsafe, _reason = _read_referenced_script(resolved, skip_binary=False)
    if unsafe:
        return "hermes gateway restart"
    return script_text or ""


# --- recursive walk ---------------------------------------------------------------------------

def _contains_unsafe_gateway_action(
    command: str, *, cwd: Optional[str], depth: int, visited: dict[Path, set[bool]],
    budget: _LifecycleScanBudget,
    read_remote_script: Optional[_ReadRemoteScriptFn] = None,
    reason_out: Optional[list[str]] = None,
) -> bool:
    # *reason_out*, when supplied, receives the FIRST block reason (a ``_BLOCK_REASON_*`` code) so a
    # caller can render an accurate refusal. It is threaded through the recursion so a reason set at
    # any depth propagates to the root. See F2 (MUSTPORT-5B r1).
    # *visited* maps each resolved referenced path to the ``skip_binary`` positions already read.
    def _block(reason: str) -> bool:
        if reason_out is not None and not reason_out:
            reason_out.append(reason)
        return True

    # Charge BEFORE _direct_lifecycle_scan: every scan in it tokenizes with shlex.
    if not budget.charge_text(command):
        _budget_exhausted("text", depth)
        return _block(_BLOCK_REASON_BUDGET)
    if _direct_lifecycle_scan(command):
        return _block(_BLOCK_REASON_COMMAND)
    if depth >= _MAX_REFERENCED_SCRIPT_DEPTH:
        return _block(_BLOCK_REASON_COMMAND)

    def recurse(text: str, cwd: Optional[str]) -> bool:
        return _contains_unsafe_gateway_action(
            text, cwd=cwd, depth=depth + 1, visited=visited, budget=budget,
            read_remote_script=read_remote_script, reason_out=reason_out,
        )

    for payload in _iter_shell_command_payloads(command):
        if recurse(payload, cwd):
            return True

    for script_path, skip_binary in _iter_referenced_shell_scripts(command, cwd=cwd):
        # Do not touch a FileProvider path even to discover whether the file is hydrated.
        if _on_cloud_path(script_path):
            return _block(_BLOCK_REASON_CLOUD)
        resolved = _resolve_lenient(script_path)
        seen_positions = visited.get(resolved)
        if seen_positions is None:
            if not budget.charge_path():
                _budget_exhausted("paths", depth)
                return _block(_BLOCK_REASON_BUDGET)
            seen_positions = visited[resolved] = set()
        elif False in seen_positions or skip_binary in seen_positions:
            continue
        # Otherwise every earlier read was skip-eligible (direct exec / `bash X`) and may have
        # skipped the file as a native executable, which does not cover this `sh X` / `. X`
        # reference: read it again. At most one re-read per unique path, so the path budget is
        # charged once.
        seen_positions.add(skip_binary)
        # Never read more than the walk can still afford to tokenize; a file larger than the
        # remainder fails closed exactly like an oversized one. The skip is scoped by position (M6):
        # a real executable run by path (`/usr/bin/python3 -c ...`) is not read, while `sh ./x`,
        # `. ./x` and every non-native-header file are scanned (F3).
        script_text, unsafe, reason = _read_referenced_script(
            script_path, max_bytes=budget.bytes_remaining, skip_binary=skip_binary
        )
        if unsafe:
            return _block(reason or _BLOCK_REASON_COMMAND)
        if script_text is None and read_remote_script is not None:
            # Local path missing; the remote backend's output crosses the same trust boundary as a
            # local read — sanitize identically (binary skip + size fail-closed).
            if not budget.charge_remote_read():
                _budget_exhausted("remote reads", depth)
                return _block(_BLOCK_REASON_BUDGET)
            script_text, unsafe = _sanitize_remote_script_text(
                read_remote_script(str(script_path)), max_bytes=budget.bytes_remaining
            )
            if unsafe:
                return _block(_BLOCK_REASON_BUDGET)
        if not script_text:
            continue
        # Relative references inside a script resolve against that script's directory, not the cwd.
        if recurse(script_text, _resolve_script_directory(str(resolved)) or cwd):
            return True
    return False


def contains_gateway_lifecycle_command_or_referenced_script(
    command: str, *, cwd: Optional[str] = None,
    read_remote_script: Optional[_ReadRemoteScriptFn] = None,
) -> bool:
    """Detect lifecycle/submit commands, including bounded nested scripts.

    Total by construction: never raises. Direct scans are pure string ops; the referenced-script
    walk (filesystem, remote backends, shlex on decoded bytes) is best-effort defense-in-depth — an
    unexpected failure is logged and treated as "walk found nothing".

    This is the contract #76762 established ("a guarded path must never crash the guard") enforced at the
    boundary instead of per-syscall: a guard crash propagates out of ``tools/terminal_tool.py`` and breaks
    every terminal command until the gateway restarts (#77780, #78256), which is strictly worse than either
    verdict.
    """
    return gateway_lifecycle_block_reason(
        command, cwd=cwd, read_remote_script=read_remote_script
    ) is not None


def gateway_lifecycle_block_reason(
    command: str, *, cwd: Optional[str] = None,
    read_remote_script: Optional[_ReadRemoteScriptFn] = None,
) -> Optional[str]:
    """Same verdict as ``contains_gateway_lifecycle_command_or_referenced_script`` but returns WHY.

    ``None`` when the command is allowed; otherwise a ``_BLOCK_REASON_*`` code so a caller can render
    an accurate refusal (a detected lifecycle command vs. a fail-closed scan-budget / device-FIFO /
    cloud-path refusal) instead of always implying a detected lifecycle command. See F2
    (MUSTPORT-5B r1). Total by construction: never raises (same #76762 contract as the bool wrapper).
    """
    reasons: list[str] = []
    try:
        blocked = _contains_unsafe_gateway_action(
            command, cwd=cwd, depth=0, visited={}, budget=_LifecycleScanBudget(),
            read_remote_script=read_remote_script, reason_out=reasons,
        )
    except Exception:
        logger.warning(
            "lifecycle guard referenced-script walk failed; "
            "falling back to direct-scan verdict",
            exc_info=True,
        )
        return _BLOCK_REASON_COMMAND if _direct_lifecycle_scan(command) else None
    if not blocked:
        return None
    return reasons[0] if reasons else _BLOCK_REASON_COMMAND


def check_gateway_lifecycle(prompt: Optional[str], script: Optional[str] = None) -> None:
    """Raise ``GatewayLifecycleBlocked`` if *prompt* or *script* contains a gateway-lifecycle
    command. The script is read from disk and concatenated with the prompt so a command cannot slip
    through by being split across the two. Callers let the ``ValueError``-shaped exception
    propagate."""
    combined = prompt or ""
    python_script = False
    if script:
        resolved_script = _resolve_script_path(script)
        # Attribute the refusal correctly: not a lifecycle command, but a cloud path never opened.
        if resolved_script is not None and _on_cloud_path(resolved_script):
            raise GatewayLifecycleBlocked(
                # Attribute the refusal correctly: the script is not known to contain a lifecycle command —
                # it lives on a cloud-synced FileProvider path (iCloud Drive / ~/Library/CloudStorage) that
                # the guard refuses to open because an evicted placeholder can hang preflight indefinitely
                # (#88052). Fail closed with the real reason instead of implying a dangerous lifecycle
                # command.
                "Blocked: the cron script lives on a cloud-synced path "
                "(iCloud Drive / ~/Library/CloudStorage). Opening an "
                "evicted FileProvider placeholder can hang the guard's "
                "preflight scan indefinitely, so it is refused without "
                "being read. Move the script to a local, non-cloud path "
                "(e.g. ~/.hermes/scripts/) and recreate the job."
            )
        python_script = resolved_script is not None and resolved_script.suffix == ".py"
        script_text = _read_script_for_scanning(script)
        if script_text:
            combined = f"{combined}\n{script_text}"

    if python_script:
        # Python runs via the interpreter, never a POSIX shell, and the shell reference walk is a
        # false-positive generator on Python sources (pathlib "/" resolves to the filesystem root).
        # The regex still scans the full text; non-regular/oversized files fail closed (sentinel).
        # The direct scan tokenizes with shlex, so it is charged against the walk budget first.
        # The direct command regex below still scans the full text, so a literal `hermes gateway restart`
        # embedded in a .py script is still blocked. See #77131, #78398.
        if not _LifecycleScanBudget().charge_text(combined):
            unsafe = _budget_exhausted("text", 0)
        else:
            unsafe = contains_gateway_lifecycle_command(combined)
    else:
        unsafe = contains_gateway_lifecycle_command_or_referenced_script(
            combined, cwd=_resolve_script_directory(script) if script else None
        )
    if unsafe:
        raise GatewayLifecycleBlocked(
            "Blocked: cron job contains a gateway lifecycle command or persistent "
            "launchctl submit operation. This is blocked to prevent agent-driven "
            "SIGTERM-respawn loops under launchd/systemd supervision "
            "(#30719). Run `hermes gateway restart` from a shell outside "
            "the running gateway instead."
        )
