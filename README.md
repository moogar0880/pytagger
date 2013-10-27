pytagger
========

A simple python interface to collecting and writing iTunes style metadata to your media files automatically.

Examples
--------

Tagging
~~~~~~~
  #python [-flags] [-list of files to be tagged]
  Given that a show/shows is/are stored locally as .../Show Name/Season Season#/Ep# Ep Title
  python tagger.py -t [list of filenames] OR python tagger.py --TV [list of filenames]
  will automatically search iTunes and TheTVDB for data to be written to the media files as metadata

  Given a movie file, regardless of where it is stored
  python tagger.py -m [list of filenames] OR python tagger.py --Movie [list of filenames]
  will automatically search iTunes and TheMovieDB for data to be written to the media files as metadata

  Given a music file/files is/are stored locally as .../Artist Name/Album Name/Track# Track Title
  python tagger.py -M [list of filenames] OR python tagger.py --Music [list of filenames]
  will automatically search iTunes for data to be written to the media files as metadata