# Design System & UI Specifications — PhD Research Lab OS

## 1. Principles
- **Chat-First Research OS**: Clean, modern interface inspired by ChatGPT simplicity, but purpose-built for scientific research workflows (Missions, Evidence, DAG, 3D University Lab).
- **Icon-First Visual Hierarchy**: Prioritize recognizable icons with clean tooltip labels over cluttered text.
- **Biophilic & Green Campus Aesthetic**: 3D University Lab uses natural green accents (`#22c55e`, `#15803d`, `#eef6f0`), light scientific palettes, and high-contrast readable text.

## 2. Spacing Rhythm & Scale
Base rhythm is 4px / 8px:
- `p-1 / gap-1`: 4px
- `p-2 / gap-2`: 8px
- `p-3 / gap-3`: 12px
- `p-4 / gap-4`: 16px
- `p-6 / gap-6`: 24px
- `p-8 / gap-8`: 32px

## 3. Typography
- **Font Stack**: Inter, system-ui, -apple-system, sans-serif.
- **Math Engine**: KaTeX (embedded math font family `KaTeX_Main`, `KaTeX_Math`).
- **Monospace**: JetBrains Mono, Fira Code, Consolas (code snippets, BibTeX, hashes).
- **Scale**:
  - Micro / Badges: `text-xs` (11px / 12px)
  - Small / UI Labels: `text-sm` (13px / 14px)
  - Body: `text-base` (15px / 16px)
  - Subheadings: `text-lg` (18px)
  - Section Headings: `text-xl` (20px)
  - Page Titles: `text-2xl` (24px)

## 4. Color Palette & Contrast (WCAG 2.2 AA)
- **Primary Accent**: Emerald / Teal (`#059669` / `#10b981`), contrast ratio > 4.8:1 against white/neutral backgrounds.
- **Dark Neutral Background**: Slate-900 (`#0f172a`), Slate-800 (`#1e293b`), Slate-700 (`#334155`).
- **Light Neutral Background**: White (`#ffffff`), Slate-50 (`#f8fafc`), Slate-100 (`#f1f5f9`).
- **Semantic Statuses**:
  - Success / Running: Emerald-600 (`#16a34a`)
  - Warning / Awaiting Approval: Amber-500 (`#f59e0b`)
  - Error / Failed / Conflict: Rose-500 (`#f43f5e`)
  - Info / Queued: Sky-500 (`#0ea5e9`)

## 5. Responsive Breakpoints & Scaling
- Mobile: `360px` - `767px` (Sidebar collapses to overlay drawer, full-width chat stage).
- Tablet: `768px` - `1023px` (Sidebar icon-rail mode, contextual drawer toggles on demand).
- Desktop: `1024px` - `1439px` (Expanded sidebar, main stage, resizable contextual drawer).
- Ultra-Wide / 4K: `1440px+` (3D Lab full-stage immersive mode, side-by-side OpenCode and DAG).
- User Zoom Scaling: Integrated scale shortcuts (`Ctrl` + `+`, `Ctrl` + `-`, `Ctrl` + `0`) scaling `uiStore.zoomScale` dynamically from 80% to 150%.
