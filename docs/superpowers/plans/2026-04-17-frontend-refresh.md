# Frontend Refresh Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Apply a navy-branded visual refresh to all Cadencia web pages: SVG logo in header, Inter font, initials avatars, colored pill badges, polished section cards, and an updated dark mode palette.

**Architecture:** Pure CSS + Jinja2 template changes. No backend logic, no new routes, no JS framework. The static file server already mounts `app/src/cadencia/web/static/` at `/static`. SVG logo files live in `assets/` at the project root and must be copied to `static/` to be served.

**Tech Stack:** FastAPI, Jinja2 templates, HTMX, plain CSS (no preprocessor). Google Fonts CDN for Inter. No Python test changes needed — verification is visual (open browser at http://localhost:8080).

---

## File Map

| File | Action | What changes |
|------|--------|-------------|
| `app/src/cadencia/web/static/logo-wordmark-white.svg` | Create | White-fill variant of wordmark for navy header |
| `app/src/cadencia/web/static/logo-wordmark.svg` | Create | Copy from `assets/logo-wordmark.svg` |
| `app/src/cadencia/web/static/logo-mark.svg` | Create | Copy from `assets/logo-mark.svg` |
| `app/src/cadencia/web/static/style.css` | Modify | Full visual refresh |
| `app/src/cadencia/web/templates/base.html` | Modify | Inter font link, navy header with SVG logo |
| `app/src/cadencia/web/templates/people_list.html` | Modify | Initials avatars, updated badge markup |
| `app/src/cadencia/web/templates/person_detail.html` | Modify | 48px avatar in person header |

---

## Task 1: Copy logo assets to static directory

**Files:**
- Create: `app/src/cadencia/web/static/logo-wordmark.svg`
- Create: `app/src/cadencia/web/static/logo-mark.svg`
- Create: `app/src/cadencia/web/static/logo-wordmark-white.svg`

The existing logos use `fill="#1e3a5f"` (navy). The header background will be navy, so we need a white variant. The white variant swaps every `#1e3a5f` fill/stroke to `#ffffff`.

- [ ] **Step 1: Copy logo-wordmark.svg to static**

```bash
cp assets/logo-wordmark.svg app/src/cadencia/web/static/logo-wordmark.svg
```

- [ ] **Step 2: Copy logo-mark.svg to static**

```bash
cp assets/logo-mark.svg app/src/cadencia/web/static/logo-mark.svg
```

- [ ] **Step 3: Create white wordmark variant**

Create `app/src/cadencia/web/static/logo-wordmark-white.svg` with this exact content:

```svg
<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 280 64" width="280" height="64">
  <circle cx="16" cy="50" r="5" fill="#ffffff"/>
  <circle cx="48" cy="50" r="5" fill="#ffffff"/>
  <path d="M 11 46 Q 32 10 53 46" fill="none" stroke="#ffffff" stroke-width="3.5" stroke-linecap="round"/>
  <text
    x="72"
    y="52"
    font-family="system-ui, -apple-system, 'Segoe UI', Helvetica, Arial, sans-serif"
    font-size="32"
    font-weight="300"
    letter-spacing="2"
    fill="#ffffff"
  >Cadencia</text>
</svg>
```

- [ ] **Step 4: Verify assets are served**

With the app running, open http://localhost:8080/static/logo-wordmark-white.svg in the browser. You should see a white SVG on whatever background the browser uses.

- [ ] **Step 5: Commit**

```bash
git add app/src/cadencia/web/static/logo-wordmark.svg \
        app/src/cadencia/web/static/logo-mark.svg \
        app/src/cadencia/web/static/logo-wordmark-white.svg
git commit -m "feat(ui): add logo SVG assets to static directory"
```

---

## Task 2: Update base.html — Inter font + navy header with logo

**Files:**
- Modify: `app/src/cadencia/web/templates/base.html`

Replace the plain-text `<h1>Cadencia</h1>` header with the SVG wordmark inside a navy `<header>` bar. Add Inter from Google Fonts.

- [ ] **Step 1: Replace base.html**

```html
<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>{% block title %}Cadencia{% endblock %}</title>
  <link rel="preconnect" href="https://fonts.googleapis.com">
  <link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
  <link href="https://fonts.googleapis.com/css2?family=Inter:wght@300;400;500;600;700&display=swap" rel="stylesheet">
  <link rel="stylesheet" href="/static/style.css">
  <script src="/static/htmx.min.js" defer></script>
</head>
<body>
  <header class="site-header">
    <a href="/" class="site-logo">
      <img src="/static/logo-wordmark-white.svg" alt="Cadencia" height="28">
    </a>
    <nav class="site-nav">
      <a href="/people" class="nav-link {% block nav_people %}{% endblock %}">People</a>
      <a href="/stakeholders" class="nav-link {% block nav_stakeholders %}{% endblock %}">Stakeholders</a>
    </nav>
    <div class="backup-status {% if backup_overdue %}overdue{% endif %}">
      {% if backup_overdue %}
        backup: OVERDUE
      {% elif backup_ts %}
        last backup: {{ backup_ts }}
      {% else %}
        backup: never
      {% endif %}
    </div>
  </header>
  <main class="container">
    {% block content %}{% endblock %}
  </main>
</body>
</html>
```

- [ ] **Step 2: Verify in browser**

Open http://localhost:8080 — you should see the navy header with the white Cadencia logo. Nav links "People" and "Stakeholders" should appear. The active page won't be highlighted yet (that comes in Task 3 with CSS).

- [ ] **Step 3: Commit**

```bash
git add app/src/cadencia/web/templates/base.html
git commit -m "feat(ui): navy header with SVG wordmark and Inter font"
```

---

## Task 3: Rewrite style.css — variables, typography, header, nav

**Files:**
- Modify: `app/src/cadencia/web/static/style.css`

Replace the `:root` variables, body typography, and header/nav styles. This task handles the structural CSS; badges and avatars come in later tasks.

- [ ] **Step 1: Replace the top of style.css (variables through header)**

Replace everything from the top of the file through the `.backup-status` block (roughly lines 1–62 in the current file) with:

```css
/* Cadencia — Inter, navy-branded */

:root {
  --bg: #ffffff;
  --fg: #0f172a;
  --muted: #64748b;
  --border: #e2e8f0;
  --accent: #1e3a5f;
  --accent-light: #eff6ff;
  --accent-border: #bfdbfe;
  --warn: #92400e;
  --warn-bg: #fef3c7;
  --warn-border: #fcd34d;
  --danger: #dc2626;
  --danger-bg: #fee2e2;
  --danger-border: #fca5a5;
  --ok: #15803d;
  --ok-bg: #f0fdf4;
  --ok-border: #bbf7d0;
  --surface: #f8fafc;
  --radius: 8px;
  --shadow-sm: 0 1px 2px rgba(0, 0, 0, 0.05);
  --shadow: 0 1px 4px rgba(0, 0, 0, 0.07);
}

@media (prefers-color-scheme: dark) {
  :root {
    --bg: #0f172a;
    --fg: #f1f5f9;
    --muted: #64748b;
    --border: #334155;
    --accent: #93c5fd;
    --accent-light: #1e3a5f;
    --accent-border: #1e40af;
    --warn: #fbbf24;
    --warn-bg: #451a03;
    --warn-border: #92400e;
    --danger: #f87171;
    --danger-bg: #450a0a;
    --danger-border: #991b1b;
    --ok: #4ade80;
    --ok-bg: #14532d;
    --ok-border: #166534;
    --surface: #1e293b;
    --shadow-sm: 0 1px 2px rgba(0, 0, 0, 0.3);
    --shadow: 0 1px 4px rgba(0, 0, 0, 0.4);
  }
}

* { box-sizing: border-box; margin: 0; padding: 0; }

body {
  font-family: 'Inter', system-ui, -apple-system, sans-serif;
  font-size: 14px;
  line-height: 1.5;
  background: var(--bg);
  color: var(--fg);
}

a { color: var(--accent); text-decoration: none; }
a:hover { text-decoration: underline; }

/* Header */
.site-header {
  display: flex;
  align-items: center;
  gap: 16px;
  padding: 0 24px;
  height: 52px;
  background: #1e3a5f;
  border-bottom: none;
}

@media (prefers-color-scheme: dark) {
  .site-header { background: #172554; }
}

.site-logo { display: flex; align-items: center; text-decoration: none; }
.site-logo:hover { text-decoration: none; }

.site-nav {
  display: flex;
  align-items: center;
  gap: 2px;
  margin-left: 16px;
}

.nav-link {
  font-size: 13px;
  font-weight: 400;
  color: #93c5fd;
  padding: 5px 12px;
  border-radius: 6px;
  text-decoration: none;
  transition: background 0.1s;
}

.nav-link:hover { background: rgba(255, 255, 255, 0.1); text-decoration: none; color: #fff; }
.nav-link.active { background: rgba(255, 255, 255, 0.15); color: #fff; font-weight: 500; }

.backup-status {
  margin-left: auto;
  font-size: 12px;
  color: #7dd3fc;
}

.backup-status.overdue { color: #fca5a5; font-weight: 600; }

.container { max-width: 960px; margin: 0 auto; padding: 24px; }
```

- [ ] **Step 2: Verify in browser**

Open http://localhost:8080/people — the header should now be navy with the white logo and nav links in light blue. The rest of the page will still use old styles temporarily.

- [ ] **Step 3: Commit**

```bash
git add app/src/cadencia/web/static/style.css
git commit -m "feat(ui): update CSS variables, Inter font, navy header styles"
```

---

## Task 4: Update style.css — badges, buttons, sections, people list

**Files:**
- Modify: `app/src/cadencia/web/static/style.css`

Replace all badge, button, section, person-row, and sort-controls styles with the refreshed versions.

- [ ] **Step 1: Replace everything after the container rule to end of file**

After the `.container` rule (end of Task 3's block), replace the rest of `style.css` with:

```css
/* Sort controls */
.sort-controls {
  display: flex;
  align-items: center;
  gap: 6px;
  margin-bottom: 12px;
}

.sort-label { font-size: 12px; color: var(--muted); font-weight: 500; }

.sort-btn {
  font-size: 12px;
  font-weight: 500;
  padding: 3px 10px;
  border-radius: 12px;
  border: 1px solid var(--border);
  background: var(--bg);
  color: var(--muted);
  cursor: pointer;
  font-family: inherit;
}

.sort-btn:hover { border-color: var(--accent); color: var(--accent); }
.sort-btn.active { border-color: var(--accent); color: var(--accent); background: var(--accent-light); }

/* People list */
.people-list { margin-top: 0; }

.person-row {
  display: flex;
  align-items: center;
  gap: 14px;
  padding: 12px 16px;
  border: 1px solid var(--border);
  border-radius: var(--radius);
  margin-bottom: 6px;
  background: var(--bg);
  text-decoration: none;
  color: var(--fg);
  box-shadow: var(--shadow-sm);
  transition: background 0.1s;
}

.person-row:hover { background: var(--surface); text-decoration: none; }

/* Initials avatar */
.avatar {
  width: 34px;
  height: 34px;
  border-radius: 50%;
  display: flex;
  align-items: center;
  justify-content: center;
  font-weight: 600;
  font-size: 12px;
  flex-shrink: 0;
  letter-spacing: 0.02em;
}

.avatar-lg {
  width: 48px;
  height: 48px;
  font-size: 16px;
}

/* 6 avatar color pairs — light mode */
.av-0 { background: #dbeafe; color: #1e3a5f; }
.av-1 { background: #ede9fe; color: #4c1d95; }
.av-2 { background: #dcfce7; color: #14532d; }
.av-3 { background: #fef3c7; color: #78350f; }
.av-4 { background: #fce7f3; color: #831843; }
.av-5 { background: #ccfbf1; color: #134e4a; }

@media (prefers-color-scheme: dark) {
  .av-0 { background: #1e3a5f; color: #93c5fd; }
  .av-1 { background: #2e1065; color: #c4b5fd; }
  .av-2 { background: #14532d; color: #86efac; }
  .av-3 { background: #451a03; color: #fcd34d; }
  .av-4 { background: #4c0519; color: #fda4af; }
  .av-5 { background: #042f2e; color: #99f6e4; }
}

.person-info { flex: 1; min-width: 0; }
.person-name { font-weight: 600; font-size: 14px; letter-spacing: -0.2px; }
.person-role { color: var(--muted); font-size: 12px; margin-top: 1px; }

/* Badges — colored fill+border pill style */
.badge {
  font-size: 11px;
  font-weight: 500;
  padding: 3px 9px;
  border-radius: 12px;
  background: var(--surface);
  border: 1px solid var(--border);
  white-space: nowrap;
  color: var(--muted);
}

.badge.alloc  { background: var(--accent-light); border-color: var(--accent-border); color: var(--accent); }
.badge.ok     { background: var(--ok-bg);         border-color: var(--ok-border);     color: var(--ok); }
.badge.warn   { background: var(--warn-bg);        border-color: var(--warn-border);   color: var(--warn); }
.badge.danger { background: var(--danger-bg);      border-color: var(--danger-border); color: var(--danger); }
.badge.muted  { color: var(--muted); }

/* Person detail header */
.person-header {
  display: flex;
  align-items: center;
  gap: 16px;
  margin-bottom: 24px;
}

.person-header-info { flex: 1; }
.person-header h2 { font-size: 22px; font-weight: 700; letter-spacing: -0.5px; }
.person-header .meta { color: var(--muted); font-size: 13px; margin-top: 2px; }

/* Sections */
.section {
  border: 1px solid var(--border);
  border-radius: var(--radius);
  margin-bottom: 10px;
  background: var(--bg);
  box-shadow: var(--shadow-sm);
}

.section-header {
  padding: 10px 16px;
  background: var(--surface);
  border-bottom: 1px solid var(--border);
  font-size: 11px;
  font-weight: 600;
  letter-spacing: 0.06em;
  text-transform: uppercase;
  color: var(--muted);
  border-radius: var(--radius) var(--radius) 0 0;
}

.section-header.collapsible {
  cursor: pointer;
  display: flex;
  justify-content: space-between;
  align-items: center;
  border-radius: var(--radius);
}

.section-header.collapsible.open { border-radius: var(--radius) var(--radius) 0 0; }

.section-body { padding: 14px 16px; }

/* Right now (allocation) */
.allocation-line { display: flex; gap: 12px; align-items: center; flex-wrap: wrap; }
.stale-note { font-size: 12px; color: var(--warn); }

/* Action items */
.action-item {
  display: flex;
  align-items: flex-start;
  gap: 10px;
  padding: 10px 0;
  border-bottom: 1px solid var(--border);
}

.action-item:last-child { border-bottom: none; }

.action-item .complete-btn {
  background: none;
  border: 1px solid var(--border);
  border-radius: 4px;
  padding: 2px 8px;
  font-size: 11px;
  font-family: inherit;
  cursor: pointer;
  color: var(--muted);
  white-space: nowrap;
}

.action-item .complete-btn:hover { border-color: var(--ok-border); color: var(--ok); }

.action-item-text { flex: 1; font-size: 13px; }
.action-item-owner { font-size: 11px; color: var(--muted); margin-top: 2px; }
.action-item-due { font-size: 11px; color: var(--muted); white-space: nowrap; }
.action-item-due.overdue { color: var(--danger); }

/* Observations */
.observation {
  padding: 10px 0;
  border-bottom: 1px solid var(--border);
}

.observation:last-child { border-bottom: none; }

.obs-meta { font-size: 12px; color: var(--muted); margin-bottom: 4px; }
.obs-tags { display: flex; gap: 4px; flex-wrap: wrap; margin-top: 4px; }
.obs-tag {
  font-size: 11px;
  padding: 1px 6px;
  border-radius: 10px;
  background: var(--surface);
  border: 1px solid var(--border);
  color: var(--muted);
}

/* Misc */
.empty { color: var(--muted); font-size: 13px; font-style: italic; }
.back-link { font-size: 13px; color: var(--muted); margin-bottom: 16px; display: block; }
.back-link:hover { color: var(--fg); }
.htmx-indicator { opacity: 0.4; }

/* List header */
.list-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  margin-bottom: 16px;
}

.list-header h2 { font-size: 20px; font-weight: 600; letter-spacing: -0.4px; }

/* Buttons */
.btn {
  display: inline-block;
  padding: 7px 14px;
  font-size: 13px;
  font-weight: 500;
  font-family: inherit;
  border-radius: var(--radius);
  cursor: pointer;
  border: 1px solid var(--border);
  background: var(--bg);
  color: var(--fg);
  text-decoration: none;
  line-height: 1.4;
}

.btn:hover { background: var(--surface); text-decoration: none; }
.btn-primary { background: #1e3a5f; color: #fff; border-color: #1e3a5f; }
.btn-primary:hover { background: #1e40af; border-color: #1e40af; opacity: 1; }
.btn-danger { color: var(--danger); border-color: var(--danger-border); }
.btn-danger:hover { background: var(--danger-bg); color: var(--danger); }

@media (prefers-color-scheme: dark) {
  .btn-primary { background: #1d4ed8; border-color: #1d4ed8; }
  .btn-primary:hover { background: #2563eb; border-color: #2563eb; }
}

/* Person form */
.person-form {
  display: flex;
  flex-direction: column;
  gap: 12px;
  max-width: 480px;
}

.person-form .field { display: flex; flex-direction: column; gap: 4px; }

.person-form label {
  font-size: 12px;
  font-weight: 600;
  letter-spacing: 0.04em;
  text-transform: uppercase;
  color: var(--muted);
}

.person-form input,
.person-form select {
  padding: 7px 10px;
  font-size: 14px;
  font-family: inherit;
  border: 1px solid var(--border);
  border-radius: var(--radius);
  background: var(--bg);
  color: var(--fg);
  width: 100%;
}

.person-form input:focus,
.person-form select:focus {
  outline: 2px solid #1e3a5f;
  outline-offset: -1px;
  border-color: #1e3a5f;
}

.advanced-details {
  border: 1px solid var(--border);
  border-radius: var(--radius);
  padding: 10px 12px;
}

.advanced-details summary {
  font-size: 13px;
  color: var(--accent);
  cursor: pointer;
  user-select: none;
  list-style: none;
}

.advanced-details summary::-webkit-details-marker { display: none; }
.advanced-details summary::before { content: "▶ "; font-size: 10px; }
.advanced-details[open] summary::before { content: "▼ "; font-size: 10px; }

.advanced-fields {
  display: flex;
  flex-direction: column;
  gap: 12px;
  padding-top: 12px;
}

.form-actions { display: flex; gap: 8px; align-items: center; margin-top: 4px; }

.recurrence-hint {
  font-size: 12px;
  color: var(--muted);
  line-height: 1.5;
  padding: 6px 0 2px;
}

/* Danger zone */
.danger-zone {
  margin-top: 32px;
  max-width: 480px;
  border: 1px solid var(--danger-border);
  border-radius: var(--radius);
  opacity: 0.85;
}

.danger-zone .section-header {
  color: var(--danger);
  background: transparent;
  border-bottom-color: var(--danger-border);
}

/* Cadence inline edit */
.edit-btn {
  background: none;
  border: none;
  padding: 0 2px;
  font-size: 11px;
  font-family: inherit;
  color: var(--muted);
  cursor: pointer;
  text-decoration: underline;
  text-underline-offset: 2px;
}
.edit-btn:hover { color: var(--accent); }
```

- [ ] **Step 2: Verify in browser**

Open http://localhost:8080/people — person rows should now show cards with a subtle shadow, badges should render as colored pills, buttons should match the navy brand.

- [ ] **Step 3: Commit**

```bash
git add app/src/cadencia/web/static/style.css
git commit -m "feat(ui): refresh badges, buttons, sections, and dark mode palette"
```

---

## Task 5: Update people_list.html — initials avatars and active nav

**Files:**
- Modify: `app/src/cadencia/web/templates/people_list.html`

Add initials avatar to each person row. Update badge classes to use the new semantic variants (`alloc`, `ok`, `warn`, `danger`, `muted`). Mark the People nav link as active.

- [ ] **Step 1: Replace people_list.html**

```html
{% extends "base.html" %}
{% block title %}People | Cadencia{% endblock %}
{% block nav_people %}active{% endblock %}

{% block content %}
<div class="list-header">
  <h2>People</h2>
  <a href="/people/new" class="btn btn-primary">+ Add person</a>
</div>

<div class="sort-controls">
  <span class="sort-label">Sort:</span>
  <button class="sort-btn active" data-sort="name">Name</button>
  <button class="sort-btn" data-sort="level">Level</button>
  <button class="sort-btn" data-sort="alloc">Allocation</button>
</div>

<div class="people-list" id="people-list">
  {% for person in people %}
  {# Compute alloc sort key: 0=no alloc, 1=bench, 2=partial, 3=full #}
  {% if person.current_allocation_type is none %}
    {% set alloc_key = 0 %}
  {% elif person.current_allocation_type == "bench" %}
    {% set alloc_key = 1 %}
  {% elif person.current_allocation_percent is not none and person.current_allocation_percent < 100 %}
    {% set alloc_key = 2 %}
  {% else %}
    {% set alloc_key = 3 %}
  {% endif %}
  {# Compute numeric level from seniority string like "L5" #}
  {% set level_num = (person.seniority or "L0")[1:] | int(default=0) %}
  {# Compute initials and avatar color index from name length #}
  {% set _parts = person.name.split() %}
  {% if _parts | length >= 2 %}
    {% set _initials = (_parts[0][0] ~ _parts[1][0]) | upper %}
  {% else %}
    {% set _initials = person.name[:2] | upper %}
  {% endif %}
  {% set _av_idx = (person.name | length) % 6 %}
  <a class="person-row"
     href="/people/{{ person.id }}"
     data-name="{{ person.name | lower }}"
     data-level="{{ level_num }}"
     data-alloc="{{ alloc_key }}">
    <div class="avatar av-{{ _av_idx }}">{{ _initials }}</div>
    <div class="person-info">
      <div class="person-name">{{ person.name }}</div>
      <div class="person-role">{{ person.role or "" }}{% if person.seniority %} &middot; {{ person.seniority }}{% endif %}</div>
    </div>

    {# Allocation badge #}
    {% if person.alloc_stale_days is not none %}
      <span class="badge warn">alloc: STALE {{ person.alloc_stale_days }}d</span>
    {% elif person.current_allocation_type == "bench" %}
      <span class="badge muted">BENCH</span>
    {% elif person.current_allocation_label %}
      <span class="badge alloc">{{ person.current_allocation_label }}</span>
    {% else %}
      <span class="badge muted">no alloc</span>
    {% endif %}

    {# 1:1 badge #}
    {% if person.one_on_one_days_ago is none %}
      <span class="badge warn">1:1 never</span>
    {% elif person.one_on_one_overdue %}
      <span class="badge danger">1:1 OVERDUE</span>
    {% elif person.one_on_one_days_until is not none %}
      <span class="badge ok">1:1 in {{ person.one_on_one_days_until }}d</span>
    {% else %}
      <span class="badge muted">1:1 {{ person.one_on_one_days_ago }}d ago</span>
    {% endif %}

    {# Action items badge #}
    {% if person.open_action_items_count > 0 %}
      <span class="badge warn">{{ person.open_action_items_count }} open</span>
    {% else %}
      <span class="badge muted">0 open</span>
    {% endif %}
  </a>
  {% else %}
  <p class="empty">No active people yet. <a href="/people/new">Add the first one.</a></p>
  {% endfor %}
</div>

<script>
(function () {
  const list = document.getElementById('people-list');
  let currentSort = 'name';
  let currentDir = 1;

  function sortRows(key, dir) {
    const rows = Array.from(list.querySelectorAll('.person-row'));
    rows.sort((a, b) => {
      const av = a.dataset[key];
      const bv = b.dataset[key];
      const an = parseFloat(av);
      const bn = parseFloat(bv);
      if (!isNaN(an) && !isNaN(bn)) return dir * (an - bn);
      return dir * av.localeCompare(bv);
    });
    rows.forEach(r => list.appendChild(r));
  }

  document.querySelectorAll('.sort-btn').forEach(btn => {
    btn.addEventListener('click', () => {
      const key = btn.dataset.sort;
      if (key === currentSort) {
        currentDir *= -1;
      } else {
        currentSort = key;
        currentDir = key === 'alloc' ? -1 : 1;
      }
      document.querySelectorAll('.sort-btn').forEach(b => b.classList.remove('active'));
      btn.classList.add('active');
      sortRows(currentSort, currentDir);
    });
  });
})();
</script>
{% endblock %}
```

- [ ] **Step 2: Verify in browser**

Open http://localhost:8080/people — each person row should show a colored initials circle. Sort buttons should still work. "People" nav link in header should be bold/white (active state).

- [ ] **Step 3: Commit**

```bash
git add app/src/cadencia/web/templates/people_list.html
git commit -m "feat(ui): add initials avatars and colored badges to people list"
```

---

## Task 6: Update person_detail.html — 48px avatar in person header

**Files:**
- Modify: `app/src/cadencia/web/templates/person_detail.html`

Add a larger initials avatar beside the person's name and wrap name+meta in `.person-header-info`. Mark the People nav link as active.

- [ ] **Step 1: Replace the person-header block (lines 1–33 of current file)**

Replace the `{% extends %}` line through the closing `</div>` of `.person-header` with:

```html
{% extends "base.html" %}
{% block title %}{{ overview.name }} | Cadencia{% endblock %}
{% block nav_people %}active{% endblock %}

{% block content %}
<a class="back-link" href="/people">&larr; People</a>

{% set _parts = overview.name.split() %}
{% if _parts | length >= 2 %}
  {% set _initials = (_parts[0][0] ~ _parts[1][0]) | upper %}
{% else %}
  {% set _initials = overview.name[:2] | upper %}
{% endif %}
{% set _av_idx = (overview.name | length) % 6 %}

<div class="person-header">
  <div class="avatar avatar-lg av-{{ _av_idx }}">{{ _initials }}</div>
  <div class="person-header-info">
    <h2>{{ overview.name }}</h2>
    <div class="meta">
      {% if overview.role %}{{ overview.role }}{% endif %}
      {% if overview.seniority %}&nbsp;&middot;&nbsp;{{ overview.seniority }}{% endif %}
      {% if overview.start_date %}&nbsp;&middot;&nbsp;Since {{ overview.start_date }}{% endif %}
      &nbsp;&middot;&nbsp; 1:1
      <span id="cadence-widget">
        every
        {% if overview.one_on_one_cadence_days %}
          <strong>{{ overview.one_on_one_cadence_days }}d</strong>
        {% else %}
          <strong>{{ global_oo_cadence }}d</strong> <span style="color:var(--muted);font-size:12px;">(global)</span>
        {% endif %}
        <button class="edit-btn"
          hx-get="/people/{{ overview.person_id }}/cadence-edit-form"
          hx-target="#cadence-widget"
          hx-swap="outerHTML">edit</button>
      </span>
      {% if overview.recurrence_weekday is not none %}
      <span style="font-size:12px; color:var(--muted); margin-left:4px;">
        ({% set days = ["Mon","Tue","Wed","Thu","Fri","Sat","Sun"] %}{{ days[overview.recurrence_weekday] }}{% if overview.recurrence_week_of_month %}, {% if overview.recurrence_week_of_month == -1 %}last{% elif overview.recurrence_week_of_month == 1 %}1st{% elif overview.recurrence_week_of_month == 2 %}2nd{% elif overview.recurrence_week_of_month == 3 %}3rd{% else %}4th{% endif %} of month{% endif %})
      </span>
      {% endif %}
    </div>
  </div>
  <a href="/people/{{ overview.person_id }}/edit" class="btn" style="margin-left:auto;">Edit</a>
</div>
```

- [ ] **Step 2: Verify in browser**

Open a person detail page (e.g. http://localhost:8080/people). Click a person — you should see the 48px avatar beside the name. The edit link should appear as a button on the right.

- [ ] **Step 3: Commit**

```bash
git add app/src/cadencia/web/templates/person_detail.html
git commit -m "feat(ui): add large initials avatar to person detail header"
```

---

## Task 7: Mark Stakeholders nav link as active on stakeholders page

**Files:**
- Modify: `app/src/cadencia/web/templates/stakeholders.html`

- [ ] **Step 1: Add active block to stakeholders template**

Open `app/src/cadencia/web/templates/stakeholders.html`. After the `{% extends "base.html" %}` line, add:

```html
{% block nav_stakeholders %}active{% endblock %}
```

- [ ] **Step 2: Verify in browser**

Open http://localhost:8080/stakeholders — the "Stakeholders" nav link should now appear white/bold (active), while "People" is dim.

- [ ] **Step 3: Commit**

```bash
git add app/src/cadencia/web/templates/stakeholders.html
git commit -m "feat(ui): highlight active nav link on stakeholders page"
```

---

## Task 8: Final visual QA

No file changes. Walk through each page and verify the full refresh is coherent.

- [ ] **Step 1: Light mode check**
  - http://localhost:8080 (dashboard/redirect)
  - http://localhost:8080/people — avatars, colored badges, sort buttons, navy header
  - Click a person — 48px avatar, sections with shadow, action item Done buttons
  - http://localhost:8080/stakeholders — active nav, consistent layout

- [ ] **Step 2: Dark mode check**

Force dark mode in your OS settings (or DevTools: Rendering > prefers-color-scheme: dark). Verify:
  - Header is `#172554` (deeper navy, not the same as light)
  - Avatar colors swap to dark variants (navy bg / light text)
  - Badges use dark-tone backgrounds (deep amber, deep green, deep red)
  - No white text on white background, no invisible elements

- [ ] **Step 3: Forms check**

Open http://localhost:8080/people/new — form fields should have Inter font, focus ring in navy.

- [ ] **Step 4: Commit if any fixups were needed, otherwise done**
