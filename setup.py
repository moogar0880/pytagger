import os
import subprocess
import zipfile
import shutil
from distutils.core import setup

VERSION = '0.5'
itunesURL = 'https://github.com/moogar0880/python-itunes/archive/master.zip'
tmdbURL = 'https://github.com/doganaydin/themoviedb/archive/master.zip'

# Check to see if pip is installed, if not quit
try:
    subprocess.check_call('which pip', shell=True)
except:
    print '''pip is required to install dependencies. 
    Please visit https://pypi.python.org/pypi/pip to download and install pip'''
    os._exit(os.EX_OK)
# Check to see if requests module is installed, if not install it    
try:
    import requests
except:
    subprocess.check_call('sudo pip install requests', shell=True)
    import requests
# Check to see if itunes module is installed, if not install it from source
try:
    import itunes
except ImportError:
    req = requests.get(itunesURL)
    f = open('src.zip','w')
    f.write(req.content)
    f.close()
    src = zipfile.ZipFile('src.zip','r')
    src.extractall()
    src.close()
    os.chdir('python-itunes-master')
    subprocess.check_call('sudo python setup.py install', shell=True)
    os.chdir('..')
    shutil.rmtree('python-itunes-master')
    os.remove('src.zip')
# Check to see if tvdb_api module is installed, if not install it through pip
try:
    import tvdb_api
except ImportError:
    subprocess.check_call('sudo pip install tvdb_api', shell=True)
# Check to see if fuzzywuzzy module is installed, if not install it through pip
try:
    import fuzzywuzzy.fuzz
except ImportError:
    subprocess.check_call('sudo pip install fuzzywuzzy', shell=True)
# Check to see if tmdb module is installed, if not install it from source
try:
    import tmdb
except ImportError:
    req = requests.get(tmdbURL)
    f = open('src.zip','w')
    f.write(req.content)
    f.close()
    src = zipfile.ZipFile('src.zip','r')
    src.extractall()
    src.close()
    os.chdir('themoviedb-master')
    subprocess.check_call('sudo python setup.py install', shell=True)
    os.chdir('..')
    shutil.rmtree('themoviedb-master')
    os.remove('src.zip')

setup(name = "pytagger",
      version = VERSION,
      description="A python backend to iTunes style metadata tagging",
      author='Jonathan Nappi',
      author_email='moogar@comcast.net',
      maintainer='Jonathan Nappi',
      maintainer_email='moogar@comcast.net',
      license = "http://www.gnu.org/copyleft/gpl.html",
      platforms = ["any"],
      entry_points=dict(console_scripts=['tag=pytagger:main']),    
      url="https://github.com/moogar0880/pytagger",
      packages=['pytagger'],
    )