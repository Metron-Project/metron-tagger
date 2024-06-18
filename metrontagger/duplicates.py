"""Module to find and remove any duplicate pages from a directory of comics."""

# Copyright 2023 Brian Pepple
from __future__ import annotations

import io
from dataclasses import dataclass
from itertools import groupby
from pathlib import Path

import pandas as pd
import questionary
from darkseid.comic import Comic
from imagehash import average_hash
from PIL import Image, UnidentifiedImageError

from metrontagger.styles import Styles


@dataclass
class DuplicateIssue:
    """A data class representing a duplicate issue.

    This class stores information about a duplicate issue, including the path to the file and a list of page indices.

    Args:
        path_: str: The path to the file with the duplicate issue.
        pages_index: list[int]: A list of page indices where the duplicate issue occurs.

    Returns:
        str: A string representation of the DuplicateIssue object.
    """

    path_: str
    pages_index: list[int]

    def __repr__(self: DuplicateIssue) -> str:
        return f"{self.__class__.__name__}(name={Path(self.path_).name})"


class Duplicates:
    """A class for handling duplicate comic book pages.

    This class provides methods for identifying duplicate pages in a list of comic book files and performing actions
    on them.

    Args:
        file_lst: list[Path]: A list of file paths to the comic book files.

    Returns:
        None
    """

    def __init__(self: Duplicates, file_lst: list[Path]) -> None:
        """Initialize the Duplicates class with a list of file paths.

        This method sets the list of file paths and initializes the data frame to None.


        Args:
            file_lst: list[Path]: A list of file paths to be processed.

        Returns:
            None
        """

        self._file_lst = file_lst
        self._data_frame: pd.DataFrame | None = None

    def _image_hashes(self: Duplicates) -> list[dict[str, any]]:
        """Method to get a list of dictionaries containing the file path, page index, and page hashes.

        This method iterates over the file list, extracts page hashes for each comic, and stores the information in
        dictionaries.

        Returns:
            list[dict[str, any]]: A list of dictionaries containing file path, page index, and page hashes.
        """

        hashes_lst = []
        for item in self._file_lst:
            comic = Comic(item)
            if not comic.is_writable():
                questionary.print(f"'{comic}' is not writable. Skipping...")
                continue
            questionary.print(
                f"Attempting to get page hashes for '{comic}'.",
                style=Styles.WARNING,
            )
            for i in range(comic.get_number_of_pages()):
                try:
                    with Image.open(io.BytesIO(comic.get_page(i))) as img:
                        try:
                            img_hash = average_hash(img)
                        except OSError:
                            questionary.print(
                                f"Unable to get image hash for page {i} of '{comic}'",
                                style=Styles.ERROR,
                            )
                            continue
                        image_info = {
                            "path": str(comic.path),
                            "index": i,
                            "hash": str(img_hash),
                        }
                        hashes_lst.append(image_info)
                except UnidentifiedImageError:
                    questionary.print(
                        f"UnidentifiedImageError: Skipping page {i} of '{comic}'",
                        style=Styles.ERROR,
                    )
                    continue
        return hashes_lst

    def _get_page_hashes(self: Duplicates) -> pd.DataFrame:
        """Method to get a DataFrame of comics with duplicate pages.

        This method calls _image_hashes to retrieve page hashes, creates a DataFrame, and filters out duplicates
        based on hash values.

        Returns:
            pd.DataFrame: A DataFrame containing comics with duplicate pages.
        """

        comic_hashes = self._image_hashes()
        self._data_frame = pd.DataFrame(comic_hashes)
        hashes = self._data_frame["hash"]
        return self._data_frame[hashes.isin(hashes[hashes.duplicated()])].sort_values("hash")

    def get_distinct_hashes(self: Duplicates) -> list[str]:
        """Method to get distinct hash values.

        This method retrieves page hashes, identifies distinct hash values, and returns a list of unique hash values.


        Returns:
            list[str]: A list of distinct hash values.
        """

        page_hashes = self._get_page_hashes()
        return [key for key, _group in groupby(page_hashes["hash"])]

    def get_comic_info_for_distinct_hash(self: Duplicates, img_hash: str) -> DuplicateIssue:
        """Method to retrieve comic information for a distinct hash value.

        This method takes a hash value, finds the corresponding comic information in the data frame, and returns a
        DuplicateIssue object with the comic's path and page index.


        Args:
            img_hash: str: The hash value to search for in the data frame.

        Returns:
            DuplicateIssue: A DuplicateIssue object representing the comic information.
        """

        idx = self._data_frame.loc[self._data_frame["hash"] == img_hash].index[0]
        row = self._data_frame.iloc[idx]
        return DuplicateIssue(row["path"], row["index"])

    def get_comic_list_from_hash(self: Duplicates, img_hash: str) -> list[DuplicateIssue]:
        """Method to get a list of DuplicateIssue objects from a hash value.

        This method retrieves comic information from the data frame based on the hash value and returns a list of
        DuplicateIssue objects.


        Args:
            img_hash: str: The hash value to search for in the data frame.

        Returns:
            list[DuplicateIssue]: A list of DuplicateIssue objects representing comics with the specified hash value.
        """

        comic_lst = []
        for i in self._data_frame.loc[self._data_frame["hash"] == img_hash].index:
            row = self._data_frame.iloc[i]
            comic_lst.append(DuplicateIssue(row["path"], [row["index"]]))
        return comic_lst

    @staticmethod
    def delete_comic_pages(dups_lst: list[DuplicateIssue]) -> None:
        """Method to delete pages from a comic.

        This method iterates over a list of DuplicateIssue objects, attempts to remove the specified pages from each
        comic, and provides feedback on the success of the operation.


        Args:
            dups_lst: list[DuplicateIssue]: A list of DuplicateIssue objects representing duplicate pages to be removed.

        Returns:
            None
        """

        for item in dups_lst:
            comic = Comic(item.path_)
            if comic.remove_pages(item.pages_index):
                questionary.print(
                    f"Removed duplicate pages from {comic}",
                    style=Styles.SUCCESS,
                )
            else:
                questionary.print(
                    f"Failed to remove duplicate pages from {comic}",
                    style=Styles.WARNING,
                )

    @staticmethod
    def show_image(first_comic: DuplicateIssue) -> None:
        """Method to show the user an image from a comic.

        This method takes a DuplicateIssue object, retrieves the image data, and displays the image to the user.


        Args:
            first_comic: DuplicateIssue: The DuplicateIssue object representing the comic to display.

        Returns:
            None
        """

        comic = Comic(first_comic.path_)
        # noinspection PyTypeChecker
        img_data = comic.get_page(first_comic.pages_index)
        try:
            image = Image.open(io.BytesIO(img_data))
        except UnidentifiedImageError:
            questionary.print(
                f"Unable to show image from {comic}.",
                style=Styles.WARNING,
            )
            return
        image.show()
