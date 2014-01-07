#!/usr/bin/python
import sys
import os
import argparse
import pytagger        

def parse_arguments():
    """
    Parse command line arguments
    """
    parser = argparse.ArgumentParser()
    parser.add_argument('-a', '--auto', action="store_true", 
                        help='enable automatic tagging')
    parser.add_argument('-t', '--TV', action="store_true", 
                        help='declare media type as TV')
    parser.add_argument('-m', '--Movie', action="store_true", 
                        help='declare media type as Movie')
    parser.add_argument('-M', '--Music', action="store_true", 
                        help='declare media type as Music')
    parser.add_argument('files', nargs='*')
    return parser.parse_args()

def map_readable_to_real(target):
    """ 
    This function returns the AtomicParsley version of the humanreadable target
    value key that the user is allowed to enter for their metadata fields.
    """
    translator = {'HD': 'hdvideo'}
    try:
        return translator[target]
    except:
        return target

def file_poll(question, toRet):
    """
    This method polls the user on which files they would like to edit until the 
    user explicitly quits the interaction.
    """
    while(True):
        choice = raw_input(question)
        if choice.lower() == 'q':
            return toRet
        elif choice.lower() == 'a': #Set metadata field for all files
            quest = 'Please enter your metadata and it\'s corresponding target (h for list of targets): '
            target = raw_input(quest)
            if target == 'h':
                print 'The list will print when it\'s been written'
            else:
                split = target.split('=')
                target = split[0]
                targetValue = split[1]
                for to in toRet:
                    to[map_readable_to_real(target)] = targetValue
        else:
            index = int(choice)-1
            quest = 'Please enter your metadata and it\'s corresponding target (h for list of targets): '
            target = raw_input(quest)
            if target == 'h':
                print 'The list will print when it\'s been written'
            else:
                split = target.split('=')
                target = split[0].strip()
                targetValue = split[1].strip()
                toRet[index][map_readable_to_real(target)] = targetValue

def gather_interactive_data(filelist):
    """
    This function generates the question to pose to the user about which file
    they would like to edit. It them passes this question and the results 
    dictionary off to the file_poll function which handles processing the user's
    input on the file level.
    """
    #Pull filenames out of all the filepaths
    toRet = []
    names = [x.split('/')[-1] for x in filelist]
    quest = 'Would you like to set custom metadata for any of these files?:\n'
    for i, name in enumerate(names):
        quest += '\t{}: {}\n'.format(i+1, name)
        toRet.append({})
    quest += 'Choose the file you would like to set metadata for (q to quit): '
    return file_poll(quest, toRet)

args = parse_arguments()
customArgs = {}
if not args.auto:
    customArgs = gather_interactive_data(args.files)
# print customArgs
tagger = None

if args.TV:
    tagger = pytagger.TVTagger(args.files)
elif args.Movie:
    tagger = pytagger.MovieTagger(args.files)
elif args.Music:
    tagger = pytagger.MusicTagger(args.files)
else:
    print 'No media type flag set'
    os._exit(os.EX_OK)

tagger.collect_metadata()
