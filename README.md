# Configurable duplicate fields

This modifies Anki's duplicate checking in the editor so that additional fields can be used to check duplicates. Fields to be checked
can be set in the add-ons config view in *Tools > Add-ons > Configurable duplicate fields > Config*.

``` json
{
  "field_names": [
    "example_field"
  ]
}
```
Replace the `example_field` with the field name you want to check duplicates for. You can add multiple fields separated by comma to
check duplicates for. This way duplicates can be compared between multiple decks, ie. if *Vocabulary-Kanji* in deck A has same value as
*target word* in deck B, duplicate will be shown.

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

Sometimes the first field in Anki is not the only field the user wants to check duplicates for. For example when sentence mining, using
some automated system ie. [mpvacious](https://github.com/Ajatt-Tools/mpvacious) can only fill in the sentence, and the user manually
fills in the target word for the note. In this case the user most likely wants to check the duplicate field also for the target word,
to make sure they have not mined that word already.

## How It Works

Configure the fields for duplicate checking in the add-ons configuration window.

When using this plugin, Anki will perform the same checks it is already doing on the first field, but it will also search duplicates for
for the additional duplicate fields. When there is a duplicate, the field is highlighted and a link for duplicates will be shown.

### Notes

This plugin works only in Anki desktop, not in mobile.

This project is forked from https://github.com/matthayes/anki_flex_dupes although the functionality is complitely different.
