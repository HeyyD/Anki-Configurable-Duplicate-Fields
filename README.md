# Configurable duplicate fields

This modifies Anki's duplicate checking in the editor so that additional fields can be used to check duplicates.
Fields to be checked can be set in the add-on's config view in *Tools > Add-ons > Configurable duplicate fields > Config*.

``` json
{
  "field_names": [
    "example_field"
  ]
}
```
Replace `example_field` wwith the field name you want to check duplicates for. You can add multiple fields separated by commas to check
duplicates for multiple fields. This way, duplicates can be compared between multiple decks, i.e., if *Vocabulary-Kanji* in deck A has
same value as *target word* in deck B, duplicate will be shown.

``` json
{
  "field_names": [
    "target word",
    "Vocabulary-Kanji"
  ]
}
```

After configuring the fields, remember to restart Anki.

## Why?

Sometimes the first field in Anki is not the only field the user wants to check for duplicates. For example, when sentence mining,
using some automated system like [mpvacious](https://github.com/Ajatt-Tools/mpvacious) may only fill in the sentence, and the user
manually fills in the target word for the note. In this case, the user most likely wants to check the duplicate field for the target
word as well, to make sure they have not mined that word already.

## How It Works

Configure the fields for duplicate checking in the add-on's configuration window.

When using this plugin, Anki will perform the same checks it is already doing on the first field, but it will also search duplicates for
for the additional duplicate fields. When there is a duplicate, the field is highlighted and a link for duplicates will be shown.

### Notes

This plugin works only in Anki desktop, not in mobile.

This project is forked from https://github.com/matthayes/anki_flex_dupes although the functionality is completely different.
