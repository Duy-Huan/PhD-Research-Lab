# Frontend v5.2 audit

Actual stack: vanilla JavaScript, `PL` global, DOM factory and fetch wrappers in core.js; hash routes in main.js; persistent chat composer and slash palette in chat.js; resizable/responsive existing panel in panels.js/app.css. No React or frontend build dependency. GitHub plugins provide Markdown skills, not executable UI components. Tests use the actual HTML/scripts with jsdom.

| Existing | Reuse | Addition |
|---|---|---|
| Project switcher / chat sessions | Existing registration and routes | Topic selector binding a separate conversation per topic |
| Library drawer / internet search | Preserve curated library | Topic corpus explorer/inbox, pagination, tier/source/year/OA filters |
| Slash palette | Existing skill catalog | Typed deterministic UI contributions returned with catalog; intercept before chat POST |
| Selected attachment refs | Existing overrides.sources + trust compiler | Stable paper/artifact refs, removable chips, explicit AI action |
| Settings / providers | Keep unchanged | Optional integrations report availability; no dependency auto-install |
| Live transport | Existing bus/polling | Real persisted job/sync status, no simulated counters |

Wireframe: sidebar project → compact Topic selector → chat and composer; Research button opens existing contextual drawer. Drawer modes: Papers / Topics / Workspaces / Jobs. Selecting a paper changes chips only. Compare/Review explicitly fills the chat input. Search, sync and scheduling call deterministic API actions. Narrow screens retain existing closeable panel behavior. One action dispatcher, whitelisted view keys, no plugin JavaScript evaluation.

Migration: additive assets, API and store. Existing chat history, library, settings and provider contracts retained. Topic context uses a separate bound conversation; topic switches clear pending selections and attachments. Corpus ingestion never opts papers into the legacy bibliography without an explicit approval/export action.
