# FinShield AI — Design System

This document defines the design tokens, components, and patterns used in the FinShield platform dashboard.

## Tokens

All tokens are defined in `tailwind.config.js` and referenced via Tailwind utility classes. The `@config` directive in `src/app/globals.css` ensures the JS config is loaded by Tailwind v4.

### Colors

#### Neutrals

| Token | Value | Usage |
|-------|-------|-------|
| `bg` | `#F8F7F4` | Page background |
| `bg-alt` | `#F0EDE8` | Alternate background (sections, cards) |
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
| `ink-muted` | `#6B7280` | Muted text |
| `ink-light` | `#9CA3AF` | Light text (placeholders) |

#### Brand

| Token | Value | Usage |
|-------|-------|-------|
| `accent` | `#C8870E` | Primary action (buttons, links) |
| `accent-light` | `#E5A628` | Hover state |
| `accent-dark` | `#A06E0A` | Active state |
| `accent-muted` | `#D4930D` | Subtle accent |
| `teal` | `#1A9E8F` | Success/info accent |
| `teal-light` | `#22B8A6` | Teal hover |
| `teal-dark` | `#147A6E` | Teal active |
| `navy` | `#0A1628` | Brand dark |
| `navy-light` | `#132038` | Navy hover |
| `navy-mid` | `#1B2D4A` | Navy mid-tone |

#### Semantic

| Token | Value | Usage |
|-------|-------|-------|
| `success` | `#16A34A` | Success state |
| `success-light` | `#DCFCE7` | Success background |
| `success-bg` | `#F0FDF4` | Success subtle background |
| `warning` | `#E5A628` | Warning state |
| `warning-light` | `#FEF3C7` | Warning background |
| `warning-bg` | `#FFFBEB` | Warning subtle background |
| `danger` | `#DC2626` | Error/danger state |
| `danger-light` | `#FEE2E2` | Error background |
| `danger-bg` | `#FEF2F2` | Error subtle background |
| `info` | `#1A9E8F` | Info state (alias for teal) |
| `info-light` | `#D1FAE5` | Info background |
| `info-bg` | `#F0FDFA` | Info subtle background |

### Typography

**Font family:** Inter (sans-serif)

```css
font-family: 'Inter', -apple-system, BlinkMacSystemFont, 'Segoe UI', sans-serif;
```

**Monospace:** JetBrains Mono, Fira Code

```css
font-family: 'JetBrains Mono', 'Fira Code', monospace;
```

**Scale:** Use Tailwind's default type scale (`text-xs`, `text-sm`, `text-base`, `text-lg`, `text-xl`, `text-2xl`, `text-3xl`, `text-4xl`).

### Spacing

Use Tailwind's default spacing scale (4px base): `p-1` (4px), `p-2` (8px), `p-3` (12px), `p-4` (16px), `p-6` (24px), `p-8` (32px), `p-12` (48px).

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

**Delay utilities:** `animate-delay-1` (50ms), `animate-delay-2` (100ms), `animate-delay-3` (150ms), `animate-delay-4` (200ms).

## Components

### Glass Card

```html
<div class="glass">...</div>
<div class="glass glass-hover">...</div>
<div class="glass-strong">...</div>
```

- `glass`: Default card with border and shadow
- `glass-hover`: Adds hover lift effect
- `glass-strong`: Emphasized shadow for important cards

### Status Badge

```html
<span class="status-badge status-approved">Approved</span>
<span class="status-badge status-flagged">Flagged</span>
<span class="status-badge status-blocked">Blocked</span>
<span class="status-badge status-review">In Review</span>
```

### Buttons

Use Tailwind utilities:

```html
<button class="bg-accent text-white px-4 py-2 rounded-lg hover:bg-accent-light transition">
  Primary Action
</button>
<button class="border border-border text-ink px-4 py-2 rounded-lg hover:bg-surface-hover transition">
  Secondary Action
</button>
```

## Rules

1. **No raw palette classes.** Always use semantic tokens (`bg-surface`, `text-ink`, `border-border`), not raw colors (`bg-white`, `text-gray-900`, `border-gray-200`).
2. **No arbitrary values.** Avoid `w-[237px]` or `text-[13px]`. Use the spacing/type scale.
3. **Inter is the only font.** Do not introduce new font families without updating this document.
4. **Shadows from tokens.** Use `shadow-card`, `shadow-card-lg`, etc. Do not invent new shadow values.
5. **Animations from tokens.** Use `animate-fade-in-up`, `animate-slide-in`. Do not invent new keyframes.

## Migration

When refactoring existing components:

1. Replace raw color classes with semantic tokens.
2. Replace arbitrary values with scale values.
3. Replace custom shadows with token shadows.
4. Test visually to ensure no regression.
