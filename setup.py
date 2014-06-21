from setuptools import setup

VERSION = '1.0.1'


packages = ['pytagger']
requires = ['fuzzywuzzy', 'requests', 'trakt']
dependency_links = ['git+http://github.com/moogar0880/python-itunes/tarball/master#egg=python-itunes-0.3']


setup(name='pytagger',
      version=VERSION,
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
