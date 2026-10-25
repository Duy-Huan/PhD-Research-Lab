# Agent client compatibility

All clients use `python scripts/verify.py` and the same AGENTS/SOP/contract policy. A shell command being portable is different from a native browser integration having been exercised inside each client.

| Client | Registration / entrypoint | Verified in this task |
|---|---|---|
| Codex | root AGENTS.md, `.agents/skills/verify/SKILL.md`, project Playwright MCP config | Actual Codex inference and separate MCP handshake/navigation were recorded in earlier task evidence; direct client-driven new Browser Use journey NOT RUN |
| Claude Code | CLAUDE.md -> AGENTS/SOP, `.claude/commands/verify.md` | Installed CLI detected; earlier inference blocked by weekly quota; new native browser integration NOT RUN |
| Antigravity CLI | root AGENTS.md/GEMINI.md and `.agents/skills/verify/SKILL.md` | Installed agy 1.4.7 help inspected; earlier actual inference returned OK; new browser journey from agy NOT RUN |
| Gemini CLI | GEMINI.md and `.gemini/commands/verify.toml` | Earlier authentication expired; no successful inference/browser qualification claimed |

Official Antigravity documentation confirms workspace AGENTS.md/GEMINI.md and `.agents/skills/<name>/SKILL.md` discovery and slash-command conversion; this was checked, not assumed from Codex behavior: [rules](https://antigravity.google/docs/rules/), [CLI migration](https://antigravity.google/docs/cli/gcli-migration/), [skills](https://www.antigravity.google/docs/skills?tab=ide). Codex's progressive skill discovery is described in [OpenAI's skills workflow article](https://developers.openai.com/blog/skills-agents-sdk).

These files are ready for subsequent client sessions to discover. Do not assert the currently running IDE/client has hot-reloaded registrations, that all clients have identical browser tools or that model listing proves actual inference. Native app launch must use installed binaries inside the authorized project-data containment; never replace it with a vendor website.
