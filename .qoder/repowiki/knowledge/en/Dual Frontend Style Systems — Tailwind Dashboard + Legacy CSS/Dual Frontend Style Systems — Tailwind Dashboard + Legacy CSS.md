---
kind: frontend_style
name: Dual Frontend Style Systems — Tailwind Dashboard + Legacy CSS
category: frontend_style
scope:
    - '**'
source_files:
    - platform-app/tailwind.config.js
    - platform-app/postcss.config.js
    - platform-app/src/app/globals.css
    - platform-app/src/components/Sidebar.tsx
    - website/css/main.css
    - website/css/platform.css
---

## Overview

FinShield ships two independent frontends with separate styling stacks:

1. **platform-app** (Next.js App Router dashboard) — styled with **Tailwind CSS v3** plus PostCSS/autoprefixer.
2. **website** (static marketing site + legacy platform console) — styled with hand-written vanilla CSS in `website/css/`.

There is no shared component library, design-token package, or cross-frontend style system; the two stacks coexist side-by-side.

---

## Platform App (Next.js Dashboard)

### Stack
- **Tailwind CSS** configured via `platform-app/tailwind.config.js`, scanned under `src/pages/**`, `src/components/**`, `src/app/**`.
- **PostCSS** pipeline (`platform-app/postcss.config.js`) runs `tailwindcss` then `autoprefixer`.
- Global styles live in `platform-app/src/app/globals.css` (imported by the root layout).

### Design tokens
The Tailwind config extends the default theme with a cohesive palette defined as semantic color groups:

| Group | Tokens | Purpose |
|-------|--------|---------|
| `bg` | `DEFAULT #F8F7F4`, `alt #F0EDE8`, `dark #0A1628` | Page backgrounds |
| `surface` | `DEFAULT #FFFFFF`, `hover #F5F4F0`, `raised #FAFAF8` | Cards / panels |
| `border` | `DEFAULT #E2DFD8`, `light #EDEBE6`, `dark #D4D0C8` | Borders |
| `ink` | `DEFAULT #1A1A2E`, `secondary #4A5568`, `muted #6B7280`, `light #9CA3AF` | Text |
| Brand accents | `accent #C8870E`, `teal #1A9E8F`, `navy #0A1628` | Primary brand colors |
| Semantic | `success #16A34A`, `warning #E5A628`, `danger #DC2626`, `info #1A9E8F` |

Shadows (`card`, `card-lg`, `card-xl`, `dropdown`) and animations (`fade-in-up`, `slide-in`) are also extended in the same file.

### CSS variables
`globals.css` re-declares the palette as CSS custom properties (`--bg`, `--surface`, `--text`, `--accent`, `--teal`, `--navy`, `--shadow-sm/md/lg`) so components can reference them directly without Tailwind class names.

### Component-level conventions
- **Glass cards**: `.glass`, `.glass-hover`, `.glass-strong` classes in `globals.css` provide a consistent card look (white surface, border, rounded-12px, shadow-sm/md).
- **Status badges**: `.status-badge` combined with `.status-approved` / `.status-flagged` / `.status-blocked` / `.status-review` variants.
- **Animations**: `.animate-fade-in-up` plus `.animate-delay-{1..4}` helpers.
- **Inputs**: global focus ring using `var(--accent)` with a 3px gold glow.
- **Typography**: Inter as primary font, JetBrains Mono / Fira Code for monospace IDs.
- **Layout**: Tailwind utility classes dominate; components like `Sidebar.tsx` compose layout entirely through Tailwind classes (`fixed left-0 top-0 bottom-0 w-64 bg-navy flex flex-col z-50`).

### Responsive strategy
No explicit breakpoints are added to `tailwind.config.js`; responsiveness relies on Tailwind's default breakpoint scale applied inline via utility classes (e.g., `w-64`, `flex`, `hidden md:flex` patterns observed in pages). No media queries exist in the project's CSS files.

---

## Website (Static Marketing + Legacy Console)

### Structure
Three CSS files under `website/css/`:
- `main.css` (~3279 lines) — marketing landing page styles.
- `platform.css` (~836 lines) — legacy dark-themed platform console (sidebar, nav items, glassmorphism).
- `admin.css` — admin shell styles.

### Design tokens
Both `main.css` and `platform.css` define their own `:root` variable sets:

- `main.css` uses light-theme tokens: `--navy`, `--gold`, `--teal`, `--bg`, `--text`, spacing scale (`--space-xs` … `--space-5xl`), radius scale (`--radius-sm` … `--radius-2xl`), shadows, and transition constants (`--ease`, `--duration`, `--duration-slow`).
- `platform.css` defines a parallel dark-theme token set prefixed with `--plat-*` (`--plat-bg`, `--plat-surface`, `--plat-card`, `--plat-accent`, `--plat-gold`, `--plat-sidebar: 260px`, `--plat-topbar: 64px`).

### Naming convention
BEM-style class naming throughout: `.hero__grid`, `.feature-card__icon--navy`, `.pipeline-stage--active`, `.plat-sidebar__nav-item`, etc. This is a deliberate convention stated in the file headers ("Professional compliance platform website", "Glassmorphism + modern compliance platform").

### Visual identity
- **Brand palette**: Navy `#0A1628`, Gold `#C8870E`, Teal `#1A9E8F` — mirrored between both CSS files and the Tailwind config of the dashboard.
- **Typography**: Inter (sans-serif) + JetBrains Mono / Fira Code (monospace).
- **Marketing site**: Light background (`#F8F7F4`), warm neutrals, section-based layout with `.section`, `.features-grid`, `.hero`, `.trust-bar`, `.stats`, `.industries-grid`, `.security-section`.
- **Legacy platform console**: Dark glassmorphism sidebar (`backdrop-filter: blur(40px) saturate(150%)`), fixed 260px sidebar, active item indicator with a left accent bar.

### Responsive strategy
Uses CSS `clamp()` for fluid typography (e.g., `h1 { font-size: clamp(2.25rem, 5vw, 3.5rem); }`) and CSS Grid/Flexbox layouts. No dedicated mobile breakpoints are declared in the CSS; responsive behavior is achieved through percentage widths, `max-width`, and viewport-relative units.

---

## Cross-Frontend Observations

- **Color consistency**: The Tailwind config in `platform-app/tailwind.config.js` explicitly comments `// Warm neutrals — matching website palette` and `// Brand accents — matching website`, indicating intentional alignment of the dashboard's Tailwind tokens with the static site's CSS variables.
- **No shared token source**: Each frontend owns its own copy of the palette; changes must be duplicated across `tailwind.config.js`, `globals.css`, `main.css`, and `platform.css`.
- **No shared component library**: Components are written inline with Tailwind utilities (dashboard) or BEM classes (website); there is no shared UI kit.
- **No CSS-in-JS or SCSS**: Both stacks use plain CSS (with Tailwind utilities for the dashboard).
- **No dark mode toggle**: The dashboard is light-themed; the legacy console is dark-themed. Theme switching is not implemented.