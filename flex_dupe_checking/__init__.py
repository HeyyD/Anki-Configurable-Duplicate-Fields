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

# When this is appended to the names of fields, then those fields are considered along with the
# first field when checking for duplicates in the editor.
KEY_SUFFIX = "_pk"

anki_patch_version = int(anki_version.split(".")[-1])

# Starting with version 20, Anki uses a class to mark the duplicate field.
if anki_patch_version < 20:
    use_color_code = True
else:
    use_color_code = False


def dupeOrEmptyWithOrds(self):
    """
    Returns a tuple. The contents of each element are as follows:

    1) 1 if first is empty; 2 if first is a duplicate, False otherwise.
    2) For a duplicate (2), this returns the list of ordinals that make up the key.
       Otherwise this is None.
    """
    val = self.fields[0]
    if not val.strip():
        return 1, None
    csum = field_checksum(val)
    # find any matching csums and compare
    for flds in self.col.db.list(
            "select flds from notes where csum = ? and id != ? and mid = ?",
            csum, self.id or 0, self.mid):

        model = self.model()
        field_ords = [0]
        for fld in model["flds"]:
            if fld["ord"] == 0:
                continue
            elif fld["name"].endswith(KEY_SUFFIX):
                field_ords.append(fld["ord"])

        all_fields_equal = True
        fields_split = split_fields(flds)
        for field_ord in field_ords:
            if strip_html_media(fields_split[field_ord]) != strip_html_media(self.fields[field_ord]):
                all_fields_equal = False

        if all_fields_equal:
            return 2, field_ords

    return False, None


def checkValid(self):
    """
    Check if the note in the editor has duplicates.  If so, it will highlight the fields that make
    up the note's key.
    """
    print("Checking valid")
    cols = []
    err = None
    for f in self.note.fields:
        if use_color_code:
            cols.append("#fff")
        else:
            cols.append("")
    err, field_ords = dupeOrEmptyWithOrds(self.note)
    if err == 2:
        for i in field_ords:
            if use_color_code:
                cols[i] = "#fcc"
            else:
                cols[i] = "dupe"
        self.web.eval("showDupes();")
    else:
        self.web.eval("hideDupes();")
    self.web.eval("setBackgrounds(%s);" % json.dumps(cols))


def dupeOrEmpty(self):
    """
    Returns 1 if first is empty; 2 if first is a duplicate, False otherwise.
    """
    res, field_ords = dupeOrEmptyWithOrds(self)
    print(res)

    return res


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

def test(self) -> None:
    print("Test")
    cols = [""] * len(self.note.fields)
    cloze_hint = ""
    if result == NoteFieldsCheckResult.DUPLICATE:
        cols[0] = "dupe"
    elif result == NoteFieldsCheckResult.NOTETYPE_NOT_CLOZE:
        cloze_hint = tr.adding_cloze_outside_cloze_notetype()
    elif result == NoteFieldsCheckResult.FIELD_NOT_CLOZE:
        cloze_hint = tr.adding_cloze_outside_cloze_field()

    self.web.eval(
        'require("anki/ui").loaded.then(() => {'
        f"setBackgrounds({json.dumps(cols)});\n"
        f"setClozeHint({json.dumps(cloze_hint)});\n"
        "}); "
    )

def isDuplicate(self, _old) -> None:
    result = _old(self)
    print(result == NoteFieldsCheckResult.DUPLICATE)

    return result


def setup():
    print("Setting up dupe checking")
    # Editor._update_duplicate_display = wrap(Editor._update_duplicate_display, test, "around")
    Note.fields_check = wrap(Note.fields_check, isDuplicate, "around")
    # Note.fields_check = wrap(Note.fields_check, dupeOrEmpty, "after")
    # Editor.showDupes = showDupes
    # Editor._links["dupes"] = showDupes
