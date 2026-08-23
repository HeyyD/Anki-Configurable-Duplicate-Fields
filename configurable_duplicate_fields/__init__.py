import html
import json
import aqt

from aqt import mw
from anki.hooks import wrap
from anki.notes import Note, NoteFieldsCheckResult
from anki.utils import field_checksum, split_fields, strip_html_media
from aqt.editor import Editor
from aqt.operations import QueryOp
from aqt.qt import (
    QAction,
    QCheckBox,
    QDialog,
    QHBoxLayout,
    QLabel,
    QMenu,
    QPlainTextEdit,
    QPushButton,
    QTextBrowser,
    QVBoxLayout,
)
from aqt.utils import showWarning, tooltip, tr

# When this is appended to the names of fields, then those fields are considered along with the
# first field when checking for duplicates in the editor.

FIELD_NAMES_CONFIG_KEY = "field_names"
EXCLUDE_OWN_NOTE_CONFIG_KEY = "exclude_own_note"
DEFAULT_EXCLUDE_OWN_NOTE = True

_config = None


def load_config() -> dict:
    global _config
    _config = mw.addonManager.getConfig(__name__) or {}
    return _config


def save_config(updates: dict) -> None:
    if _config is None:
        load_config()
    _config.update(updates)
    mw.addonManager.writeConfig(__name__, _config)


def get_field_names() -> list:
    if _config is None:
        load_config()
    names = []
    for raw_name in _config.get(FIELD_NAMES_CONFIG_KEY, []):
        name = str(raw_name).strip()
        if name and name not in names:
            names.append(name)
    return names


def get_exclude_own_note() -> bool:
    if _config is None:
        load_config()
    return bool(_config.get(EXCLUDE_OWN_NOTE_CONFIG_KEY, DEFAULT_EXCLUDE_OWN_NOTE))


class FieldNamesDialog(QDialog):
    def __init__(self):
        super().__init__(mw)
        self.setWindowTitle("Configurable Duplicate Fields")
        layout = QVBoxLayout(self)

        layout.addWidget(QLabel("Field names to check for duplicates (one name per line):", self))
        self.field_names_edit = QPlainTextEdit(self)
        self.field_names_edit.setPlainText("\n".join(get_field_names()))
        layout.addWidget(self.field_names_edit)

        self.exclude_own_note_box = QCheckBox("Exclude current note from duplicate search results", self)
        self.exclude_own_note_box.setChecked(get_exclude_own_note())
        self.exclude_own_note_box.setToolTip(
            "Checked (default): searches exclude the note being edited, as before.\n"
            "Unchecked: the original note is included in the results so you can\n"
            "compare it against its duplicates directly.")
        layout.addWidget(self.exclude_own_note_box)

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
        save_config({
            FIELD_NAMES_CONFIG_KEY: field_names,
            EXCLUDE_OWN_NOTE_CONFIG_KEY: self.exclude_own_note_box.isChecked(),
        })
        tooltip("Configuration saved. Changes are active immediately.")
        QDialog.accept(self)


def open_config_dialog() -> None:
    FieldNamesDialog().exec()


def on_config_updated(_new_config) -> None:
    load_config()


class DuplicateReportDialog(QDialog):
    def __init__(self, duplicate_groups, scanned_note_count):
        super().__init__(mw)
        self.setWindowTitle("Configurable Duplicate Fields")
        layout = QVBoxLayout(self)

        if duplicate_groups:
            summary_text = "%d duplicate groups found while scanning %d notes." % (
                len(duplicate_groups), scanned_note_count)
        else:
            summary_text = "No duplicates found while scanning %d notes." % scanned_note_count
        layout.addWidget(QLabel(summary_text, self))

        self.report_view = QTextBrowser(self)
        self.report_view.setOpenLinks(False)
        self.report_view.setHtml(self.build_report_html(duplicate_groups))
        self.report_view.anchorClicked.connect(self.open_group_in_browser)
        layout.addWidget(self.report_view)

        button_layout = QHBoxLayout()
        button_layout.addStretch()
        close_button = QPushButton("Close", self)
        close_button.clicked.connect(self.reject)
        button_layout.addWidget(close_button)
        layout.addLayout(button_layout)

        self.resize(520, 420)

    @staticmethod
    def build_report_html(duplicate_groups) -> str:
        rows = []
        for group in duplicate_groups:
            nids = ",".join(str(nid) for nid in group["nids"])
            rows.append(
                "<tr><td align=\"right\" width=\"90\">%d notes</td>"
                "<td><a href=\"#%s\">%s</a>&nbsp;<span style=\"color:#777\">(%s)</span></td></tr>"
                % (group["count"], nids, html.escape(group["label"]), html.escape(", ".join(group["names"]))))
        return "<table>%s</table>" % "".join(rows)

    def open_group_in_browser(self, url) -> None:
        fragment = url.fragment()
        if not fragment:
            return
        query = " OR ".join("nid:%s" % part for part in fragment.split(","))
        browser = aqt.dialogs.open("Browser", mw)
        browser.form.searchEdit.lineEdit().setText(query)
        browser.onSearchActivated()


def find_duplicate_groups(col) -> tuple:
    configured_names = set(get_field_names())
    groups = {}
    scanned_note_count = 0

    for nid, mid, flds in col.db.execute("select id, mid, flds from notes"):
        scanned_note_count += 1
        note_type = col.models.get(mid)
        if note_type is None:
            continue
        values = split_fields(flds)
        seen_checksums = set()
        for index, fld in enumerate(note_type["flds"]):
            name = fld["name"]
            if name not in configured_names:
                continue
            value = values[index]
            if not value.strip():
                continue
            checksum = field_checksum(value)
            entry = groups.setdefault(checksum, {
                "label": strip_html_media(value),
                "names": set(),
                "nids": [],
            })
            entry["names"].add(name)
            if checksum not in seen_checksums:
                seen_checksums.add(checksum)
                entry["nids"].append(nid)

    duplicate_groups = []
    for entry in groups.values():
        if len(entry["nids"]) > 1:
            label = entry["label"]
            duplicate_groups.append({
                "label": label if len(label) <= 100 else label[:97] + "...",
                "names": sorted(entry["names"]),
                "count": len(entry["nids"]),
                "nids": entry["nids"],
            })

    duplicate_groups.sort(key=lambda group: (-group["count"], group["label"].casefold()))
    return duplicate_groups, scanned_note_count


def open_find_duplicates_dialog() -> None:
    def on_done(result: tuple) -> None:
        duplicate_groups, scanned_note_count = result
        DuplicateReportDialog(duplicate_groups, scanned_note_count).exec()

    QueryOp(parent=mw, op=lambda col: find_duplicate_groups(col), success=on_done).run_in_background()


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

    menu = QMenu("&Configurable Duplicate Fields", mw)

    configure_action = QAction("Configure...", mw)
    configure_action.triggered.connect(open_config_dialog)
    menu.addAction(configure_action)

    find_duplicates_action = QAction("Find Duplicates...", mw)
    find_duplicates_action.triggered.connect(open_find_duplicates_dialog)
    menu.addAction(find_duplicates_action)

    mw.form.menuTools.addMenu(menu)

    mw.addonManager.setConfigUpdatedAction(__name__, on_config_updated)
