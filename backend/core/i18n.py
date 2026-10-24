"""Interface language of the texts the app writes itself (help, status, run notices): Settings → Appearance → Language."""
from __future__ import annotations


def lang() -> str:
    from backend.core.config import load_config
    return "en" if (load_config().get("ui") or {}).get("language") == "en" else "vi"


def ai_lang() -> str:
    from backend.core.config import load_config
    return (load_config().get("ui") or {}).get("ai_language") or "auto"


def L(vi: str, en: str) -> str:
    """The Vietnamese or English variant of one message, by the researcher's interface language."""
    return en if lang() == "en" else vi
