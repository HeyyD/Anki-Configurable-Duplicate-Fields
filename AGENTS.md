# AGENTS.md

## Project Overview

Anki desktop add-on ("Configurable Duplicate Fields") that extends Anki's duplicate checking so users can configure which note fields are checked for duplicates, instead of only the first field. Forked from https://github.com/matthayes/anki_flex_dupes (functionality is completely different). Licensed under AGPL-3.0 — keep the license header at the top of `__init__.py`.

## Commands

- `make init` — install dev dependencies (`requirements.txt`: flake8, pytest)
- `make flake8` (or just `flake8`) — lint; this is the CI gate (`.travis.yml`)
- `make release` / `./release.sh` — package the add-on into `target/configurable_duplicate_fields.zip`

There is no test suite; pytest is listed in requirements but unused. Verification is done via `flake8` and manual testing inside Anki.

## Code Layout

- `__init__.py` — add-on entry point; imports `setup()` from the package and calls it
- `manifest.json` — Anki manifest (`package: configurable_duplicate_fields`)
- `config.json` — default user-facing config: `{ "field_names": [...], "exclude_own_note": true }`
- `configurable_duplicate_fields/__init__.py` — all logic lives in this single module
- `release.sh` — build script; copies `__init__.py`, `manifest.json`, and `configurable_duplicate_fields/__init__.py` into a zip

## Architecture Notes

The add-on works by wrapping (monkey-patching) Anki internals with `anki.hooks.wrap(..., "around")` in `setup()`:

- `Editor._check_and_update_duplicate_display_async` → `check_duplicate` — re-runs duplicate detection asynchronously via `QueryOp` and highlights configured fields in the editor web view (`setBackgrounds`)
- `Note.fields_check` → `is_duplicate` — appends ordinals of duplicate-configured fields to Anki's normal result tuple
- `Editor.showDupes` → `show_dupes` — opens the browser with a search query combining Anki's native dupe search (`dupe:<notetype-id>,<first-field>`) and custom queries built as `"fieldname:value"` per configured field

Tools menu → "Configurable Duplicate Fields" submenu with two actions:

- "Configure..." → `FieldNamesDialog` — GUI editor for the field list plus an *Exclude current note from duplicate search results* checkbox; saves via `mw.addonManager.writeConfig` (through `save_config`) and refreshes the in-memory cache so changes apply without restarting Anki
- "Find Duplicates..." → `open_find_duplicates_dialog` — scans the whole collection (`col.db.execute("select id, mid, flds from notes")`) inside a background `QueryOp`, groups notes by value checksum across ALL configured field names (so differently named fields with equal values group together, matching the editor-side `"name:value"` OR-query semantics), and shows groups with > 1 note in `DuplicateReportDialog`; clicking a group opens the Browser with a `nid:` query

Key behaviors to preserve when editing:

- Config comes from `{field_names, exclude_own_note}`; the raw config dict is cached at startup (`load_config`) and read through `get_field_names()` / `get_exclude_own_note()` everywhere. Never cache values in a module-level constant again, or hot-reload (dialog save and `setConfigUpdatedAction` callback) breaks.
- `create_search_query(self, exclude_own_note=True)` prepends `-nid:<id>` to exclude the note being edited. `is_duplicate` must always exclude it (default), otherwise every field matches its own note and everything is flagged as a dupe. Only `show_dupes` passes the user setting.
- Fields are matched by name against all notetypes (`get_primary_key_field_orders` maps names to field ordinals); empty fields are skipped when building search queries.
- Wrapped functions receive `_old` and must call/return through it (around-wrap convention); results are tuples `(first_field_result, duplicate_field_ords)`.
- Search strings are quoted with embedded double quotes (`"field:value"`) — be careful with escaping.
- Uses both legacy (`anki.hooks`) and modern (`aqt.operations.QueryOp`, `aqt.utils.tr`) Anki APIs; keep compatibility with the current Anki desktop API versions used here.
- Code runs inside Anki's bundled Python; `anki`/`aqt` are not pip-installable dependencies and won't resolve outside Anki.

## Style

- flake8 with `max-line-length = 120` and `ignore = F723` (see `.flake8`)
- Plain Python, no type stubs for anki/aqt; type hints used sparingly where obvious
