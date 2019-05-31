from setuptools import find_packages, setup

import metrontagger

setup(
    name="metron-tagger",
    version=metrontagger.version,
    description="A program to write metadata from metron.cloud to a comic archive",
    long_description=open("README.md").read(),
    long_description_content_type="text/markdown",
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
        "Operating System :: MacOS :: MacOS X",
        "Operating System :: POSIX",
        "Operating System :: POSIX :: BSD",
        "Operating System :: POSIX :: Linux",
        "Operating System :: Microsoft :: Windows",
    ],
    keywords=["comics", "comic", "metadata", "tagging", "tagger"],
)
