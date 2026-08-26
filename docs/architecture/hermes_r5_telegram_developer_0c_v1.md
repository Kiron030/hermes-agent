# Telegram Developer second-bot 0C ACTIVATE

**Slice:** `TELEGRAM_DEVELOPER_SECOND_BOT_0C_ACTIVATE`  
**Status:** human smoke complete. `R5_GATE = CLOSED`.  
**Architecture:** `TWO_BOT`

Operator Hermes keeps the existing Railway Telegram bot. Developer Hermes
uses a **second** BotFather identity on the dedicated `telegram-ops`
profile (display: **Developer Remote**). The two tokens must differ.
This slice does not rename the internal profile: the volume, plugin,
Desktop Bot listing, and tests already use `telegram-ops`. Display,
SOUL, and docs identify it as Developer Remote.

```text
OPERATOR_TELEGRAM_CHANGED        = NO
RAILWAY_CHANGED                  = NO
DEVELOPER_PROFILE_NAME           = telegram-ops
PROFILE_RENAME_PERFORMED         = NO
DISPLAY_NAME                     = Developer Remote
TOKEN_STORAGE                    = /opt/data/profiles/telegram-ops/.env
TRANSPORT                        = LONG_POLLING
EGRESS_CLASS                     = MESSAGING_PLATFORM
PUBLIC_INBOUND_PORT              = NO
DEFAULT_DENY                     = YES
DM_ONLY                          = YES
GROUPS                           = NO
```

## Human secret step

Never paste the Developer token into Cursor chat. Never commit it.
Never reuse the Operator Railway token.

If the second bot does not exist yet:

1. Open BotFather in Telegram.
2. `/newbot` and choose a name/username that is clearly Developer, not Operator.
3. Copy the new token locally. Do not send it to chat.
4. Confirm your numeric Telegram user id (`@userinfobot` or similar).
   The same numeric human as Operator is allowed.

Then, in a local PowerShell **outside Cursor chat**:

```powershell
.\scripts\r5_developer_hermes\container\launch-developer-hermes.ps1 -Mode telegram-activate
```

Type `ACTIVATE-DEVELOPER-TELEGRAM`. Enter the new token (hidden) and
one numeric user id. Ordinary `telegram-up` still refuses LIVE_SHAPED
tokens.

## Availability

Operator bot: 24/7 on Railway Operator Hermes.  
Developer bot: only while the Windows host, Docker Desktop, Developer
Hermes, the Developer Telegram gateway, and the model provider are up.
Do not move Developer Hermes to Railway.

The Docker-native primitive is `hermes -p telegram-ops gateway run`
as uid 10000 (`hermes`). Do not use `gateway start` (systemd/launchd)
and do not run the gateway as root. Status requires a live
`telegram-ops` `gateway run` process; a stored token or `hermes serve`
is not polling evidence. `telegram-down` stops that process only.

## Human smoke evidence

Observed on the live Developer Remote bot (`telegram-ops`). No tokens,
numeric user ids, chat ids, or secret-bearing logs are recorded here.

```text
HUMAN_RUNTIME_SMOKE                    = PASS
HUMAN_PIN_SMOKE                        = PASS
HUMAN_REPO_B_SMOKE                     = PASS
HUMAN_YOLO_SMOKE                       = PASS
HUMAN_DENY_SMOKE                       = PASS
DENY_PRODUCES_ZERO_MUTATION            = PASS
HUMAN_APPROVE_ONCE_SMOKE               = PASS
APPROVE_EXECUTES_EXACT_MUTATION        = PASS
TWO_BOT_COEXISTENCE                    = PASS
YOLO_ENABLED                           = NO
```

Runtime/read checks used the existing workspace mounts only. Deny left
`.telegram-deny-smoke-2.txt` absent. Approve Once created only the
requested approve fixture with the exact requested contents; that
fixture was deleted after verification. Operator Telegram stayed on
Railway. No 409 polling conflict was observed.
