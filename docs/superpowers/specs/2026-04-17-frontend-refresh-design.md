# Frontend Refresh Design

**Date:** 2026-04-17
**Status:** Approved

## Summary

Full visual refresh of the Cadencia web frontend. Introduces the existing SVG logo, navy branded header, Inter web font, avatar initials, polished badge styles, and a tuned dark mode palette. No new features, no layout restructuring, no framework changes. The stack remains FastAPI + Jinja2 + HTMX.

## Design Decisions

- **Direction:** Navy Branded — navy header bar (`#1e3a5f`) with SVG wordmark on white/light body
- **Typography:** Inter (Google Fonts, weights 300/400/500/600/700) replaces system-ui everywhere
- **Scope:** Full refresh — header, people list, person detail, forms, sections, badges, dark mode

## Visual Spec

### Header

- Background: `#1e3a5f` (navy, matches logo fill color)
- Logo: `logo-wordmark.svg` served as a static asset, white fill variant for dark backgrounds
- Nav links: inline in the header bar, active page highlighted with `rgba(255,255,255,0.15)` pill, inactive links in `#93c5fd`
- Backup status: right-aligned, `#93c5fd` normal / `#f87171` overdue
- Dark mode header: `#172554` (deeper navy to preserve contrast)

### Typography

- Font: Inter loaded from Google Fonts (`<link>` in `base.html`)
- Headings (`h1`, `h2`): `font-weight: 600`, `letter-spacing: -0.4px`
- Body: `font-size: 14px`, `font-weight: 400`
- Labels/meta: `font-size: 12–13px`, `color: var(--muted)`

### Person Rows (people list)

- Add initials avatar: 34px circle, background derived from name hash, initials in brand navy
- Layout: avatar | name+role stacked | badges right-aligned
- Card: white background, `border-radius: 8px`, subtle `box-shadow: 0 1px 2px rgba(0,0,0,0.04)`
- Hover: `background: var(--surface)` (no change needed, already works)

### Badges

Replace outline-only badges with colored fill+border pairs:
- Allocation (active): `background: #eff6ff`, `border: #bfdbfe`, `color: #1e3a5f`
- Bench: neutral surface/border/muted
- 1:1 OK: `background: #f0fdf4`, `border: #bbf7d0`, `color: #15803d`
- 1:1 overdue / stale: amber (`#fef3c7` / `#fcd34d` / `#92400e`)
- Danger: red family
- Dark mode: swap to dark-tone equivalents (navy bg, green bg, amber bg)

### Sections (person detail)

- Section cards: white bg, `border-radius: 8px`, 1px border, subtle shadow
- Section header: `background: #f8fafc`, `font-size: 11px`, uppercase, `letter-spacing: 0.06em`, muted color
- Section body: `padding: 14px 16px`

### Person Header (detail page)

- Add 48px initials avatar beside name
- Name: `font-size: 22px`, `font-weight: 700`, `letter-spacing: -0.5px`
- Meta line: role, level, notable badge (e.g. J'onn J'onzz) in brand navy

### Dark Mode Palette Updates

| Token | Current | New |
|-------|---------|-----|
| `--bg` | `#0f172a` | `#0f172a` (keep) |
| `--surface` | `#1e293b` | `#1e293b` (keep) |
| `--accent` | `#60a5fa` | `#60a5fa` (keep) |
| `--border` | `#334155` | `#334155` (keep) |
| Header bg | N/A | `#172554` |
| Allocation badge bg | none | `#1e3a5f` |
| Allocation badge border | none | `#1e40af` |
| Allocation badge text | none | `#93c5fd` |
| 1:1 OK bg | none | `#14532d` |
| 1:1 OK text | none | `#4ade80` |
| Warn bg | none | `#451a03` |
| Warn text | none | `#fbbf24` |

### Avatar Color Generation

Derive avatar background from name using a simple hash to pick from a set of brand-consistent color pairs (background/text). Avoid requiring a database change — compute client-side or in the Jinja2 template using a deterministic mapping.

Use 6 color pairs that all work in light mode; swap to dark equivalents in dark mode via CSS.

## Files Changed

| File | Change |
|------|--------|
| `app/src/cadencia/web/static/style.css` | Full rewrite of variables, header, badges, sections, avatars, dark mode |
| `app/src/cadencia/web/templates/base.html` | Add Inter font link, replace text header with SVG logo |
| `app/src/cadencia/web/templates/people_list.html` | Add avatar initials, update badge markup |
| `app/src/cadencia/web/templates/person_detail.html` | Add avatar, update section markup |
| `app/src/cadencia/web/static/logo-wordmark-white.svg` | New: white variant of wordmark for dark header |
| `app/src/cadencia/web/static/logo-mark.svg` | Copy from assets/ |
| `app/src/cadencia/web/static/logo-wordmark.svg` | Copy from assets/ |

## Out of Scope

- No new pages or routes
- No JS framework changes
- No backend changes
- No favicon (can be added separately)
- No mobile/responsive redesign (current layout is acceptable on desktop)

## Testing

- Visual check: open each page in browser, verify light and dark mode
- No automated tests needed (pure CSS/template changes)
- Existing Python tests unaffected
