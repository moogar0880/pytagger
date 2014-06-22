import os
import subprocess
from setuptools import setup

from pytagger import __version__


packages = ['pytagger']
requires = ['fuzzywuzzy', 'requests', 'trakt', 'subler']

itunes = 'git+https://github.com/moogar0880/python-itunes#egg=python-itunes-1.1'

install_cmd = 'pip install %s'
if os.getuid() == 0:
    install_cmd = 'sudo pip install %s'

subprocess.check_call(install_cmd % itunes, shell=True)

setup(name='pytagger',
      version=__version__,
      description='A python backend to iTunes style metadata tagging',
      author='Jonathan Nappi',
      author_email='moogar@comcast.net',
      maintainer='Jonathan Nappi',
      maintainer_email='moogar@comcast.net',
      license='http://www.gnu.org/copyleft/gpl.html',
      platforms=['OS X'],
      url='https://github.com/moogar0880/pytagger',
      packages=packages,
      install_requires=requires,
      entry_points={
          'console_scripts': ['tag = pytagger.main:main']
      },
      )
