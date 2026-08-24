# When this is appended to the names of fields, then those fields are considered along with the
# first field when checking for duplicates in the editor.

from aqt import mw
from aqt.qt import (
    QCheckBox,
    QDialog,
    QHBoxLayout,
    QLabel,
    QPlainTextEdit,
    QPushButton,
    QVBoxLayout,
)
from aqt.utils import showWarning, tooltip

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
