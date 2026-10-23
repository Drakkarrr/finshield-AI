# FinShield AI — Design System

This document defines the design tokens, components and patterns of the FinShield platform app (`platform-app/`). It describes the state after Phase 5 (S5.1–S5.3); `S5.2-MIGRATION.md` records what changed and what is still open.

## Tokens

All tokens live in `tailwind.config.js` (`theme.extend`) and are used as Tailwind utilities. The `@config` directive in `src/app/globals.css` loads the JS config into Tailwind v4.

### Colors

#### Neutrals

| Token | Value | Usage |
|-------|-------|-------|
| `bg` | `#F8F7F4` | Page background |
| `bg-alt` | `#F0EDE8` | Alternate background (sections, tracks) |
| `bg-dark` | `#0A1628` | Dark background (brand panel) |
| `surface` | `#FFFFFF` | Card surface |
| `surface-hover` | `#F5F4F0` | Hover state |
| `surface-raised` | `#FAFAF8` | Elevated surface |
| `border` | `#E2DFD8` | Default border |
| `border-light` | `#EDEBE6` | Subtle border |
| `border-dark` | `#D4D0C8` | Emphasized border |

#### Text

| Token | Value | Usage |
|-------|-------|-------|
| `ink` | `#1A1A2E` | Primary text |
| `ink-secondary` | `#4A5568` | Secondary text |
| `ink-muted` | `#6B7280` | Muted text (4.8:1 on white — the lightest colour allowed for information) |
| `ink-light` | `#9CA3AF` | Placeholders and decoration only (2.5:1 — never for information) |

#### Brand

| Token | Value | Usage |
|-------|-------|-------|
| `accent` | `#C8870E` | Primary button fill, focus ring, active nav |
| `accent-light` | `#E5A628` | Primary button hover |
| `accent-dark` | `#A06E0A` | Link hover |
| `accent-muted` | `#D4930D` | Subtle accent |
| `accent-fg` | `#875C08` | Accent as **text / links** on light surfaces (5.9:1 on white; `accent` is 3:1) |
| `teal` | `#1A9E8F` | Teal accent |
| `teal-light` | `#22B8A6` | Teal hover |
| `teal-dark` | `#147A6E` | Teal active |
| `navy` | `#0A1628` | Sidebar, brand panel, text on accent buttons |
| `navy-light` | `#132038` | Navy hover |
| `navy-mid` | `#1B2D4A` | Navy mid-tone |

#### Semantic

| Token | Value | Usage |
|-------|-------|-------|
| `success` | `#16A34A` | Fills, dots, bars |
| `success-light` | `#DCFCE7` | Badge border / strong background |
| `success-bg` | `#F0FDF4` | Subtle background |
| `success-fg` | `#15803D` | Success **text** (4.8:1 on `success-bg`) |
| `warning` | `#E5A628` | Fills, dots, bars |
| `warning-light` | `#FEF3C7` | Badge border / strong background |
| `warning-bg` | `#FFFBEB` | Subtle background |
| `warning-fg` | `#92400E` | Warning **text** (6.8:1; `warning` itself is 2:1 — fills only) |
| `danger` | `#DC2626` | Fills, dots, bars |
| `danger-light` | `#FEE2E2` | Badge border / strong background |
| `danger-bg` | `#FEF2F2` | Subtle background |
| `danger-fg` | `#B91C1C` | Error **text** (5.9:1 on `danger-bg`) |
| `info` | `#1A9E8F` | Fills (alias of teal) |
| `info-light` | `#D1FAE5` | Badge border / strong background |
| `info-bg` | `#F0FDFA` | Subtle background |
| `info-fg` | `#0F766E` | Info **text** (5.3:1 on `info-bg`) |

**Contrast rule.** `DEFAULT` semantic colours are for fills, dots, bars and borders; text uses the `-fg` variant. Primary buttons are navy text on `accent` (white on `accent` is 3:1 and fails WCAG AA).

### Typography

| Token | Value | Usage |
|-------|-------|-------|
| `font-sans` | Inter via `next/font` (`--font-inter`) | Everything |
| `font-mono` | JetBrains Mono via `next/font` (`--font-mono`) | IDs, hashes, codes |

Fonts are self-hosted by `next/font/google` in `src/app/layout.tsx` (fetched at build time), so the CSP needs no font origin. Do not add `<link>` font tags.

**Scale:** Tailwind's default type scale plus one smaller step:

| Token | Size / line height | Usage |
|-------|-------|-------|
| `text-2xs` | 11px / 16px | Dense meta text only: table sub-lines, timestamps, badges |
| `text-xs` … `text-3xl` | Tailwind defaults | Body is `text-sm`, page titles `text-2xl` |

### Spacing and layout

Tailwind's default 4px spacing scale (`p-1` = 4px … `p-12` = 48px), plus:

| Token | Value | Usage |
|-------|-------|-------|
| `w-sidebar` / `ml-sidebar` | 16rem | Sidebar width and the main column offset |
| `max-h-modal` | 85vh | Modal height cap |

### Z-index

| Token | Value | Usage |
|-------|-------|-------|
| `z-topbar` | 40 | Sticky top bar |
| `z-sidebar` | 50 | Fixed sidebar |
| `z-dropdown` | 60 | Menus / popovers (notifications) |
| `z-modal` | 70 | Focused skip link. Modals use the native `<dialog>` top layer and need no z-index |

### Radii

`rounded-lg` (8px) for small controls and list rows, `rounded-xl` (12px) for inputs, buttons and cards, `rounded-2xl` (16px) for modals, `rounded-full` for badges, switches and meters.

### Shadows

| Token | Value | Usage |
|-------|-------|-------|
| `shadow-card` | `0 1px 3px rgba(10, 22, 40, 0.04), 0 1px 2px rgba(10, 22, 40, 0.06)` | Default card |
| `shadow-card-lg` | `0 4px 12px rgba(10, 22, 40, 0.08)` | Hovered card |
| `shadow-card-xl` | `0 8px 24px rgba(10, 22, 40, 0.12)` | Elevated card |
| `shadow-dropdown` | `0 12px 40px rgba(10, 22, 40, 0.15)` | Dropdowns, modals |

### Animations

| Token | Duration | Easing | Usage |
|-------|----------|--------|-------|
| `animate-fade-in-up` | 0.4s | ease | Page entry |
| `animate-slide-in` | 0.3s | ease | Side panels |

`prefers-reduced-motion: reduce` disables animations and transitions globally (`globals.css`).

## Components (`src/components/ui/`, import from `@/components/ui`)

Every primitive owns its focus ring, disabled state, error state and ARIA wiring, so accessibility is fixed once rather than per page.

| Primitive | Notes |
|-----------|-------|
| `Button`, `buttonClasses()` | `primary` (navy on accent), `secondary`, `danger`, `ghost`; `sm/md/lg`; `loading` sets `aria-busy`. `buttonClasses()` styles a `<Link>` as a button |
| `Input`, `Textarea`, `Select` | `label` is **required** (`hideLabel` keeps it for screen readers only); `error` / `helpText` linked with `aria-describedby`; `aria-invalid` on error |
| `Switch` | `role="switch"` + `aria-checked`, labelled by its visible label |
| `Card` | The `.glass` surface; `as="section" / "form" / "article"`; padding `none/sm/md/lg` |
| `Badge`, `StatusBadge` | The text carries the meaning, colour reinforces it. `StatusBadge` maps API statuses to tones |
| `Alert` | `role="alert"` for danger, `role="status"` otherwise; optional dismiss button with `aria-label` |
| `Modal` | Native `<dialog>` + `showModal()` (page inert behind it), explicit Tab wrap, Escape and backdrop click close, focus moves in (`data-autofocus` or first focusable) and back to the opener, `aria-labelledby` / `aria-describedby` |
| `Table`, `THead`, `TBody`, `Tr`, `Th`, `Td` | `caption` is **required** (visually hidden by default); `Th` defaults to `scope="col"`, `scope="row"` for row headers |
| `Tabs`, `TabPanel` | WAI-ARIA tabs: roving `tabIndex`, Left/Right arrow keys |
| `FilterChips` | `role="group"` of `aria-pressed` toggle buttons |
| `Pagination` | `<nav>` with a live "1–50 of 10,000" range (offset/limit) |
| `Meter` | `role="meter"` with `aria-valuenow` / `aria-valuetext`; holds the only inline `style` in `src/` (the bar width is data) |
| `Spinner`, `LoadingState`, `EmptyState` | Loading (`role="status"`) and empty states |
| `PageHeader`, `InfoRow`, `CopyButton` | Page title + actions; `<dt>`/`<dd>` pair; clipboard button with a live "Copied" |

Domain components outside `ui/`: `RiskScore` (percentage + worded level, e.g. "62% · Medium"), `AuthShell` (login / sign-up layout).

## Rules

1. **No raw palette classes.** Use semantic tokens (`bg-surface`, `text-ink`, `text-danger-fg`), never `bg-white`, `text-gray-900`, `bg-red-500`. Enforced: `npm run lint` fails on any `(bg|text|border|ring|from|to|via|fill|stroke)-<palette>-<shade>` class string (`no-restricted-syntax` in `eslint.config.mjs`).
2. **No arbitrary values.** No `w-[237px]` / `text-[13px]`; add a token here instead (count in `src/` today: 0).
3. **No hand-rolled tables or modals.** Use `Table` and `Modal`.
4. **Colour is never the only signal.** Status, risk and health always carry text (badge label, "Medium", "Stale (31 h)").
5. **Every control is labelled; icon-only buttons have `aria-label`; decorative SVGs have `aria-hidden="true"`.** The `jsx-a11y` recommended rules run in `npm run lint`.
6. **Inter and JetBrains Mono only**, loaded by `next/font`.
7. **Shadows and animations from tokens.** Do not invent new values.

## Do / don't

| Do | Don't |
|----|-------|
| `<Badge tone="danger">Blocked</Badge>` | A red dot with no text |
| `text-warning-fg` on `bg-warning-bg` | `text-warning` for text (2:1 contrast) |
| `<Input label="Amount" … />` | `<input placeholder="Amount">` with no label |
| `aria-label="Delete case CASE-1A2B"` on repeated row buttons | A column of identical, context-free "Delete" buttons |
| Hide what a role cannot do with `useCan()` (mirror of the backend matrix in `src/lib/permissions.ts`) | UI-only permission rules — `backend/app/permissions.py` is the authority |
