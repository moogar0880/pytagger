import os
import logging
import subprocess
import unicodedata
from contextlib import contextmanager

from subler import Atom

__author__ = 'Jon Nappi'
__all__ = ['ignored', 'move_to_trash', 'dict_concat', 'strip_unicode',
           'AtomCollection']


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


class AtomCollection(dict):
    """A dictionary collection of Atom instances. When a tag is added the tag
    for it is used as the key to the dictionary, the value for which is an Atom
    instance. When you key back on an item already in the dictionary the value
    of that Atom is returned. Thus, if you know a key 'Artist' exists, you can
    get the value of that tag by doing ``my_collection['Artist']``
    """
    def get(self, k, d=None):
        """ D.get(k[,d]) -> D[k] if k in D, else d.  d defaults to None. """
        if k in self:
            return self[k]
        return d

    @property
    def atoms(self):
        """The list of :class:`Atom`'s contained in this collection"""
        return [super(AtomCollection, self).__getitem__(key) for key in self]

    def items(self):
        """ D.items() -> list of D's (key, value) pairs, as 2-tuples """
        items = []
        for tag in self:
            items.append((tag, self[tag]))
        return items

    def __getitem__(self, key):
        """Return the value of the Atom at key"""
        return super(AtomCollection, self).__getitem__(key).value

    def __setitem__(self, key, val):
        """Custom __setitem__ for entering Atoms based on key, val"""
        super(AtomCollection, self).__setitem__(key, Atom(key, val))
