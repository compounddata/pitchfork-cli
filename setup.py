# -*- coding: utf-8 -*-

import sys
if not sys.version_info[0] == 3:
    sys.exit("Sorry, Python 3 is required. Use: \'python3 setup.py install\'")

from setuptools import find_packages, setup
import re

install_requires = [
    'click', 'pyyaml', 'jinja2', 'requests'
]

version = re.search(
    '^__version__\s*=\s*"(.*)"',
    open('pitchfork/pitchfork.py').read(),
    re.M
    ).group(1)


setup(
    name='pitchfork',
    version=version,
    description='pitchfork cli',
    maintainer='Rene Cunningham',
    maintainer_email='pitchfork@pitchfork.io',
    install_requires=install_requires,
    packages=find_packages(exclude=['tests']),
    entry_points={
        'console_scripts': [
            'pitchfork = pitchfork.pitchfork:pitchfork',
        ],
    }
)
