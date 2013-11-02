#!/opt/local/bin/python
import sys
import argparse
import pytagger        

parser = argparse.ArgumentParser()
parser.add_argument('-t', '--TV', action="store_true", 
                    help='declare media type as TV')
parser.add_argument('-m', '--Movie', action="store_true", 
                    help='declare media type as Movie')
parser.add_argument('-M', '--Music', action="store_true", 
                    help='declare media type as Music')
parser.add_argument('files', nargs='*')
args = parser.parse_args()

tagger = None

if args.TV:
    tagger = pytagger.TVTagger(args.files)
elif args.Movie:
    tagger = pytagger.MovieTagger(args.files)
elif args.Music:
    tagger = pytagger.MusicTagger(args.files)
tagger.collectMetadata()
