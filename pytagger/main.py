#!/usr/bin/python
from __future__ import print_function

import os
import sys
import json
import argparse

from time import sleep
from multiprocessing import Process, cpu_count, Value


def parse_arguments():
    """Parse command line arguments"""
    parser = argparse.ArgumentParser()
    parser.add_argument('-a', '--auto', action='store_true',
                        help='enable automatic tagging')
    parser.add_argument('-t', '--TV', action='store_true',
                        help='declare media type as TV')
    parser.add_argument('-m', '--Movie', action='store_true',
                        help='declare media type as Movie')
    parser.add_argument('-M', '--Music', action='store_true',
                        help='declare media type as Music')
    parser.add_argument('-n', '--num_procs', action='store',
                        default=cpu_count() * 2,
                        help='Set the number of files to tag simultaneously')
    parser.add_argument('-e', '--edit', action='store_true',
                        help='Interactively edit your config file')
    parser.add_argument('files', nargs='*')
    return parser.parse_args()


def map_readable_to_real(target):
    """This function returns the AtomicParsley version of the humanreadable
    target value key that the user is allowed to enter for their metadata
    fields.
    """
    translator = {'HD': 'HD Video'}
    try:
        return translator[target]
    except KeyError:
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
                print('The list will print when it\'s been written')
            else:
                split = target.split('=')
                target = split[0]
                target_value = split[1]
                print(target, target_value, to_ret)
                for to in to_ret:
                    to[map_readable_to_real(target)] = target_value
                    print(to[map_readable_to_real(target)])
        else:
            index = int(choice)-1
            quest = 'Please enter your metadata and it\'s corresponding ' \
                    'target (h for list of targets): '
            target = raw_input(quest)
            if target == 'h':
                print('The list will print when it\'s been written')
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
        print(to_ret)
    quest += 'Choose the file you would like to set metadata for, a for ' \
             'all, e to finish, q to quit: '
    return file_poll(quest, to_ret)


def first_use():
    """To be run only if the pytagger config file does not exist which,
    assumingly will only happen the first time the script is run in order to
    store user specific information in a cerntrally available location
    """
    user = os.path.expanduser('~').split(os.sep)[-1]
    question = "Well hey there, %s. It looks like this is your first time " \
               "running PyTagger, so let's go ahead and get some basic info " \
               "from you real quick to make your metadata tagging even " \
               "easier.\n\nFirst, please enter your Apple ID: " % user
    apple_id = raw_input(question).decode()
    question_2 = "\nNow please enter your Trakt.tv API Key which can be " \
                 "found at http://trakt.tv/api-docs/authentication: "
    api_key = raw_input(question_2).decode()
    config_file = os.sep.join([os.path.expanduser('~'), '.pytagger.json'])
    config_data = {'iTunes Account': apple_id, 'trakt_key': api_key}
    with open(config_file, 'w') as f:
        json.dump(config_data, f)


def edit_configs():
    """Similar to first_use but focused on editing the pre-existing info stored
    in pytagger.json
    """
    config_file = os.sep.join([os.path.expanduser('~'), '.pytagger.json'])
    if not os.path.exists(config_file):
        return first_use()
    with open(config_file) as f:
        config_data = json.load(f)
    user = os.path.expanduser('~').split(os.sep)[-1]
    question = "Hey, %s. To edit a particular field just provide a new value" \
               "when prompted, to leave a value alone just press enter." \
               "from you real quick to make your metadata tagging even " \
               "easier.\n\nFirst, please enter your Apple ID [%s]: "
    apple_id = raw_input(question % (user, config_data.get('iTunes Account',
                                                           ''))).decode()
    question_2 = "\nNow please enter your Trakt.tv API Key which can be " \
                 "found at http://trakt.tv/api-docs/authentication [%s]: "
    api_key = raw_input(question_2 % config_data.get('trakt_key', '')).decode()
    config_file = os.sep.join([os.path.expanduser('~'), '.pytagger.json'])
    config_data = {'iTunes Account': apple_id, 'trakt_key': api_key}
    with open(config_file, 'w') as f:
        json.dump(config_data, f)


def load_configs():
    """Read in the information stored in the current users pytagger config file
    and return it as a dict
    """
    config_file = os.sep.join([os.path.expanduser('~'), '.pytagger.json'])
    if not os.path.exists(config_file):
        first_use()
    with open(config_file) as f:
        config_data = json.load(f)
    return config_data


def main():
    """Main loop"""
    from pytagger import TVTagger, MovieTagger, MusicTagger
    from pytagger.utils import initialize_logging, print_progress

    global_logger = initialize_logging()

    progress_meter = Value('d', 0.0)

    args = parse_arguments()

    if not any([args.TV, args.Movie, args.Music]):
        print('No media type flag set')
        sys.exit(1)
    if len(args.files) == 0:
        print('No files given to tag')
        sys.exit(2)

    custom_args = [{} for _ in args.files]

    if args.edit:
        edit_configs()
    config_args = load_configs()

    if not args.auto:
        custom_args = gather_interactive_data(args.files)

    tagger_type = TVTagger if args.TV else MovieTagger
    if args.Music:
        tagger_type = MusicTagger

    taggers = []
    for index, file_name in enumerate(args.files):
        user_args = config_args
        for key, val in custom_args[index]:
            user_args[key] = val
        tagger = tagger_type(file_name, global_logger, progress_meter,
                             customs=user_args)
        taggers.append(tagger)

    max_steps = float(len(taggers) * tagger_type.steps)

    running = []
    num_procs = args.num_procs
    while len(taggers) > 0:
        while len(running) < num_procs:
            try:
                tagger = taggers.pop(0)
            except IndexError:
                break
            p = Process(target=tagger.collect_metadata, name=tagger.file_name)
            running.append(p)
            p.start()
        print_progress(progress_meter, max_steps)
        sleep(1)
        running[:] = [process for process in running if process.is_alive()]
    while len(running) > 0:
        print_progress(progress_meter, max_steps)
        sleep(1)
        running[:] = [process for process in running if process.is_alive()]
