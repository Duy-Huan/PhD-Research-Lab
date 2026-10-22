# UI refinement and regression

The existing left sidebar, central chat composer and right contextual drawer remain in place.

## Projects and conversations

Use **Dự án & hội thoại / Projects & conversations** to browse conversations grouped under registered research projects in the right drawer. Expand a project to load its conversation summaries. Opening a conversation explicitly activates its project first. The **＋** button beside the project browser and **Tạo dự án / Create project** inside the drawer open the existing project creation flow.

Conversation history groups use local calendar days, followed by localized month/year headings. Messages show full localized date/time and conversations show their last update in the tooltip.

**Ghim tin nhắn / Pin message** is separate from **Ghim vào kết quả / Pin to results**. User and assistant messages can be pinned. The header pin button opens the pinned-message drawer; it supports jumping to a message and unpinning. Pins persist in the session's project. An in-flight pin action blocks duplicate clicks and cannot repaint another chat after navigation.

## Theme packages

Open **Cài đặt → Giao diện & ngôn ngữ / Settings → Appearance & language**. Apply Lab Midnight or Lab Forest, or install a local JSON theme. Installed packages can be selected from the theme dropdown and removed from their cards. They are stored in this browser; a removed selected package falls back to the system theme.

PhD Lab packages have `id`, `name`, `base` (`light` or `dark`) and `colors`. See [the sample package](themes/ocean.json). Hex colors support 3, 4, 6 or 8 digits. Each package is limited to 64 KB; up to 30 custom packages can be installed. Invalid packages report an error without replacing the selected theme.

VS Code color-theme JSON files with `name`, `type` and `colors` are also supported. Mappings include editor background/foreground, sidebar colors, panel background/border, input background, descriptions, focus border, button colors and selection background. Token colors, arbitrary CSS, scripts, external URLs, `include` files and executable VSIX extensions are not imported.

## PDF names

New Library uploads, PDFs dropped directly into the references directory, and Library **save/download** actions share this convention:

```text
YEAR_Author_Title_SHA256-first12.pdf
2024_Nguyen_A-Study-of-Image-Restoration_012345abcdef.pdf
```

The year uses `nd` when unknown; author uses `Unknown` when unavailable. Metadata comes from the retrieved source or the PDF's local metadata/first pages. The title and author are converted to safe ASCII filename components, with bounded length. No model or network call is needed for naming. Uploads preserve `original_name`; identical content is reused and different content with the same original filename is kept separately. A metadata-only retrieved record is upgraded using the same convention when its PDF becomes available.

Existing curated records retain their filenames, citation keys and links. Scientific Knowledge Base content-addressed objects retain their hashes. Updating bibliographic metadata does not rename an already registered file. Malformed files dropped directly into references remain visible as excluded error records rather than preventing the whole Library from loading.

## Verification

```powershell
node tests/frontend/run.js
.venv/Scripts/python -B tools/run_tests.py
```

The frontend command enforces **100% lines, branches and functions** across every first-party JavaScript file in `frontend/assets/`, including the first-paint initialization script. It fails for missing script coverage or an unexecuted/unknown branch. There are no ignore annotations or omitted application modules. Vendor libraries and CSS are outside V8's JavaScript coverage scope; real-browser checks cover responsive geometry, keyboard focus, themes and reduced motion.

For repeatable visual checks on isolated sample data:

```powershell
.venv/Scripts/python -B tools/demo_server.py 8799
# In a second terminal:
node tools/ui_visual_check.js http://127.0.0.1:8799 artifacts/ui-refinement
```

The demo uses a fake model and temporary project data. The visual checker changes only this demo's language, pins and browser-local theme. It must be pointed at the isolated demo, not a live research project.

See [the audit](ui-refinement-audit.md) and [validation evidence](../artifacts/ui-refinement/validation.md).
