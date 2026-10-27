# Language audit

The CLI now reads the shared `ui_language` configuration, supports `/language en|vi`, `/language ai auto|en|vi`, and exposes eight `/settings` groups. The real CLI test switches EN/VI, reads persisted configuration and sends a real Spark chat. Unit/integration cases cover invalid locale/JSON, settings updates and redacted secret setters.

This is not 100% locale parity. Visual 3D inspection in EN found Vietnamese agent subtitles/object labels. Some legacy CLI action/reasoning labels and wider UI strings remain untranslated. Generated model text follows its separate AI-language setting; translating UI labels must not rewrite user text, source evidence or model answers.

Next work: enumerate translation keys and hardcoded user-facing labels per surface, assert EN and VI behavior, test cross-client updates and complete manual terminal rendering. Do not mark language coverage complete from the presence of a toggle alone.
