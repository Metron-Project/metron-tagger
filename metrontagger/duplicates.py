"""Module to find and remove any duplicate pages from a directory of comics."""
# Copyright 2023 Brian Pepple

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
    path_: str
    pages_index: list[int]

    def __repr__(self: "DuplicateIssue") -> str:
        return f"{self.__class__.__name__}(name={Path(self.path_).name})"


class Duplicates:
    """Class to find and remove any duplicate pages."""

    def __init__(self: "Duplicates", file_lst: list[Path]) -> None:
        self._file_lst = file_lst
        self._data_frame: pd.DataFrame | None = None

    def _image_hashes(self: "Duplicates") -> list[dict[str, any]]:
        """
        Method to get a list of dicts containing the file path, page index, and page hashes.
        """
        hashes_lst = []
        for item in self._file_lst:
            comic = Comic(str(item))
            if not comic.is_writable():
                questionary.print(f"'{comic}' is not writable. Skipping...")
                continue
            questionary.print(
                f"Attempting to get page hashes for '{comic}'.",
                style=Styles.WARNING,
            )
            for i in range(comic.get_number_of_pages()):
                with Image.open(io.BytesIO(comic.get_page(i))) as img:
                    try:
                        img_hash = average_hash(img)
                    except OSError:
                        questionary.print(
                            f"Unable to get image hash for page {i} of '{comic}'",
                            style=Styles.ERROR,
                        )
                        continue
                    image_info = {"path": str(comic.path), "index": i, "hash": str(img_hash)}
                    hashes_lst.append(image_info)
        return hashes_lst

    def _get_page_hashes(self: "Duplicates") -> pd.DataFrame:
        """Method to get a dataframe of comics with duplicate pages."""
        comic_hashes = self._image_hashes()
        self._data_frame = pd.DataFrame(comic_hashes)
        hashes = self._data_frame["hash"]
        return self._data_frame[hashes.isin(hashes[hashes.duplicated()])].sort_values("hash")

    def get_distinct_hashes(self: "Duplicates") -> list[str]:
        """Method to get distinct hash values."""
        page_hashes = self._get_page_hashes()
        return [key for key, _group in groupby(page_hashes["hash"])]

    def get_comic_info_for_distinct_hash(self: "Duplicates", img_hash: str) -> DuplicateIssue:
        """Method to retrieve first comic instance's path and page index from a hash value."""
        idx = self._data_frame.loc[self._data_frame["hash"] == img_hash].index[0]
        row = self._data_frame.iloc[idx]
        return DuplicateIssue(row["path"], row["index"])

    def get_comic_list_from_hash(self: "Duplicates", img_hash: str) -> list[DuplicateIssue]:
        comic_lst = []
        for i in self._data_frame.loc[self._data_frame["hash"] == img_hash].index:
            row = self._data_frame.iloc[i]
            comic_lst.append(DuplicateIssue(row["path"], [row["index"]]))
        return comic_lst

    @staticmethod
    def delete_comic_pages(dups_lst: list[DuplicateIssue]) -> None:
        """Method to delete pages from a comic."""
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
        """Method to show the user an image from a comic."""
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
