# coding=utf-8
"""Some generic utilities"""

# Copyright 2012-2014 Anthony Beville

# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at

#     http://www.apache.org/licenses/LICENSE-2.0

# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.

import os
import re
import sys


def get_recursive_filelist(pathlist):
    """Get a recursive list of of all files under all path items in the list"""
    filelist = []
    for p in pathlist:
        # if path is a folder, walk it recursively, and all files underneath
        if isinstance(p, str):
            pass
        elif not isinstance(p, str):
            # it's probably a QString
            p = str(p)

        if os.path.isdir(p):
            for root, _, files in os.walk(p):
                for f in files:
                    if isinstance(f, str):
                        pass
                    elif not isinstance(f, str):
                        # it's probably a QString
                        f = str(f)
                    filelist.append(os.path.join(root, f))
        else:
            filelist.append(p)

    return filelist


def listToString(l):
    string = ""
    if l is not None:
        for item in l:
            if len(string) > 0:
                string += "; "
            string += item
    return string


def addtopath(dirname):
    if dirname is not None and dirname != "":

        # verify that path doesn't already contain the given dirname
        tmpdirname = re.escape(dirname)
        pattern = r"{sep}{dir}$|^{dir}{sep}|{sep}{dir}{sep}|^{dir}$".format(
            dir=tmpdirname, sep=os.pathsep
        )

        match = re.search(pattern, os.environ["PATH"])
        if not match:
            os.environ["PATH"] = dirname + os.pathsep + os.environ["PATH"]


def removearticles(text):
    text = text.lower()
    articles = ["and", "a", "&", "issue", "the"]
    newText = ""
    for word in text.split(" "):
        if word not in articles:
            newText += word + " "

    newText = newText[:-1]

    # now get rid of some other junk
    newText = newText.replace(":", "")
    newText = newText.replace(",", "")
    newText = newText.replace("-", " ")

    # since the CV API changed, searches for series names with periods
    # now explicitly require the period to be in the search key,
    # so the line below is removed (for now)
    # newText = newText.replace(".", "")

    return newText


def unique_file(file_name):
    counter = 1
    # returns ('/path/file', '.ext')
    file_name_parts = os.path.splitext(file_name)
    while True:
        if not os.path.lexists(file_name):
            return file_name
        file_name = file_name_parts[0] + " (" + str(counter) + ")" + file_name_parts[1]
        counter += 1
