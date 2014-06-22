from setuptools import setup

from pytagger import __version__


packages = ['pytagger']
requires = ['fuzzywuzzy', 'requests', 'trakt', 'subler']
dependency_links = [
    'git+https://github.com/moogar0880/python-itunes#egg=python-itunes-0.3'
]


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
      dependency_links=dependency_links,
      packages=packages,
      install_requires=requires,
      entry_points={
          'console_scripts': ['tag = pytagger.main:main']
      },
      )
