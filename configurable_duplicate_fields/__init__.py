import json
import aqt

from aqt import mw
from anki.hooks import wrap
from anki.notes import Note, NoteFieldsCheckResult
from aqt.editor import Editor
from aqt.operations import QueryOp
from aqt.qt import QAction, QDialog, QHBoxLayout, QLabel, QPlainTextEdit, QPushButton, QVBoxLayout
from aqt.utils import showWarning, tooltip, tr

# When this is appended to the names of fields, then those fields are considered along with the
# first field when checking for duplicates in the editor.

FIELD_NAMES_CONFIG_KEY = "field_names"

_field_names = None


def load_field_names() -> list:
    global _field_names
    config = mw.addonManager.getConfig(__name__) or {}
    names = []
    for raw_name in config.get(FIELD_NAMES_CONFIG_KEY, []):
        name = str(raw_name).strip()
        if name and name not in names:
            names.append(name)
    _field_names = names
    return names


def get_field_names() -> list:
    if _field_names is None:
        load_field_names()
    return list(_field_names)


def save_field_names(field_names) -> None:
    global _field_names
    names = []
    for raw_name in field_names:
        name = str(raw_name).strip()
        if name and name not in names:
            names.append(name)
    mw.addonManager.writeConfig(__name__, {FIELD_NAMES_CONFIG_KEY: names})
    _field_names = names


class FieldNamesDialog(QDialog):
    def __init__(self):
        super().__init__(mw)
        self.setWindowTitle("Configurable Duplicate Fields")
        layout = QVBoxLayout(self)

        layout.addWidget(QLabel("Field names to check for duplicates (one name per line):", self))
        self.field_names_edit = QPlainTextEdit(self)
        self.field_names_edit.setPlainText("\n".join(get_field_names()))
        layout.addWidget(self.field_names_edit)

        button_layout = QHBoxLayout()
        button_layout.addStretch()
        save_button = QPushButton("Save", self)
        save_button.clicked.connect(self.accept)
        cancel_button = QPushButton("Cancel", self)
        cancel_button.clicked.connect(self.reject)
        button_layout.addWidget(save_button)
        button_layout.addWidget(cancel_button)
        layout.addLayout(button_layout)

    def accept(self):
        field_names = [line.strip() for line in self.field_names_edit.toPlainText().splitlines() if line.strip()]
        if not field_names:
            showWarning("Please enter at least one field name.", parent=self)
            return
        save_field_names(field_names)
        tooltip("Configuration saved. Changes are active immediately.")
        QDialog.accept(self)


def open_config_dialog() -> None:
    FieldNamesDialog().exec()


def on_config_updated(_config) -> None:
    load_field_names()


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


def create_search_query(self) -> str:
    nid = self.id
    primary_key_cols = get_primary_key_field_orders(self)
    queries = []

    for order in primary_key_cols:
        if not self.fields[order].strip():
            continue
        val = self.fields[order]
        for name in get_field_names():
            queries.append("\"%s:%s\"" % (name, val))

    return "%s(%s)" % ("-nid:%s " % nid if nid != 0 else "", " OR ".join(queries)) if len(queries) != 0 else ""


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

    if first_field_result == NoteFieldsCheckResult.DUPLICATE and len(duplicate_fields) == 0:
        _old(self)
        return
    elif first_field_result == NoteFieldsCheckResult.DUPLICATE and len(duplicate_fields) != 0:
        query = "dupe:%s,%s OR (%s)" % (note.note_type()["id"], note.fields[0], create_search_query(note))
    else:
        query = create_search_query(note)

    browser = aqt.dialogs.open("Browser", self.mw)
    browser.form.searchEdit.lineEdit().setText(query)
    browser.onSearchActivated()


def setup():
    print("Setting up duplicate checking...")
    Editor._check_and_update_duplicate_display_async = wrap(
        Editor._check_and_update_duplicate_display_async, check_duplicate, "around")
    Note.fields_check = wrap(Note.fields_check, is_duplicate, "around")
    Editor.showDupes = wrap(Editor.showDupes, show_dupes, "around")

    load_field_names()

    action = QAction("Configurable Duplicate Fields...", mw)
    action.triggered.connect(open_config_dialog)
    mw.form.menuTools.addAction(action)

    mw.addonManager.setConfigUpdatedAction(__name__, on_config_updated)
