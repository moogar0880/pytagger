import os
import logging
import subprocess
import unicodedata
from contextlib import contextmanager

__author__ = 'Jon Nappi'
__all__ = ['ignored', 'move_to_trash', 'dict_concat', 'strip_unicode']


@contextmanager
def ignored(*exceptions):
    """Context manager to ignore specified exceptions and logging pertinent
    info

        with ignored(AttributeError):
            a = None
            a.foo()
            # bar() is reached despite a.foo() throwing an AttributeError
            bar()
    """
    logger = logging.getLogger('ignored')
    try:
        yield
    except exceptions:
        logger.info('IGNORING {}'.format(exceptions))


def move_to_trash(file_path):
    """Move the provided file to it's closest Trash folder"""
    uid = os.geteuid()
    disk = file_path.split('/')[1]
    local_trash = os.path.join(os.path.expanduser('~'), '.Trash')
    if disk == 'Users':
        if os.path.exists(local_trash):
            command = 'mv "{}" "{}"'.format(file_path, local_trash)
            subprocess.call(command, shell=True)
        else:
            print 'ERROR: Can not find Trash'
    elif disk == 'Volumes':
        dirs = file_path.split('/')
        volume_trash = os.path.join(dirs[1], dirs[2], '.Trashes')
        if os.path.exists(volume_trash):
            users_volume_trash = os.path.join(volume_trash, str(uid))
            if os.path.exists(users_volume_trash):
                subprocess.call('mv "{}" "{}"'.format(file_path,
                                                      users_volume_trash),
                                shell=True)
            else:
                os.mkdir(users_volume_trash)
                subprocess.call('mv "{}" "{}"'.format(file_path,
                                                      users_volume_trash),
                                shell=True)
        elif os.path.exists(local_trash):
            subprocess.call('mv "{}" "{}"'.format(file_path, local_trash),
                            shell=True)
        else:
            print 'ERROR: Can not find Trash'
        subprocess.call('mv "{}" "{}"'.format(file_path, local_trash),
                        shell=True)


def dict_concat(d1, d2):
    """Universal dictionary concatenater.
    WARNING: Assumes that all key values will be unique
    """
    for key in d2.keys():
        d1[key] = d2[key]
    return d1


def strip_unicode(message):
    """Strip unicode characters from strings. Useful for descriptions and
    titles, which by default get returned from iTunes as unicode strings.
    """
    if type(message) == unicode:
        output = ''
        for ch in message:
            if unicodedata.normalize('NFKD', ch).encode('ascii',
                                                        'ignore') == '':
                if ch == u'\u2019':
                    output += "'"
            else:
                output += unicodedata.normalize('NFKD', ch).encode('ascii',
                                                                   'ignore')
        return output
    else:
        return message
