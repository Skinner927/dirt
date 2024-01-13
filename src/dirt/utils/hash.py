"""Hashing utilities.

**Table of Contents**

- `hashlib_new()`: Forwards compatible wrapper around `hashlib.new()`.
- `hash_file()`: Hash a single file.
- `hash_iterable_file_contents()`: Hash a sequence of files.
- `hash_update_open_binary_file()`: Update HASH with an open binary file.
"""
from __future__ import annotations

import concurrent.futures
import functools
import hashlib
import io
import logging
import os
import threading
from pathlib import Path
from typing import BinaryIO, Final, Iterable, Optional, Protocol, Tuple, Union

from dirt import const

__all__ = [
    "BLAKE2_FOR_ARCH",
    "HASH",
    "hashlib_new",
    "hash_file",
    "hash_iterable_file_contents",
    "hash_update_open_binary_file",
]


BUFFER_SIZE: int = 2**18
DEFAULT_ALGO: str = "md5"
BLAKE2_FOR_ARCH: Final[str] = "blake2b" if const.IS_64bit else "blake2s"
logger = logging.getLogger(__name__)


class HASH(Protocol):
    # Because hashlib._hashlib.HASH doesn't seem to work
    def digest(self) -> bytes:
        ...

    def hexdigest(self) -> str:
        ...

    def update(self, data: bytes | memoryview) -> None:
        ...


# Forward compat
def hashlib_new(
    algo: str = DEFAULT_ALGO, data: bytes = b"", usedforsecurity: bool = True, **kwargs
) -> "HASH":
    if const.PY_GE_39:
        return hashlib.new(algo, data, usedforsecurity=usedforsecurity, **kwargs)  # type: ignore
    return hashlib.new(algo, data, **kwargs)


def hash_update_open_binary_file(
    file: BinaryIO | io.BytesIO | io.BufferedIOBase,
    hash_obj: HASH,
    buffer: bytearray,
    view: Optional[memoryview] = None,
) -> None:
    """Update hash object with hash of an open binary file.

    Copied/derived from Python 3.11 hashlib.file_digest()
    https://github.com/python/cpython/blob/4f97d64c831c94660ceb01f34d51fa236ad968b0/Lib/hashlib.py

    :param file: File open in binary read mode ("rb").
    :param hash_obj: Hashlib hash (e.g. `hashlib.md5()`)
    :param buffer: Pre-allocated scratch buffer to read file chunks into.
    :param view: Pass a `memoryview` that wraps the buffer. If one is not passed,
        one will be created. This option is for performance.
    :return: When done reading file into digest, nothing is returned.
    """
    if hasattr(file, "getbuffer"):
        # io.BytesIO object, use zero-copy buffer
        hash_obj.update(file.getbuffer())
        return

    # Only binary files implement readinto().
    if not (
        hasattr(file, "readinto") and hasattr(file, "readable") and file.readable()
    ):
        raise ValueError(
            f"'{file!r}' is not a file-like object in binary reading mode."
        )

    if view is None:
        view = memoryview(buffer)

    while True:
        # Was checked above for readinto
        size: None | int = file.readinto(buffer)  # type: ignore
        if not size:
            break  # EOF
        hash_obj.update(view[:size])


def hash_file(
    path: Union[str, os.PathLike[str]],
    buffer: Optional[bytearray] = None,
    view: Optional[memoryview] = None,
    hash_file_path: bool = True,
    hash_obj_or_name: str | HASH = DEFAULT_ALGO,
) -> str:
    """Hash a single file."""
    # Ensure path is absolute
    path = Path(path).resolve(strict=True)

    if buffer is None:
        buffer = bytearray(BUFFER_SIZE)
    if view is None:
        view = memoryview(buffer)

    if isinstance(hash_obj_or_name, str):
        digest = hashlib_new(hash_obj_or_name, usedforsecurity=False)
    else:
        digest = hash_obj_or_name

    if hash_file_path:
        # Start digest with file name
        digest.update(str(path).encode("utf-8"))

    with path.open("rb") as fb:
        hash_update_open_binary_file(fb, hash_obj=digest, buffer=buffer, view=view)
    return digest.hexdigest()


def _hash_contents_pool_worker(
    file_name: os.PathLike[str] | str,
    *,
    prefix_content_with_path: bool,
    algo: str = DEFAULT_ALGO,
) -> Tuple[str, Union[bytes, Exception]]:
    """Worker for hash_iterable_file_contents()."""
    file_name = str(file_name)
    try:
        tls = threading.local()
        # Init
        buf_view: Tuple[bytearray, memoryview]
        try:
            buf_view = tls.hash_file_buffer
        except AttributeError:
            _buffer = bytearray(BUFFER_SIZE)
            buf_view = _buffer, memoryview(_buffer)
            tls.hash_file_buffer = buf_view

        buffer, view = buf_view

        digest = hashlib_new(algo, usedforsecurity=False)
        with open(file_name, "rb") as fb:
            # Add filename first
            if prefix_content_with_path:
                digest.update(file_name.encode("utf-8"))
            # Then add file contents
            hash_update_open_binary_file(fb, hash_obj=digest, buffer=buffer, view=view)
        return file_name, digest.digest()
    except Exception as e:
        return file_name, e


def hash_iterable_file_contents(
    files: Iterable[os.PathLike[str] | str],
    hash_obj_or_name: str | HASH,
    *,
    sort_files: bool = True,
    hash_file_paths: bool = True,
    max_workers: int = 12,
    ignore_file_errors: bool = True,
) -> Tuple[HASH, int]:
    """Hash all file contents in the given iterable.

    :param files: Paths to files to hash. Paths should be absolute, but not required.
    :param hash_obj_or_name:
    :param sort_files: False if files are already sorted or order should be preserved.
    :param hash_file_paths: Include the file paths in the hashes.
    :param max_workers:
    :param ignore_file_errors: If True, skip files that cause errors; such as files that
        don't exist and files we don't have permission to read.
    :return: Hash object, Number of files hashed
    """
    my_logger = logger.getChild(hash_iterable_file_contents.__name__)
    if isinstance(hash_obj_or_name, str):
        hash_obj = hashlib_new(hash_obj_or_name, usedforsecurity=False)
    else:
        hash_obj = hash_obj_or_name

    # Always convert to str
    str_files: Iterable[str] = (str(f) for f in files)
    if sort_files:
        str_files = sorted(str_files)
    max_workers = min(max_workers, (os.cpu_count() or 1) + 4)

    # Faster with 1 file (only works with list, tuple, etc.)
    try:
        num_files = len(str_files)  # type: ignore
    except Exception:
        num_files = -1
    if 0 == num_files:
        return hash_obj, 0
    elif 1 == num_files:
        try:
            hash_file(
                str_files[0],  # type: ignore
                hash_file_path=hash_file_paths,
                hash_obj_or_name=hash_obj,
            )
            return hash_obj, 1
        except Exception:
            # Do it the regular way
            pass

    # worker function
    worker = functools.partial(
        _hash_contents_pool_worker,
        hash_file_paths=hash_file_paths,
    )

    num_files = 0
    with concurrent.futures.ThreadPoolExecutor(max_workers=max_workers) as pool:
        file_name: str
        digest_or_err: Union[bytes, Exception]
        for file_name, digest_or_err in pool.map(worker, str_files):
            if isinstance(digest_or_err, Exception):
                if ignore_file_errors:
                    my_logger.debug(
                        "Ignored file error %s: %s", file_name, digest_or_err
                    )
                    continue
                raise digest_or_err
            num_files += 1
            hash_obj.update(digest_or_err)
    return hash_obj, num_files
