# pytagger

A simple python interface to collecting and writing iTunes style metadata to your media files automatically.

## Examples

### TV Shows
Given that a show is stored locally as /Volumes/Shows/<Show>/<Season>/<file>.mv4
```bash
$ tag -t /Volumes/Shows/<Show>/<Season>/<file>.mv4
```
will automatically search iTunes and Trakt.tv for data to be written to the media
files as metadata.

### Movies
Given a movie file,
```bash
$ tag -m /Volumes/Movies/<file>.mv4
```
will automatically search iTunes and Trakt.tv for data to be written to the media
files as metadata.

### Music
Given an audio file,
```bash
$ tag -M /Volumes/Music/<file>.m4a
```
will automatically search iTunes for data to be written to the media files as
metadata.
