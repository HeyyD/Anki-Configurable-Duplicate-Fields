# AGENTS.md

## Project Overview

Anki desktop add-on ("Configurable Duplicate Fields") that extends Anki's duplicate checking so users can configure which note fields are checked for duplicates, instead of only the first field. Forked from https://github.com/matthayes/anki_flex_dupes (functionality is completely different). Licensed under AGPL-3.0 — keep the license header at the top of `__init__.py`.

## Commands

- `make init` — install dev dependencies (`requirements.txt`: flake8, pytest)
- `make flake8` (or just `flake8`) — lint; this is the CI gate (`.travis.yml`)
- `make release` / `python release.py` — package the add-on into `target/configurable_duplicate_fields.ankiaddon` (pure-Python zipping, works without a `zip` binary)

There is no test suite; pytest is listed in requirements but unused. Verification is done via `flake8` and manual testing inside Anki.

## Code Layout

- `__init__.py` — add-on entry point; imports `setup()` from the package and calls it
- `manifest.json` — Anki manifest (`package: configurable_duplicate_fields`)
- `config.json` — default user-facing config: `{ "field_names": [...], "exclude_own_note": true }`
- `configurable_duplicate_fields/__init__.py` — editor-side duplicate checking (`check_duplicate`, `is_duplicate`, `show_dupes`) and `setup()`
- `configurable_duplicate_fields/config.py` — config cache (`load_config` / `save_config` / `get_field_names` / `get_exclude_own_note`), its keys, and the Tools-menu config dialog (`FieldNamesDialog` / `open_config_dialog`)
- `configurable_duplicate_fields/find_duplicates.py` — collection-wide duplicate scan: `DuplicateReportDialog` (optional search filter, Open All in Browser), `find_duplicate_groups`, and the Browser Notes-menu hook (`install_browser_menu_action`)
- `release.py` — build script; zips `__init__.py`, `manifest.json`, and the whole `configurable_duplicate_fields/` directory (skipping `__pycache__`/`.pyc`) into `target/configurable_duplicate_fields.ankiaddon`

## Architecture Notes

Anki desktop internals reference: https://github.com/ankitects/anki (`qt/aqt/...`; `_aqt/hooks.py` is build-generated and not in the repo). Desktop installs ship `.pyc`-only bytecode for `aqt`/`_aqt` — class/method names, `co_varnames`, and embedded type strings can be dumped with `marshal` from the local installation when behavior needs verifying.

The add-on works by wrapping (monkey-patching) Anki internals with `anki.hooks.wrap(..., "around")` in `setup()`:

- `Editor._check_and_update_duplicate_display_async` → `check_duplicate` — re-runs duplicate detection asynchronously via `QueryOp` and highlights configured fields in the editor web view (`setBackgrounds`)
- `Note.fields_check` → `is_duplicate` — appends ordinals of duplicate-configured fields to Anki's normal result tuple
- `Editor.showDupes` → `show_dupes` — opens the browser with a search query combining Anki's native dupe search (`dupe:<notetype-id>,<first-field>`) and custom queries built as `"fieldname:value"` per configured field

Tools menu → "Configurable Duplicate Fields" submenu containing only:

- "Config..." → `FieldNamesDialog` — GUI editor for the field list plus an *Exclude current note from duplicate search results* checkbox; saves via `mw.addonManager.writeConfig` (through `save_config`) and refreshes the in-memory cache so changes apply without restarting Anki

Browser window Notes menu → "(Configured Duplicates) Find duplicates..." → `open_find_duplicates_dialog`, inserted directly below Anki's native "Find Duplicates" entry (`_install_browser_menu_action` registers `_add_find_duplicates_menu_action` on the official `gui_hooks.browser_menus_did_init` hook — current releases pass only `(browser)`, older ones `(menu, browser)`, so the callback takes `*args` and reads the browser from the last arg; the menu is resolved as `browser.form.menu_Notes` with legacy `menuNotes` fallback, and positioning uses `browser.form.actionFindDuplicates`, then text matching, then appends at the end; if the hook itself is unavailable, the action is added to the Tools submenu instead). The dialog and its `QueryOp` are parented to the Browser window (not `mw`) so the main window is not raised, and it is shown non-modally (`show()` with a reference kept on the parent). It scans the whole collection (`col.db.execute("select id, mid, flds from notes")`) inside a background `QueryOp`, groups notes by value checksum across ALL configured field names (so differently named fields with equal values group together, matching the editor-side `"name:value"` OR-query semantics), and shows groups with > 1 note in `DuplicateReportDialog`; the dialog owns the scan (`run_scan` → `find_duplicate_groups(col, search_filter)`; an optional filter line edit limits the scan to notes matching a Browser-syntax query via `col.find_notes`, re-runnable via Search button or Enter, with invalid searches reported through a QueryOp failure handler attached via the `.failure()` builder method (newer releases removed the `failure=` constructor kwarg)) and clicking a group — or the *Open All in Browser* button for every group's notes at once — opens the Browser with a comma-separated `nid:` query (`_nids_search_query`; chunked with `or` beyond 1000 nids to stay under SQLite's expression-tree depth limit).

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
