# Telegram existing-path 0B PREP

**Slice:** `TELEGRAM_EXISTING_PATH_0B_PREP`  
**Status:** preparation only. `R5_GATE = CLOSED`.  
**Activation:** do **not** run this checklist until a human opens `TELEGRAM_EXISTING_PATH_0C_ACTIVATE`.

The existing Telegram bot identity stays on Railway Operator Hermes during 0B.
The target after a later explicit activation is the dedicated Developer
profile `telegram-ops` (same BotFather bot, same token, same allowed human).
Developer Hermes and Operator Hermes remain separate runtimes.

```text
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
forbidden. Activation remains a separate human slice.

Telegram never resolves to the default Developer / Desktop profile
(`approvals: mode: off` stays local-only). After Developer Hermes reload,
official Desktop Bot Mode lists `telegram-ops` under SESSIONS | BOTS because
upstream `Bot = profile`. No custom Bot UI.

Local availability: Telegram is reachable only while the Windows host, Docker
Desktop, the Developer container, and the `telegram-ops` gateway are up.
Railway Operator remains the 24/7 concept until a human moves the token.

Rollback is token/config based: stop the local gateway, put the same token
back on Railway, restart the Operator poller. No BotFather action.

## TELEGRAM_EXISTING_PATH_0C_ACTIVATE

Do **not** execute this in 0B.

1. Verify the Developer `telegram-ops` profile, config, and focused tests.
2. Verify the local Developer gateway is **not** polling the live token yet
   (`TOKEN_CLASS` is `MISSING` or `SYNTHETIC`; `LIVE_POLLING = NO`).
3. Record the current Railway Telegram state (start command, token present,
   allowed-user count only, allow-all unset, long polling, no webhook).
4. Stop / remove the Telegram token from the Railway poller.
5. Confirm the old poller has stopped (`getUpdates` is no longer held).
6. Place the **same** token and the **same** allowed numeric user ID into
   the local `telegram-ops` profile `.env` (`TELEGRAM_BOT_TOKEN`,
   `TELEGRAM_ALLOWED_USERS`). Do not enable allow-all. Do not set a webhook.
7. Start the local gateway (`launch.py telegram-up`).
8. Confirm polling is healthy.
9. Send one real message from the existing Telegram chat.
10. Verify the session is `telegram-ops`, not the Desktop default profile.
11. Verify read-first repository answers work (Repo A and Repo B).
12. Verify forbidden tools and `/yolo` are denied.
13. Test one manual approval flow only if a benign approval-capable action
    exists.
14. Document rollback (stop local gateway; restore Railway token; restart
    Operator poller).
15. Human decides whether to keep the local cutover.

Human confirmation still required before 0C if live Railway state could not
be read safely in 0B: start command, token present, allowed-user policy
shape, `GATEWAY_ALLOW_ALL_USERS` / `TELEGRAM_ALLOW_ALL_USERS` unset, capability
tier, long polling, webhook absent.
