# Real provider validation

Canonical records: [provider CLI events](../qa/evidence/2026-10-25/providers-cli/report.json), [Spark benchmark](../qa/evidence/2026-10-25/native-vs-wrapped-serial/report.json).

| Path | Measured outcome | Qualification limit |
|---|---|---|
| LM Studio `spark-x2.5-4b` | Real inference through native API, wrapped chat, browser and CLI; final bounded comparison 6/6 native and 6/6 wrapped | Earlier two model-unloaded request failures retained; no sustained-load certification |
| Codex installed CLI | Real `OK` reply, exit 0, about 16.5 s | Vendor-default model; no blanket model capability claim |
| Antigravity installed CLI | Real `OK` reply, exit 0, about 8.2 s | Vendor-default model; do not infer requested Gemini version from subscription availability |
| Claude Code | Request attempted; weekly quota error | BLOCKED, not passing inference |
| Gemini CLI | Request attempted; sign-in method absent | BLOCKED until actual authentication |
| Cloud API providers | No configured API keys in local configuration | BLOCKED; CLI subscriptions do not supply API credentials |
| Ollama | Local service not listening during discovery | BLOCKED |
| Research engine adapters | Offline tests and selected native missions | Complete live Feynman/OpenScience/OpenCode/PaperOrchestra qualification remains open |

Forward/connect actions resolve installed executable paths. A missing executable returns unavailable; it cannot fall back to a vendor website. Windows process quoting is tested as a unit boundary; every vendor's visible interactive window still needs manual qualification.
