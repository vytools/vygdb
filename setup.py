#!/usr/bin/env python
import setuptools, re

try:
    with open('README.md','r') as f:
        readme = f.read()
except Exception as exc:
    readme = ''

setuptools.setup(name='vygdb',
    description='Server debugger',
    long_description=readme,
    license='MIT',
    author='Nate Bunderson',
    author_email='nbunderson@gmail.com',
    url='https://github.com/NateBu/vygdb',
    keywords = ["vy", "vytools", "vygdb", "debug", "gdb"],
    classifiers = [
        "Programming Language :: Python",
        "Development Status :: 2 - Pre-Alpha",
        "Intended Audience :: Developers",
        "License :: OSI Approved :: MIT License",
        "Operating System :: OS Independent",
        "Programming Language :: Python :: 3",
        "Topic :: Other/Nonlisted Topic"
    ],
    python_requires='>=3.6',
    packages=setuptools.find_packages(),
    package_data = {'vygdb': ['main/*']},
    install_requires=['websockets'],
    entry_points={
        'console_scripts':[
            'vygdb=vygdb:_commandline'
        ]
    },
    setup_requires=['pytest-runner'],
    tests_require=['pytest'],
)

