# Telegram existing-path 0B PREP

**Slice:** `TELEGRAM_EXISTING_PATH_0B_PREP`  
**Status:** preparation complete. `R5_GATE = CLOSED`.  
**Activation:** live start is `TELEGRAM_DEVELOPER_SECOND_BOT_0C_ACTIVATE`.

Architecture after 0C: **two Telegram identities**. 0B prepared the
dedicated Developer profile. It does **not** move the Railway Operator
token. The later 0C slice creates or uses a **second** BotFather bot for
local Developer Hermes.

```text
PROFILE_NAME                     = telegram-ops
DISPLAY_NAME                     = Developer Remote
PROFILE_IS_OS_SANDBOX            = NO
TELEGRAM_PROFILE_IS_DEDICATED    = YES
APPROVALS_MODE                   = manual
CRON_MODE                        = deny
TRANSPORT                        = LONG_POLLING
PUBLIC_INBOUND_PORT              = NO
EGRESS_CLASS                     = MESSAGING_PLATFORM
EGRESS_ALLOWED_HOSTS             = api.telegram.org
MEDIA_DOWNLOAD                   = OUT_OF_SCOPE
TOKEN_STORAGE                    = /opt/data/profiles/telegram-ops/.env
PROFILE_POLICY                   = READ_FIRST_WITH_APPROVAL_GATED_WRITES
ARCHITECTURE                     = TWO_BOT
```

`telegram-ops` is a capability/configuration boundary, not an OS or container
sandbox. The R5 outer container remains the real isolation boundary. This
profile shares the Developer container, uid, mounts, egress broker, and
model provider boundary. Safety is the explicit tool allowlist, the
profile-local write-approval plugin, slash-command tiering, numeric Telegram
allowlist, and that outer sandbox.

Telegram starts READ-FIRST, with write/patch callable only behind explicit
manual approval. Upstream `file` is atomic, so `write_file` and `patch`
appear in the callable schema with `read_file` / `search_files`. That is
not structurally or cryptographically read-only.
`approvals.mode = manual` alone does not gate ordinary file writes; the
seeded `telegram-ops-write-approval` plugin escalates write/patch to the
upstream human approval gate. Writes cannot execute unattended. `/yolo`
cannot bypass the approval posture. Terminal, Git commit, Git push,
browser, Computer Use, cron, and `/yolo` stay unavailable. Repository Git
status via terminal is out of scope because exposing `terminal` is
forbidden.

Telegram never resolves to the default Developer / Desktop profile
(`approvals: mode: off` stays local-only). After Developer Hermes reload,
official Desktop Bot Mode lists `telegram-ops` under SESSIONS | BOTS because
upstream `Bot = profile`. No custom Bot UI.

Local availability: Telegram is reachable only while the Windows host, Docker
Desktop, the Developer container, and the `telegram-ops` gateway are up.
Railway Operator remains the 24/7 Operator Telegram identity.

Ordinary `telegram-up` refuses LIVE_SHAPED tokens. Live Developer polling
requires `telegram-activate`. See
[`hermes_r5_telegram_developer_0c_v1.md`](hermes_r5_telegram_developer_0c_v1.md).

## Superseded same-token cutover

The original 0B note described moving the **same** Railway token onto
Developer Hermes. That cutover is **withdrawn**. Operator keeps its
token. Developer uses a second bot. Do not remove or alter Railway
`TELEGRAM_BOT_TOKEN` / `TELEGRAM_ALLOWED_USERS` for this path.
