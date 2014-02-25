#!/usr/bin/python
import os
import argparse
import pytagger


def parse_arguments():
    """Parse command line arguments"""
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
    """This function returns the AtomicParsley version of the humanreadable
    target value key that the user is allowed to enter for their metadata
    fields.
    """
    translator = {'HD': 'hdvideo'}
    try:
        return translator[target]
    except Exception:
        return target


def file_poll(question, to_ret):
    """This method polls the user on which files they would like to edit until
    the user explicitly quits the interaction.
    """
    while True:
        choice = raw_input(question)
        if choice.lower() == 'q':
            exit()
        elif choice.lower() == 'e':
            return to_ret
        elif choice.lower() == 'a':
            # Set metadata field for all files
            quest = 'Please enter your metadata and it\'s corresponding ' \
                    'target (h for list of targets): '
            target = raw_input(quest)
            if target == 'h':
                print 'The list will print when it\'s been written'
            else:
                split = target.split('=')
                target = split[0]
                target_value = split[1]
                print target, target_value, to_ret
                for to in to_ret:
                    to[map_readable_to_real(target)] = target_value
                    print to[map_readable_to_real(target)]
        else:
            index = int(choice)-1
            quest = 'Please enter your metadata and it\'s corresponding ' \
                    'target (h for list of targets): '
            target = raw_input(quest)
            if target == 'h':
                print 'The list will print when it\'s been written'
            else:
                split = target.split('=')
                target = split[0].strip()
                target_value = split[1].strip()
                to_ret[index][map_readable_to_real(target)] = target_value


def gather_interactive_data(file_list):
    """This function generates the question to pose to the user about which file
    they would like to edit. It them passes this question and the results 
    dictionary off to the file_poll function which handles processing the user's
    input on the file level.
    """
    # Pull file names out of all the file paths
    to_ret = []
    names = [x.split('/')[-1] for x in file_list]
    quest = 'Would you like to set custom metadata for any of these files?:\n'
    for i, name in enumerate(names):
        quest += '\t{}: {}\n'.format(i+1, name)
        to_ret.append({})
        print to_ret
    quest += 'Choose the file you would like to set metadata for, a for ' \
             'all, e to finish, q to quit: '
    return file_poll(quest, to_ret)

args = parse_arguments()
customArgs = [{} for f in args.files]
if not args.auto:
    customArgs = gather_interactive_data(args.files)
print customArgs
tagger = None

if len(args.files) == 0:
    print 'No files given to tag'
    os._exit(os.EX_OK)

for index, file_name in enumerate(args.files):
    if args.TV:
        tagger = pytagger.TVTagger(file_name=file_name,
                                   customs=customArgs[index])
    elif args.Movie:
        tagger = pytagger.MovieTagger(file_name)
    elif args.Music:
        tagger = pytagger.MusicTagger(file_name)
    else:
        print 'No media type flag set'
        os._exit(os.EX_OK)
    tagger.collect_metadata()
    print '{0:.2f}% done'.format(100.0*(float(index+1)/float(len(args.files))))
