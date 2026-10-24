# CLI Provider Non-Destructive Inspection Results
**Date:** 20261024T031029Z | **Commit:** `de9a764ac7451d006fc85e828e546db85985c75f`

| Provider | Installed | Path | Auth Status | Login Forwarding CMD | Sandboxing |
| :--- | :--- | :--- | :--- | :--- | :--- |
| `codex` | True | `C:\Users\win\AppData\Roaming\npm\codex.CMD` | **unauthenticated** | `codex login` | Enforced |
| `claude_code` | False | `N/A` | **unauthenticated** | `claude login` | Enforced |
| `antigravity` | False | `N/A` | **unauthenticated** | `agy auth login` | Enforced |
| `gemini_cli` | False | `N/A` | **unauthenticated** | `gemini login` | Enforced |

## Policy Enforcement
- All CLI provider invocations are wrapped in strict subprocess isolation.
- If a provider is unauthenticated, PhD Lab forwards the researcher to run the specified `login_cmd`.
- No mock responses are injected into CLI flows.