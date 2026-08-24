import html

import aqt

from aqt import mw, gui_hooks
from anki.utils import field_checksum, split_fields, strip_html_media
from aqt.operations import QueryOp
from aqt.qt import (
    QAction,
    QDialog,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QPushButton,
    QTextBrowser,
    QVBoxLayout,
)
from aqt.utils import showWarning

from .config import get_field_names

BROWSER_FIND_DUPLICATES_LABEL = "(Configured Duplicates) Find &duplicates..."


class DuplicateReportDialog(QDialog):
    def __init__(self, parent=None):
        super().__init__(parent or mw)
        self.setWindowTitle("(Configured Duplicates) Find Duplicates")
        self.duplicate_groups = []
        layout = QVBoxLayout(self)

        filter_layout = QHBoxLayout()
        filter_layout.addWidget(QLabel("Limit to notes matching this search (optional):", self))
        self.filter_edit = QLineEdit(self)
        self.filter_edit.setPlaceholderText("e.g. deck:current tag:leech")
        self.filter_edit.returnPressed.connect(self.run_scan)
        filter_layout.addWidget(self.filter_edit, 1)
        self.search_button = QPushButton("Search", self)
        self.search_button.clicked.connect(self.run_scan)
        filter_layout.addWidget(self.search_button)
        layout.addLayout(filter_layout)

        self.summary_label = QLabel("Scanning collection...", self)
        layout.addWidget(self.summary_label)

        self.report_view = QTextBrowser(self)
        self.report_view.setOpenLinks(False)
        self.report_view.anchorClicked.connect(self.open_group_in_browser)
        layout.addWidget(self.report_view)

        button_layout = QHBoxLayout()
        self.open_all_button = QPushButton("Open All in Browser", self)
        self.open_all_button.setEnabled(False)
        self.open_all_button.clicked.connect(self.open_all_in_browser)
        button_layout.addWidget(self.open_all_button)
        button_layout.addStretch()
        close_button = QPushButton("Close", self)
        close_button.clicked.connect(self.reject)
        button_layout.addWidget(close_button)
        layout.addLayout(button_layout)

        self.resize(520, 460)
        self.run_scan()

    def run_scan(self) -> None:
        search_filter = self.filter_edit.text().strip()
        self.search_button.setEnabled(False)

        def on_done(result: tuple) -> None:
            try:
                self.set_results(*result)
                self.search_button.setEnabled(True)
            except RuntimeError:
                return

        def on_failure(exc: Exception) -> None:
            try:
                showWarning(
                    "The search filter could not be applied:\n%s\n\n"
                    "Clear the filter to scan the whole collection again." % exc,
                    parent=self)
                self.search_button.setEnabled(True)
            except RuntimeError:
                return

        query_op = QueryOp(
            parent=self,
            op=lambda col: find_duplicate_groups(col, search_filter),
            success=on_done,
        )
        if hasattr(query_op, "failure"):
            query_op = query_op.failure(on_failure)
        query_op.run_in_background()

    def set_results(self, duplicate_groups, scanned_note_count) -> None:
        self.duplicate_groups = duplicate_groups
        if duplicate_groups:
            summary_text = "%d duplicate groups found while scanning %d notes." % (
                len(duplicate_groups), scanned_note_count)
        else:
            summary_text = "No duplicates found while scanning %d notes." % scanned_note_count
        self.summary_label.setText(summary_text)
        self.report_view.setHtml(self.build_report_html(duplicate_groups))
        self.open_all_button.setEnabled(bool(duplicate_groups))

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
        self.open_search_in_browser(self._nids_search_query(fragment.split(",")))

    def open_all_in_browser(self) -> None:
        nids = [nid for group in self.duplicate_groups for nid in group["nids"]]
        if nids:
            self.open_search_in_browser(self._nids_search_query(nids))

    @staticmethod
    def _nids_search_query(nids) -> str:
        nids = [str(nid) for nid in nids]
        if len(nids) <= 1000:
            return "nid:" + ",".join(nids)
        chunks = (nids[index:index + 1000] for index in range(0, len(nids), 1000))
        return " or ".join("nid:" + ",".join(chunk) for chunk in chunks)

    @staticmethod
    def open_search_in_browser(query) -> None:
        browser = aqt.dialogs.open("Browser", mw)
        browser.form.searchEdit.lineEdit().setText(query)
        browser.onSearchActivated()


def find_duplicate_groups(col, search_filter="") -> tuple:
    configured_names = set(get_field_names())
    allowed_nids = None
    if search_filter:
        allowed_nids = set(col.find_notes(search_filter))
    groups = {}
    scanned_note_count = 0

    for nid, mid, flds in col.db.execute("select id, mid, flds from notes"):
        if allowed_nids is not None and nid not in allowed_nids:
            continue
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


def open_find_duplicates_dialog(parent=None) -> None:
    parent = parent or mw
    dialog = DuplicateReportDialog(parent)
    parent._configurable_dupes_report_dialog = dialog
    dialog.show()
    dialog.raise_()
    dialog.activateWindow()


def install_browser_menu_action() -> bool:
    try:
        gui_hooks.browser_menus_did_init.append(_add_find_duplicates_menu_action)
    except (AttributeError, TypeError):
        print("Configurable Duplicate Fields: could not hook the Browser window; "
              "keeping Find Duplicates in the Tools menu.")
        return False
    return True


def _add_find_duplicates_menu_action(*args) -> None:
    if not args:
        return
    browser = args[-1]
    form = getattr(browser, "form", None)
    notes_menu = getattr(form, "menu_Notes", None)
    if notes_menu is None:
        notes_menu = getattr(form, "menuNotes", None)
    if notes_menu is None:
        return

    action = QAction(BROWSER_FIND_DUPLICATES_LABEL, browser)
    action.setToolTip("Find duplicates across all configured duplicate-check fields.")
    action.triggered.connect(lambda checked=False, parent=browser: open_find_duplicates_dialog(parent))

    vanilla_action = getattr(form, "actionFindDuplicates", None)
    if vanilla_action is None:
        vanilla_action = _find_vanilla_find_duplicates_action(notes_menu)

    if vanilla_action is None:
        notes_menu.addAction(action)
        return

    menu_actions = notes_menu.actions()
    position = menu_actions.index(vanilla_action)
    following_action = menu_actions[position + 1] if position + 1 < len(menu_actions) else None
    if following_action is None:
        notes_menu.addAction(action)
    else:
        notes_menu.insertAction(following_action, action)


def _find_vanilla_find_duplicates_action(notes_menu):
    for action in notes_menu.actions():
        text = str(action.text() or "").replace("&", "").strip().lower()
        if "find duplicates" in text or text == "finddupes":
            return action
    return None
