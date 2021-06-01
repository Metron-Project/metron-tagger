"""Setup file for metron-tagger"""
from setuptools import find_packages, setup

import metrontagger

setup(
    name="metron-tagger",
    version=metrontagger.VERSION,
    description="A program to write metadata from metron.cloud to a comic archive",
    long_description=open("README.rst").read(),
    long_description_content_type="text/x-rst",
    author="Brian Pepple",
    author_email="bdpepple@gmail.com",
    url="https://github.com/bpepple/metron-tagger",
    license="GPLv3",
    packages=find_packages(exclude=["tests"]),
    python_requires=">=3.8",
    install_requires=["darkseid >= 1.0.6", "mokkari >= 0.1.2"],
    entry_points={"console_scripts": ["metron-tagger=metrontagger.main:main"]},
    classifiers=[
        "Development Status :: 4 - Beta",
        "Environment :: Console",
        "Intended Audience :: End Users/Desktop",
        "License :: OSI Approved :: GNU General Public License v3 or later (GPLv3+)",
        "Natural Language :: English",
        "Programming Language :: Python :: 3.8",
        "Topic :: Utilities",
        "Topic :: Other/Nonlisted Topic",
        "Operating System :: MacOS :: MacOS X",
        "Operating System :: POSIX",
        "Operating System :: POSIX :: BSD",
        "Operating System :: POSIX :: Linux",
        "Operating System :: Microsoft :: Windows",
    ],
    keywords=["comics", "comic", "metadata", "tagging", "tagger"],
)
