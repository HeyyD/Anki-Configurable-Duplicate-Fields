# Anki Flexible Dupe Checing
# Copyright (C) 2019-2020 Matthew Hayes

# This program is free software: you can redistribute it and/or modify
# it under the terms of the GNU Affero General Public License as published by
# the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.

# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU Affero General Public License for more details.

# You should have received a copy of the GNU Affero General Public License
# along with this program.  If not, see <http://www.gnu.org/licenses/>.

import json

import aqt
from anki import version as anki_version
from anki.hooks import wrap
from anki.notes import Note, NoteFieldsCheckResult
from anki.utils import field_checksum, strip_html_media, split_fields
from aqt.editor import Editor
from aqt.operations import QueryOp
from aqt.utils import tr

# When this is appended to the names of fields, then those fields are considered along with the
# first field when checking for duplicates in the editor.
KEY_SUFFIX = "_pk"

def showDupes(self):
    """
    Shows the duplicates for the current note in the editor by conducting a search in the browser.

    This basically performs the normal dupes search that Anki does but appends additional search
    terms for other keys that have the _pk suffix.
    """
    print("Show dupes")
    contents = strip_html_media(self.note.fields[0])
    browser = aqt.dialogs.open("Browser", self.mw)

    model = self.note.model()

    # Find other notes with the same content for the first field.
    search_cmds = [
        '"dupe:%s,%s"' % (model['id'], contents)
    ]

    # If any other field names end in the special suffix, then they are considered part of the "key"
    # that uniquely identifies a note.  Search for notes that have the same content for these fields,
    # in addition to having the first field match.
    for fld in model["flds"]:
        # First field is already filtered on by the dupe check.
        if fld["ord"] == 0:
            continue
        elif fld["name"].endswith(KEY_SUFFIX):
            term = strip_html_media(self.note.fields[fld["ord"]])
            cmd_args = (fld["name"], term)
            if '"' in term and "'" in term:
                # ignore, unfortunately we can't search for it
                pass
            elif '"' in term:
                search_cmds.append("%s:'%s'" % cmd_args)
            else:
                search_cmds.append("%s:\"%s\"" % cmd_args)

    browser.form.searchEdit.lineEdit().setText(" ".join(search_cmds))
    browser.onSearchActivated()

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

    field_ords = []
    for fld in note_type["flds"]:
        if fld["ord"] == 0:
            continue
        elif fld["name"].endswith(KEY_SUFFIX):
            field_ords.append(fld["ord"])

    return field_ords

def is_duplicate(self, _old) -> tuple:
    primary_key_cols = get_primary_key_field_orders(self)
    columns = []

    for order in primary_key_cols:
        if not self.fields[order].strip():
            continue
        val = self.fields[order]
        for fields in self.col.db.list("select flds from notes where flds LIKE ? and id != ?", "%" + val + "%", self.id or 0):
            for field in split_fields(fields):
                normalized = strip_html_media(field)
                if field_checksum(normalized) == field_checksum(val):
                    columns.append(order)

    return _old(self), columns

def setup():
    print("Setting up duplicate checking...")
    Editor._check_and_update_duplicate_display_async = wrap(Editor._check_and_update_duplicate_display_async, check_duplicate, "around")
    Note.fields_check = wrap(Note.fields_check, is_duplicate, "around")
    # Editor.showDupes = showDupes
    # Editor._links["dupes"] = showDupes
