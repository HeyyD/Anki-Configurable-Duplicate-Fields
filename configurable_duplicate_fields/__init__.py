import json

import aqt

from aqt import mw
from anki.hooks import wrap
from anki.notes import Note, NoteFieldsCheckResult
from aqt.editor import Editor
from aqt.operations import QueryOp
from aqt.qt import QAction, QMenu
from aqt.utils import tr

from .config import (
    get_exclude_own_note,
    get_field_names,
    load_config,
    open_config_dialog,
)
from .find_duplicates import (
    BROWSER_FIND_DUPLICATES_LABEL,
    install_browser_menu_action,
    open_find_duplicates_dialog,
)


def on_config_updated(_new_config) -> None:
    load_config()


def update_duplicate_display(self, first_field_result, duplicate_fields) -> None:
    cols = [""] * len(self.note.fields)
    cloze_hint = ""
    if first_field_result == NoteFieldsCheckResult.DUPLICATE:
        cols[0] = "dupe"
    elif first_field_result == NoteFieldsCheckResult.NOTETYPE_NOT_CLOZE:
        cloze_hint = tr.adding_cloze_outside_cloze_notetype()
    elif first_field_result == NoteFieldsCheckResult.FIELD_NOT_CLOZE:
        cloze_hint = tr.adding_cloze_outside_cloze_field()

    for field_ord in duplicate_fields:
        cols[field_ord] = "dupe"

    self.web.eval(
        'require("anki/ui").loaded.then(() => {'
        f"setBackgrounds({json.dumps(cols)});\n"
        f"setClozeHint({json.dumps(cloze_hint)});\n"
        "}); "
    )


def check_duplicate(self, _old) -> None:
    note = self.note
    if not note:
        return

    def on_done(result: tuple) -> None:
        first_field_result, duplicate_fields = result
        if self.note != note:
            return
        update_duplicate_display(self, first_field_result, duplicate_fields)

    QueryOp(
        parent=self.parentWindow,
        op=lambda _: note.fields_check(),
        success=on_done,
    ).run_in_background()


def get_primary_key_field_orders(self) -> list:
    note_type = self.note_type()
    field_names = get_field_names()

    field_ords = []
    for fld in note_type["flds"]:
        if fld["name"] in field_names:
            field_ords.append(fld["ord"])

    return field_ords


def create_search_query(self, exclude_own_note=True) -> str:
    nid = self.id
    primary_key_cols = get_primary_key_field_orders(self)
    queries = []

    for order in primary_key_cols:
        if not self.fields[order].strip():
            continue
        val = self.fields[order]
        for name in get_field_names():
            queries.append("\"%s:%s\"" % (name, val))

    if len(queries) == 0:
        return ""

    prefix = "-nid:%s " % nid if nid != 0 and exclude_own_note else ""
    return "%s(%s)" % (prefix, " OR ".join(queries))


def is_duplicate(self, _old) -> tuple:
    cols = get_primary_key_field_orders(self)
    orders = []

    query = create_search_query(self)
    if query != "":
        for order in cols:
            if len(self.col.find_cards(create_search_query(self))) != 0:
                orders.append(order)

    return _old(self), orders


def show_dupes(self, _old) -> None:
    note = self.note
    if not note:
        return

    first_field_result, duplicate_fields = note.fields_check()
    query = ""
    exclude_own_note = get_exclude_own_note()

    if first_field_result == NoteFieldsCheckResult.DUPLICATE and len(duplicate_fields) == 0:
        _old(self)
        return
    elif first_field_result == NoteFieldsCheckResult.DUPLICATE and len(duplicate_fields) != 0:
        query = "dupe:%s,%s OR (%s)" % (
            note.note_type()["id"], note.fields[0], create_search_query(note, exclude_own_note))
    else:
        query = create_search_query(note, exclude_own_note)

    browser = aqt.dialogs.open("Browser", self.mw)
    browser.form.searchEdit.lineEdit().setText(query)
    browser.onSearchActivated()


def setup():
    print("Setting up duplicate checking...")
    Editor._check_and_update_duplicate_display_async = wrap(
        Editor._check_and_update_duplicate_display_async, check_duplicate, "around")
    Note.fields_check = wrap(Note.fields_check, is_duplicate, "around")
    Editor.showDupes = wrap(Editor.showDupes, show_dupes, "around")

    load_config()

    tools_menu = QMenu("&Configurable Duplicate Fields", mw)

    configure_action = QAction("&Config...", mw)
    configure_action.triggered.connect(open_config_dialog)
    tools_menu.addAction(configure_action)
    mw.form.menuTools.addMenu(tools_menu)

    if not install_browser_menu_action():
        find_duplicates_action = QAction(BROWSER_FIND_DUPLICATES_LABEL, mw)
        find_duplicates_action.triggered.connect(open_find_duplicates_dialog)
        tools_menu.addAction(find_duplicates_action)

    mw.addonManager.setConfigUpdatedAction(__name__, on_config_updated)
