"""Functions for renaming files based on metadata"""

# Copyright 2012-2014 Anthony Beville

import datetime
import re
from pathlib import Path

from darkseid.issuestring import IssueString


class FileRenamer:
    """Class to rename a comic archive based on it's metadata tag"""

    def __init__(self, metadata):
        self.set_metadata(metadata)
        self.set_template("%series% v%volume% #%issue% (of %issuecount%) (%year%)")
        self.smart_cleanup = True
        self.issue_zero_padding = 3

    def set_metadata(self, metadata):
        """Method to set the metadata"""
        self.metdata = metadata

    def set_issue_zero_padding(self, count):
        """Method to set the padding for the issue's number"""
        self.issue_zero_padding = count

    def set_smart_cleanup(self, enabled):
        """Method to use smart clean up. Currently not used"""
        self.smart_cleanup = enabled

    def set_template(self, template):
        """
        Method to use a user's custom file naming template.
        Currently this hasn't been implemented
        """
        self.template = template

    def replace_token(self, text, value, token):
        """Method to replace a value with another value"""
        # helper func
        def is_token(word):
            return word[0] == "%" and word[-1:] == "%"

        if value is not None:
            return text.replace(token, str(value))
        else:
            if self.smart_cleanup:
                # smart cleanup means we want to remove anything appended to token if it's empty
                # (e.g "#%issue%"  or "v%volume%")
                # (TODO: This could fail if there is more than one token appended together, I guess)
                text_list = text.split()

                # special case for issuecount, remove preceding non-token word,
                # as in "...(of %issuecount%)..."
                if token == "%issuecount%":
                    for idx, word in enumerate(text_list):
                        if token in word and not is_token(text_list[idx - 1]):
                            text_list[idx - 1] = ""

                text_list = [x for x in text_list if token not in x]
                return " ".join(text_list)
            else:
                return text.replace(token, "")

    def determine_name(self, filename, ext=None):
        """Method to create the new filename based on the files metadata"""
        meta_data = self.metdata
        new_name = self.template

        new_name = self.replace_token(new_name, meta_data.series, "%series%")
        new_name = self.replace_token(new_name, meta_data.volume, "%volume%")

        if meta_data.issue is not None:
            issue_str = "{0}".format(
                IssueString(meta_data.issue).as_string(pad=self.issue_zero_padding)
            )
        else:
            issue_str = None
        new_name = self.replace_token(new_name, issue_str, "%issue%")

        new_name = self.replace_token(new_name, meta_data.issue_count, "%issuecount%")
        new_name = self.replace_token(new_name, meta_data.year, "%year%")
        new_name = self.replace_token(new_name, meta_data.publisher, "%publisher%")
        new_name = self.replace_token(new_name, meta_data.title, "%title%")
        new_name = self.replace_token(new_name, meta_data.month, "%month%")
        month_name = None
        if meta_data.month is not None:
            if (
                isinstance(meta_data.month, str) and meta_data.month.isdigit()
            ) or isinstance(meta_data.month, int):
                if int(meta_data.month) in range(1, 13):
                    date_time = datetime.datetime(1970, int(meta_data.month), 1, 0, 0)
                    month_name = date_time.strftime("%B")
        new_name = self.replace_token(new_name, month_name, "%month_name%")

        new_name = self.replace_token(new_name, meta_data.genre, "%genre%")
        new_name = self.replace_token(new_name, meta_data.language, "%language_code%")
        new_name = self.replace_token(
            new_name, meta_data.critical_rating, "%criticalrating%"
        )
        new_name = self.replace_token(
            new_name, meta_data.alternate_series, "%alternateseries%"
        )
        new_name = self.replace_token(
            new_name, meta_data.alternate_number, "%alternatenumber%"
        )
        new_name = self.replace_token(
            new_name, meta_data.alternate_count, "%alternatecount%"
        )
        new_name = self.replace_token(new_name, meta_data.imprint, "%imprint%")
        new_name = self.replace_token(new_name, meta_data.format, "%format%")
        new_name = self.replace_token(
            new_name, meta_data.maturity_rating, "%maturityrating%"
        )
        new_name = self.replace_token(new_name, meta_data.story_arc, "%storyarc%")
        new_name = self.replace_token(new_name, meta_data.series_group, "%seriesgroup%")
        new_name = self.replace_token(new_name, meta_data.scan_info, "%scaninfo%")

        if self.smart_cleanup:

            # remove empty braces,brackets, parentheses
            new_name = re.sub(r"\(\s*[-:]*\s*\)", "", new_name)
            new_name = re.sub(r"\[\s*[-:]*\s*\]", "", new_name)
            new_name = re.sub(r"\{\s*[-:]*\s*\}", "", new_name)

            # remove duplicate spaces
            new_name = " ".join(new_name.split())

            # remove remove duplicate -, _,
            new_name = re.sub(r"[-_]{2,}\s+", "-- ", new_name)
            new_name = re.sub(r"(\s--)+", " --", new_name)
            new_name = re.sub(r"(\s-)+", " -", new_name)

            # remove dash or double dash at end of line
            new_name = re.sub(r"[-]{1,2}\s*$", "", new_name)

            # remove duplicate spaces (again!)
            new_name = " ".join(new_name.split())

        if ext is None:
            ext = Path(filename).suffix

        new_name += ext

        # some tweaks to keep various filesystems happy
        new_name = new_name.replace("/", "-")
        new_name = new_name.replace(" :", " -")
        new_name = new_name.replace(": ", " - ")
        new_name = new_name.replace(":", "-")
        new_name = new_name.replace("?", "")

        return new_name
