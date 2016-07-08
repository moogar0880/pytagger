from setuptools import setup

from pytagger import __version__


packages = ['pytagger']
with open('requirements.txt') as f:
    requires = [line.strip() for line in f if line.strip()]

setup(name='pytagger',
      version=__version__,
      description='A python backend to iTunes style metadata tagging',
      author='Jonathan Nappi',
      author_email='moogar@comcast.net',
      maintainer='Jonathan Nappi',
      maintainer_email='moogar@comcast.net',
      license='http://www.gnu.org/copyleft/gpl.html',
      package_dir={'pytagger': 'pytagger'},
      platforms=['OS X'],
      url='https://github.com/moogar0880/pytagger',
      packages=packages,
      install_requires=requires,
      zip_safe=False,
      entry_points={
          'console_scripts': ['tag = pytagger.main:main']
      },
      )
