"""Module to find and remove any duplicate pages from a directory of comics."""
# Copyright 2023 Brian Pepple

import io
from itertools import groupby
from pathlib import Path
from typing import Optional

import pandas as pd
import questionary
from darkseid.comic import Comic
from imagehash import average_hash
from PIL import Image

from metrontagger.styles import Styles


class Duplicates:
    """Class to find and remove any duplicate pages."""

    def __init__(self: "Duplicates", file_lst: list[Path]) -> None:
        self.file_lst = file_lst
        self.data_frame: Optional[pd.DataFrame] = None

    def _image_hashes(self: "Duplicates") -> list[dict[str, any]]:
        """
        Method to get a list of dicts containing the file path, page index, and page hashes.
        """
        hashes_lst = []
        for item in self.file_lst:
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

    def get(self: "Duplicates") -> pd.DataFrame:
        """Method to get a dataframe of comics with duplicate pages."""
        comic_hashes = self._image_hashes()
        self.data_frame = pd.DataFrame(comic_hashes)
        hashes = self.data_frame["hash"]
        return self.data_frame[hashes.isin(hashes[hashes.duplicated()])].sort_values("hash")

    @staticmethod
    def reduce_hashes(dupes: pd.DataFrame) -> list[str]:
        """Method to get distinct hash values."""
        return [key for key, _group in groupby(dupes["hash"])]

    def retrieve_comic_path(self: "Duplicates", img_hash: str) -> tuple[str, int]:
        """Method to retrieve first comic instance's path and page index from a hash value."""
        idx = self.data_frame.loc[self.data_frame["hash"] == img_hash].index[0]
        row = self.data_frame.iloc[idx]
        return row["path"], row["index"]

    @staticmethod
    def show_image(comic: str, idx: int) -> None:
        """Method to show the user an image from a comic."""
        c = Comic(comic)
        img_data = c.get_page(idx)
        image = Image.open(io.BytesIO(img_data))
        image.show()
