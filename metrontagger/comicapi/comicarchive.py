"""A class to represent a single comic, be it file or folder of images"""

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

import io
import os
import sys
import tempfile
import zipfile

from natsort import natsorted

from .comicinfoxml import ComicInfoXml
from .filenameparser import FileNameParser
from .genericmetadata import GenericMetadata

try:
    from PIL import Image

    pil_available = True
except ImportError:
    pil_available = False


sys.path.insert(0, os.path.abspath("."))


class MetaDataStyle:
    # Only have ComicRack is supported for now, but if we want to add back other formats this will be useful.
    CIX = 0
    name = ["ComicRack"]


class ZipArchiver:

    """ZIP implementation"""

    def __init__(self, path):
        self.path = path

    def readArchiveFile(self, archive_file):
        data = ""
        zf = zipfile.ZipFile(self.path, "r")

        try:
            data = zf.read(archive_file)
        except zipfile.BadZipfile as e:
            print(f"bad zipfile [{e}]: {self.path} :: {archive_file}", file=sys.stderr)
            zf.close()
            raise IOError
        except Exception as e:
            zf.close()
            print(f"bad zipfile [{e}]: {self.path} :: {archive_file}", file=sys.stderr)
            raise IOError
        finally:
            zf.close()
        return data

    def removeArchiveFile(self, archive_file):
        try:
            self.rebuildZipFile([archive_file])
        except zipfile.BadZipfile:
            return False
        else:
            return True

    def writeArchiveFile(self, archive_file, data):
        #  At the moment, no other option but to rebuild the whole
        #  zip archive w/o the indicated file. Very sucky, but maybe
        # another solution can be found
        try:
            self.rebuildZipFile([archive_file])

            # now just add the archive file as a new one
            zf = zipfile.ZipFile(
                self.path, mode="a", allowZip64=True, compression=zipfile.ZIP_DEFLATED
            )
            zf.writestr(archive_file, data)
            zf.close()
            return True
        except (zipfile.BadZipfile, zipfile.LargeZipFile) as e:
            print(f"Error writing zipfile: {e}.")
            return False

    def getArchiveFilenameList(self):
        try:
            zf = zipfile.ZipFile(self.path, "r")
            namelist = zf.namelist()
            zf.close()
            return namelist
        except Exception as e:
            print(f"Unable to get zipfile list [{e}]: {self.path}", file=sys.stderr)
            return []

    def rebuildZipFile(self, exclude_list):
        """Zip helper func

        This recompresses the zip archive, without the files in the exclude_list
        """

        # print ">> sys.stderr, Rebuilding zip {0} without {1}".format(
        #                                            self.path, exclude_list )

        # generate temp file
        tmp_fd, tmp_name = tempfile.mkstemp(dir=os.path.dirname(self.path))
        os.close(tmp_fd)

        zin = zipfile.ZipFile(self.path, "r")
        zout = zipfile.ZipFile(tmp_name, "w", allowZip64=True)
        for item in zin.infolist():
            buffer = zin.read(item.filename)
            if item.filename not in exclude_list:
                zout.writestr(item, buffer)

        zout.close()
        zin.close()

        # replace with the new file
        os.remove(self.path)
        os.rename(tmp_name, self.path)

    def copyFromArchive(self, otherArchive):
        """Replace the current zip with one copied from another archive"""

        try:
            zout = zipfile.ZipFile(self.path, "w", allowZip64=True)
            for fname in otherArchive.getArchiveFilenameList():
                data = otherArchive.readArchiveFile(fname)
                if data is not None:
                    zout.writestr(fname, data)
            zout.close()
        except Exception as e:
            print(f"Error while copying to {self.path}: {e}", file=sys.stderr)
            return False
        else:
            return True


# ------------------------------------------


class UnknownArchiver:

    """Unknown implementation"""

    def __init__(self, path):
        self.path = path

    @classmethod
    def readArchiveFile(self):
        return ""

    @classmethod
    def writeArchiveFile(self, archive_file, data):
        return False

    @classmethod
    def removeArchiveFile(self, archive_file):
        return False

    @classmethod
    def getArchiveFilenameList(self):
        return []


# ------------------------------------------------------------------


class ComicArchive:
    class ArchiveType:
        Zip, Unknown = list(range(2))

    def __init__(self, path):
        self.path = path

        self.ci_xml_filename = "ComicInfo.xml"
        self.resetCache()

        self.archive_type = self.ArchiveType.Unknown
        self.archiver = UnknownArchiver(self.path)

        if self.zipTest():
            self.archive_type = self.ArchiveType.Zip
            self.archiver = ZipArchiver(self.path)

    def resetCache(self):
        """Clears the cached data"""
        self.has_cix = None
        self.page_count = None
        self.page_list = None
        self.cix_md = None

    def loadCache(self, style_list):
        for style in style_list:
            self.readMetadata(style)

    def rename(self, path):
        self.path = path
        self.archiver.path = path

    def zipTest(self):
        return zipfile.is_zipfile(self.path)

    def isZip(self):
        return self.archive_type == self.ArchiveType.Zip

    def isWritable(self):
        if self.archive_type == self.ArchiveType.Unknown:
            return False

        elif not os.access(self.path, os.W_OK):
            return False

        return True

    def isWritableForStyle(self, data_style):

        return self.isWritable()

    def seemsToBeAComicArchive(self):

        if (self.isZip()) and (self.getNumberOfPages() > 0):
            return True
        else:
            return False

    def readMetadata(self, style):

        if style == MetaDataStyle.CIX:
            return self.readCIX()
        else:
            return GenericMetadata()

    def writeMetadata(self, metadata, style):

        retcode = None
        if style == MetaDataStyle.CIX:
            retcode = self.writeCIX(metadata)
        return retcode

    def hasMetadata(self, style):

        if style == MetaDataStyle.CIX:
            return self.hasCIX()
        else:
            return False

    def removeMetadata(self, style):
        retcode = True
        if style == MetaDataStyle.CIX:
            retcode = self.removeCIX()
        return retcode

    def getPage(self, index):

        image_data = None

        filename = self.getPageName(index)

        if filename is not None:
            try:
                image_data = self.archiver.readArchiveFile(filename)
            except IOError:
                print("Error reading in page.", file=sys.stderr)

        return image_data

    def getPageName(self, index):

        if index is None:
            return None

        page_list = self.getPageNameList()

        num_pages = len(page_list)
        if num_pages == 0 or index >= num_pages:
            return None

        return page_list[index]

    def getScannerPageIndex(self):

        scanner_page_index = None

        # make a guess at the scanner page
        name_list = self.getPageNameList()
        count = self.getNumberOfPages()

        # too few pages to really know
        if count < 5:
            return None

        # count the length of every filename, and count occurences
        length_buckets = dict()
        for name in name_list:
            fname = os.path.split(name)[1]
            length = len(fname)
            if length in length_buckets:
                length_buckets[length] += 1
            else:
                length_buckets[length] = 1

        # sort by most common
        sorted_buckets = sorted(
            iter(length_buckets.items()), key=lambda k_v: (k_v[1], k_v[0]), reverse=True
        )

        # statistical mode occurence is first
        mode_length = sorted_buckets[0][0]

        # we are only going to consider the final image file:
        final_name = os.path.split(name_list[count - 1])[1]

        common_length_list = list()
        for name in name_list:
            if len(os.path.split(name)[1]) == mode_length:
                common_length_list.append(os.path.split(name)[1])

        prefix = os.path.commonprefix(common_length_list)

        if mode_length <= 7 and prefix == "":
            # probably all numbers
            if len(final_name) > mode_length:
                scanner_page_index = count - 1

        # see if the last page doesn't start with the same prefix as most
        # others
        elif not final_name.startswith(prefix):
            scanner_page_index = count - 1

        return scanner_page_index

    def getPageNameList(self, sort_list=True):

        if self.page_list is None:
            # get the list file names in the archive, and sort
            files = self.archiver.getArchiveFilenameList()

            # seems like some archive creators are on  Windows, and don't know
            # about case-sensitivity!
            if sort_list:

                def keyfunc(k):
                    # hack to account for some weird scanner ID pages
                    # basename=os.path.split(k)[1]
                    # if basename < '0':
                    #    k = os.path.join(os.path.split(k)[0], "z" + basename)
                    return k.lower()

                files = natsorted(files, key=keyfunc)

            # make a sub-list of image files
            self.page_list = []
            for name in files:
                if (
                    name[-4:].lower() in [".jpg", "jpeg", ".png", ".gif", "webp"]
                    and os.path.basename(name)[0] != "."
                ):
                    self.page_list.append(name)

        return self.page_list

    def getNumberOfPages(self):

        if self.page_count is None:
            self.page_count = len(self.getPageNameList())
        return self.page_count

    def readCIX(self):
        if self.cix_md is None:
            raw_cix = self.readRawCIX()
            if raw_cix is None or raw_cix == "":
                self.cix_md = GenericMetadata()
            else:
                self.cix_md = ComicInfoXml().metadataFromString(raw_cix)

            # validate the existing page list (make sure count is correct)
            if len(self.cix_md.pages) != 0:
                if len(self.cix_md.pages) != self.getNumberOfPages():
                    # pages array doesn't match the actual number of images we're seeing
                    # in the archive, so discard the data
                    self.cix_md.pages = []

            if len(self.cix_md.pages) == 0:
                self.cix_md.setDefaultPageList(self.getNumberOfPages())

        return self.cix_md

    def readRawCIX(self):
        if not self.hasCIX():
            return None
        try:
            raw_cix = self.archiver.readArchiveFile(self.ci_xml_filename)
        except IOError:
            print("Error reading in raw CIX!")
            raw_cix = ""
        return raw_cix

    def writeCIX(self, metadata):

        if metadata is not None:
            self.applyArchiveInfoToMetadata(metadata, calc_page_sizes=True)
            cix_string = ComicInfoXml().stringFromMetadata(metadata)
            write_success = self.archiver.writeArchiveFile(
                self.ci_xml_filename, cix_string
            )
            if write_success:
                self.has_cix = True
                self.cix_md = metadata
            self.resetCache()
            return write_success
        else:
            return False

    def removeCIX(self):
        if self.hasCIX():
            write_success = self.archiver.removeArchiveFile(self.ci_xml_filename)
            if write_success:
                self.has_cix = False
                self.cix_md = None
            self.resetCache()
            return write_success
        return True

    def hasCIX(self):
        if self.has_cix is None:

            if not self.seemsToBeAComicArchive():
                self.has_cix = False
            elif self.ci_xml_filename in self.archiver.getArchiveFilenameList():
                self.has_cix = True
            else:
                self.has_cix = False
        return self.has_cix

    def applyArchiveInfoToMetadata(self, md, calc_page_sizes=False):
        md.pageCount = self.getNumberOfPages()

        if calc_page_sizes:
            for p in md.pages:
                idx = int(p["Image"])
                if pil_available:
                    if (
                        "ImageSize" not in p
                        or "ImageHeight" not in p
                        or "ImageWidth" not in p
                    ):
                        data = self.getPage(idx)
                        if data is not None:
                            try:
                                im = Image.open(io.BytesIO(data))
                                w, h = im.size

                                p["ImageSize"] = str(len(data))
                                p["ImageHeight"] = str(h)
                                p["ImageWidth"] = str(w)
                            except IOError:
                                p["ImageSize"] = str(len(data))

                else:
                    if "ImageSize" not in p:
                        data = self.getPage(idx)
                        p["ImageSize"] = str(len(data))

    def metadataFromFilename(self, parse_scan_info=True):

        metadata = GenericMetadata()

        fnp = FileNameParser()
        fnp.parseFilename(self.path)

        if fnp.issue != "":
            metadata.issue = fnp.issue
        if fnp.series != "":
            metadata.series = fnp.series
        if fnp.volume != "":
            metadata.volume = fnp.volume
        if fnp.year != "":
            metadata.year = fnp.year
        if fnp.issue_count != "":
            metadata.issueCount = fnp.issue_count
        if parse_scan_info:
            if fnp.remainder != "":
                metadata.scanInfo = fnp.remainder

        metadata.isEmpty = False

        return metadata

    def exportAsZip(self, zipfilename):
        if self.archive_type == self.ArchiveType.Zip:
            # nothing to do, we're already a zip
            return True

        zip_archiver = ZipArchiver(zipfilename)
        return zip_archiver.copyFromArchive(self.archiver)
