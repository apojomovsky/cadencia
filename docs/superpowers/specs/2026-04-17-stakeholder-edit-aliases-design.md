# Stakeholder Edit + Aliases Design

**Date:** 2026-04-17
**Status:** Approved

## Summary

Add a web edit page for stakeholders and introduce an aliases feature. Aliases are alternate names a stakeholder is known by (e.g. "Agus" for "Agustin Alba Chicar"). They are stored as a JSON array on the stakeholders table and are resolved interchangeably with the canonical name in both the web UI and MCP tools.

## Data Layer

### Migration

New file `008_stakeholder_aliases.sql`:

```sql
ALTER TABLE stakeholders ADD COLUMN aliases TEXT NOT NULL DEFAULT '[]';
```

### Model changes (`models/stakeholders.py`)

Add `aliases: list[str] = []` to `Stakeholder` and `CreateStakeholderInput`. Add `aliases: list[str] | None = None` to `UpdateStakeholderInput`.

`UpdateStakeholderInput.aliases` uses `None` as sentinel for "not provided" (same pattern as other optional fields), so an explicit empty list clears all aliases.

### Service changes (`services/stakeholders.py`)

- `_row_to_stakeholder`: parse `aliases` via `json.loads(r.get("aliases", "[]"))`
- `create_stakeholder`: serialize `aliases` via `json.dumps(data.aliases)`
- `update_stakeholder`: include aliases in the partial-update SET block when `data.aliases is not None`
- New function `find_stakeholder_by_name_or_alias(conn, query, owner_id)`:
  - Case-insensitive exact match on `name` first
  - Falls back to `json_each(aliases)` scan for alias match
  - Returns `list[Stakeholder]` (may match multiple if names collide)

## MCP Layer

New tool `find_stakeholder(name_or_alias: str)` in `cadencia_mcp/server.py`:
- Calls `find_stakeholder_by_name_or_alias`
- Returns list of matches as dicts (id, name, aliases, type, organization)
- Used to resolve a name/alias to an ID before calling other stakeholder tools

No changes to existing MCP tools.

## Web UI

### Stakeholder list (`stakeholders.html`)

Each row gains alias display after the name:

```
Agustin Alba Chicar  Agus, Agus Alba   [client]   [REDACTED]
```

Aliases rendered as muted text or small pills, whichever fits.

### Create form

Existing form gains an `aliases` field: a plain text input with placeholder `"Nicknames, e.g. Agus, Gonzo"`. Comma-separated on submit, split+stripped server-side.

### Edit page (new)

`GET /stakeholders/{id}/edit` renders `stakeholder_edit.html` with the stakeholder pre-filled.
`POST /stakeholders/{id}` processes the form and redirects to `/stakeholders`.

Form fields: Name (required), Type (select), Organization, Aliases (comma-separated text), Notes (text). Uses `.person-form` CSS class for consistency with person edit.

### Router additions

```python
@router.get("/stakeholders/{stakeholder_id}/edit")
@router.post("/stakeholders/{stakeholder_id}")
```

Both import and call `update_stakeholder` from the service layer. The POST handler parses aliases from the `aliases` form field (split on `,`, strip whitespace, drop empty strings).

## Files Changed

| File | Change |
|------|--------|
| `app/src/cadencia/db/sql/008_stakeholder_aliases.sql` | New migration |
| `app/src/cadencia/models/stakeholders.py` | Add `aliases` to all three models |
| `app/src/cadencia/services/stakeholders.py` | Parse/write aliases, add `find_stakeholder_by_name_or_alias` |
| `app/src/cadencia/web/router.py` | Add GET+POST edit routes, import `update_stakeholder` |
| `app/src/cadencia/web/templates/stakeholders.html` | Show aliases in list row, add aliases field to create form |
| `app/src/cadencia/web/templates/stakeholder_edit.html` | New edit page |
| `mcp/src/cadencia_mcp/server.py` | Add `find_stakeholder` tool |
| `app/tests/services/test_stakeholders.py` | Tests for alias CRUD and find-by-alias |

## Testing

- `test_create_stakeholder_with_aliases`: create with aliases, verify stored and returned
- `test_update_stakeholder_aliases`: update aliases, verify changed
- `test_clear_stakeholder_aliases`: update with `aliases=[]`, verify cleared
- `test_find_by_name`: exact name match returns correct stakeholder
- `test_find_by_alias`: alias match returns correct stakeholder
- `test_find_case_insensitive`: "gonzo" matches "Gonzo"
- Existing tests unaffected

## Out of Scope

- No alias uniqueness enforcement across stakeholders
- No fuzzy/partial matching in `find_stakeholder_by_name_or_alias`
- No alias display in stakeholder feedback section (feedback already shows stakeholder name)
- No delete-stakeholder feature
