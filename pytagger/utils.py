from __future__ import print_function

import os
import sys
import shutil
import logging
import threading
import traceback
import unicodedata
import multiprocessing

from datetime import date
from contextlib import contextmanager
from logging.handlers import RotatingFileHandler

__author__ = 'Jon Nappi'
__all__ = ['ignored', 'move_to_trash', 'dict_concat', 'strip_unicode',
           'MultiProcessingLogger']


class MultiProcessingLogger(logging.Handler):
    """A multiprocessing-safe logger with built in log rolling/backups"""
    def __init__(self, name, mode='a', maxsize=10000, rotate=100):
        """Create a new MultiprocessingLogger for a file named *name*

        :param name: The name of the log file to be written to
        :param mode: The mode in which the file should be opened in
        :param maxsize: The number of bytes this log file should roll over at
        :param rotate: The number of rolled log files to keep hanging around
        """
        logging.Handler.__init__(self)

        self._handler = RotatingFileHandler(name, mode, maxsize, rotate)
        self.queue = multiprocessing.Queue(-1)

        t = threading.Thread(target=self.receive)
        t.daemon = True
        t.start()

    def setFormatter(self, fmt):
        logging.Handler.setFormatter(self, fmt)
        self._handler.setFormatter(fmt)

    def receive(self):
        while True:
            try:
                record = self.queue.get()
                self._handler.emit(record)
            except (KeyboardInterrupt, SystemExit):
                raise
            except EOFError:
                break
            except:
                traceback.print_exc(file=sys.stderr)

    def send(self, s):
        self.queue.put_nowait(s)

    def _format_record(self, record):
        # ensure that exc_info and args
        # have been stringified.  Removes any chance of
        # unpickleable things inside and possibly reduces
        # message size sent over the pipe
        if record.args:
            record.msg = record.msg % record.args
            record.args = None
        if record.exc_info:
            dummy = self.format(record)
            record.exc_info = None

        return record

    def emit(self, record):
        try:
            s = self._format_record(record)
            self.send(s)
        except (KeyboardInterrupt, SystemExit):
            raise
        except:
            self.handleError(record)

    def close(self):
        self._handler.close()
        logging.Handler.close(self)


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
            shutil.move(file_path, local_trash)
        else:
            print('ERROR: Can not find Trash')
    elif disk == 'Volumes':
        dirs = file_path.split('/')
        volume_trash = os.path.join(dirs[1], dirs[2], '.Trashes')
        if os.path.exists(volume_trash):
            users_volume_trash = os.path.join(volume_trash, str(uid))
            if os.path.exists(users_volume_trash):
                shutil.move(file_path, users_volume_trash)
            else:
                os.mkdir(users_volume_trash)
                shutil.move(file_path, users_volume_trash)
        elif os.path.exists(local_trash):
            shutil.move(file_path, local_trash)
        else:
            print('ERROR: Can not find Trash')
        shutil.move(file_path, local_trash)


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


def initialize_logging():
    """Initialize a logger for us to use. This function can ONLY be called from
    main in order to ensure that we don't hose the locks on the log files
    """
    log_date = date.today().isoformat()
    home = os.path.expanduser('~')
    name = os.path.join(home, '.pytagger_logs/{}{}.log'.format(__name__,
                                                               log_date))
    logging.basicConfig(filename=name, level=logging.CRITICAL,
                        format='%(asctime)s %(levelname)s:%(message)s',
                        datefmt='%m/%d/%Y %I:%M:%S %p')

    logger = logging.getLogger('pytager')
    logger.addHandler(MultiProcessingLogger)
    return logger


def print_progress(meter, total_steps):
    """Print the current progress, as depicted by the progress_meter, to stdout

    :param meter: The multiprocess Value instance containing our progress data
    :param total_steps: The total number of steps we can possibly hit
    """
    msg = '\r{0:.2f}% Done'

    with meter.get_lock():
        sys.stdout.write(msg.format(100.0*(meter.value/total_steps)))
        sys.stdout.flush()
