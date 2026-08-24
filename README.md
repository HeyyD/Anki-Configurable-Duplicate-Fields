# Configurable duplicate fields

This modifies Anki's duplicate checking in the editor so that additional fields can be used to check duplicates.

Fields to be checked can be set in *Tools > Configurable Duplicate Fields > Config...* (one field name per line).
Changes are saved to the add-on config and take effect immediately — no restart needed. The same settings can also be
edited by hand via the add-on's JSON config (*Tools > Add-ons > Configurable duplicate fields > Config*):

``` json
{
  "field_names": [
    "example_field"
  ],
  "exclude_own_note": true
}
```
Replace `example_field` with the field name you want to check duplicates for. You can add multiple fields to check
duplicates for multiple fields. This way, duplicates can be compared between multiple decks, i.e., if *Vocabulary-Kanji*
in deck A has same value as *target word* in deck B, duplicate will be shown.

``` json
{
  "field_names": [
    "target word",
    "Vocabulary-Kanji"
  ]
}
```

### Exclude current note

By default, duplicate searches exclude the note being edited (`exclude_own_note: true`), matching Anki's own behavior.
If you prefer to see the original note next to its duplicates so you can compare them directly, untick
*Exclude current note from duplicate search results* in the configuration window (or set `exclude_own_note` to `false`).

## Find Duplicates across your collection

*Browse > Notes > (Configured Duplicates) Find duplicates...* — placed directly below Anki's built-in
*Find Duplicates...* — scans the whole collection for notes that share the same value in any of the configured fields,
including values stored under differently named fields (e.g. *Vocabulary-Kanji* matching *target word*). Unlike the
built-in search, it checks all configured fields at once instead of one by one. An optional filter field (same search
syntax as the Browser, like Anki's own *Find Duplicates* filter) limits the scan to matching notes — press *Search* or
Enter to re-run. Results are grouped by value and sorted by frequency; the report stays open next to the Browser, and
clicking a group (or *Open All in Browser*) shows the notes there so you can review them side by side.

## Why?

Sometimes the first field in Anki is not the only field the user wants to check for duplicates. For example, when sentence mining,
using some automated system like [mpvacious](https://github.com/Ajatt-Tools/mpvacious) may only fill in the sentence, and the user
manually fills in the target word for the note. In this case, the user most likely wants to check the duplicate field for the target
word as well, to make sure they have not mined that word already.

## How It Works

Configure the fields for duplicate checking in the add-on's configuration window.

When using this plugin, Anki will perform the same checks it is already doing on the first field,
but it will also search duplicates for the additional duplicate fields. When there is a duplicate,
the field is highlighted and a link for duplicates will be shown.

### Notes

This plugin works only in Anki desktop, not in mobile.

This project is forked from https://github.com/matthayes/anki_flex_dupes although the functionality is completely different.
