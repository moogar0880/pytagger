#!/usr/bin/env python
# -*- coding: utf-8 -*-
import asyncio
import argparse
import json
import logging
import os
import sys
from asyncio.log import logger as LOGGER
from pytagger import TVTagger, MovieTagger, MusicTagger


def parse_arguments():
    """Parse command line arguments"""
    parser = argparse.ArgumentParser()
    parser.add_argument('-t', '--TV', action='store_true',
                        help='declare media type as TV')
    parser.add_argument('-m', '--Movie', action='store_true',
                        help='declare media type as Movie')
    parser.add_argument('-M', '--Music', action='store_true',
                        help='declare media type as Music')
    parser.add_argument('-e', '--edit', action='store_true',
                        help='Interactively edit your config file')
    parser.add_argument('files', nargs='*')
    return parser.parse_args()


def first_use():
    """To be run only if the pytagger config file does not exist which, ideally
    will only happen the first time the script is run in order to store user
    specific information in a common location
    """
    question = 'Apple ID: '
    apple_id = input(question).decode()
    question = "\nTrakt.tv API Token (https://trakt.tv/oauth/applications): "
    api_key = input(question).decode()

    config_file = os.sep.join([os.path.expanduser('~'), '.pytagger.json'])
    config_data = {'apple_id': apple_id, 'trakt_key': api_key}
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
    question = "Apple ID [{current}]: ".format(
        current=config_data.get('iTunes Account', '')
    )
    apple_id = input(question).decode()
    question = "\nTrakt.tv API Token (https://trakt.tv/oauth/applications): "
    api_key = input(question).decode()
    config_file = os.sep.join([os.path.expanduser('~'), '.pytagger.json'])
    config_data = {'apple_id': apple_id, 'trakt_key': api_key}
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


def get_tasks(files, tagger_type, config):
    """Generate an :class:`asyncio.Task` future for each file to be tagged
    :param files: A list of files to be tagged
    :param tagger_type: A :class:`Tagger` subclass used to actually tag an
        input file
    """
    tasks = []
    for index, file_name in enumerate(files):
        tagger = tagger_type(file_name, **config)
        tasks.append(tagger.tag())
    return tasks


def check_args(args):
    """validate the provided input arguments. Specifically it is determined if
    no media type flag was provided, or if no input files were provided.
    Additionally, this function handles launching the config editor if that
    option was provided
    """
    if args.edit:
        edit_configs()
        sys.exit(0)

    if not any([args.TV, args.Movie, args.Music]):
        print('No media type flag set')
        sys.exit(1)

    if len(args.files) == 0:
        print('No files given to tag')
        sys.exit(2)


def main():
    """Main loop"""
    LOGGER.setLevel(logging.DEBUG)  # enable debug logging

    # read commandline flags and ensure they are valid
    args = parse_arguments()
    check_args(args)

    # load user's config file
    config_args = load_configs()

    # determine the type of tagger to use for the provided files
    tagger_type = TVTagger if args.TV else MovieTagger
    if args.Music:
        tagger_type = MusicTagger

    # create a task future for each file to be tagged, grab an event loop from
    # asyncio, and run the futures asynchronously
    tasks = get_tasks(args.files, tagger_type, config_args)
    loop = asyncio.get_event_loop()
    loop.run_until_complete(asyncio.wait(tasks))

if __name__ == '__main__':
    main()
