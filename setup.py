from setuptools import find_packages, setup

import metrontagger

setup(
    name="metron-tagger",
    version=metrontagger.version,
    description="A program to write metadata from metron.cloud to a comic archive",
    author="Brian Pepple",
    author_email="bdpepple@gmail.com",
    url="https://github.com/bpepple/metron-tagger",
    license="GPLv3",
    packages=find_packages(),
    python_requires=">=3.7",
    install_requires=["natsort", "pillow", "ratelimit"],
    entry_points={"console_scripts": ["metron-tagger=metrontagger.metron_tagger:main"]},
    classifiers=[
        "Development Status :: 3 - Alpha",
        "Environment :: Console",
        "Intended Audience :: End Users/Desktop",
        "License :: OSI Approved :: GNU General Public License v3 or later (GPLv3+)",
        "Natural Language :: English",
        "Programming Language :: Python :: 3.7",
        "Topic :: Utilities",
        "Topic :: Other/Nonlisted Topic",
    ],
    keywords=["comics", "comic", "metadata", "tagging", "tagger"],
)
