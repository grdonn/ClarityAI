from __future__ import annotations

from pathlib import Path
from typing import Dict, Iterable, Iterator, List

import pandas as pd


def read_csv_safely(
    path: Path,
    usecols: List[str] | None = None,
    dtype: Dict[str, str] | None = None,
    nrows: int | None = None,
    chunksize: int | None = None,
) -> pd.DataFrame:
    if chunksize:
        frames = []
        for chunk in pd.read_csv(
            path,
            usecols=usecols,
            dtype=dtype,
            nrows=nrows,
            chunksize=chunksize,
        ):
            frames.append(chunk)
        if not frames:
            return pd.DataFrame(columns=usecols)
        return pd.concat(frames, ignore_index=True)

    return pd.read_csv(path, usecols=usecols, dtype=dtype, nrows=nrows)


def iter_csv_chunks(
    path: Path,
    usecols: List[str] | None = None,
    dtype: Dict[str, str] | None = None,
    nrows: int | None = None,
    chunksize: int | None = None,
) -> Iterator[pd.DataFrame]:
    if not chunksize:
        yield pd.read_csv(path, usecols=usecols, dtype=dtype, nrows=nrows)
        return

    for chunk in pd.read_csv(
        path,
        usecols=usecols,
        dtype=dtype,
        nrows=nrows,
        chunksize=chunksize,
    ):
        yield chunk
