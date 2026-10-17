# Changelog

## v1.2.0 — 2026-10-17
- Multi-provider cloud AI: Anthropic Claude, OpenAI ChatGPT, Google Gemini, xAI Grok, DeepSeek, Mistral, Alibaba Qwen, Moonshot Kimi, Cohere, Perplexity, Groq, OpenRouter, Together AI, and any custom OpenAI-compatible endpoint.
- Per-provider API key, model (with live "List models"), base URL, and connection test.
- Per-agent engine selector: Default cloud / Local (LM Studio) / specific provider.
- Automatic handling of provider parameter differences (`max_completion_tokens`, fixed temperature).
- v1.0/v1.1 settings are migrated automatically (Claude key and model kept).

## v1.1.0 — 2026-10-17
- Robust launcher `start.py` (checks Python, installs missing packages, frees port, opens browser when ready).
- Works under Windows 11 Smart App Control: pure-Python PDF engine (pypdf) fallback and pure-Python server stack.

## v1.0.0 — 2026-10-17
- Initial release: Lit2Plan, Experimental Design, PDF library + Data Chat + multi-agent LaTeX writer, Masterclass, `latex.zip` export.
