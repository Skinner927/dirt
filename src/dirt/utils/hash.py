"""Hashing utilities."""
from __future__ import annotations

import concurrent.futures
import functools
import hashlib
import io
import itertools
import logging
import os
import sys
import threading
from pathlib import Path
from typing import BinaryIO, ClassVar, List, Optional, Protocol, Tuple

from dirt.utils.fs import find


class HASH(Protocol):
    # Because hashlib._hashlib.HASH doesn't seem to work
    def digest(self) -> bytes:
        ...

    def hexdigest(self) -> str:
        ...

    def update(self, data: bytes | memoryview) -> None:
        ...


class InvalidHashError(Exception):
    pass


# Forward compat
def hashlib_new(algo: str, usedforsecurity: bool = True) -> "HASH":
    if sys.version_info >= (3, 9, 0):
        return hashlib.new(algo, usedforsecurity=usedforsecurity)  # type: ignore
    return hashlib.new(algo)


logger = logging.getLogger(__name__)


def hash_file_digest(
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
    path: Path,
    buffer_size: int = 2**18,
    buffer: Optional[bytearray] = None,
    view: Optional[memoryview] = None,
    add_path_to_hash: bool = False,
    algo: str = "md5",
) -> str:
    # Copied Py3.11 hashlib.file_digest()
    # https://github.com/python/cpython/blob/0b13575e74ff3321364a3389eda6b4e92792afe1/Lib/hashlib.py3
    # binary file, socket.SocketIO object
    # Note: socket I/O uses different syscalls than file I/O.

    # Ensure path is absolute
    path = path.absolute()

    if buffer is None:
        buffer = bytearray(buffer_size)
    if view is None:
        view = memoryview(buffer)

    digest = hashlib_new(algo, usedforsecurity=False)
    if add_path_to_hash:
        # Start digest with file name
        digest.update(str(path).encode("utf-8"))

    with path.open("rb") as fb:
        hash_file_digest(fb, hash_obj=digest, buffer=buffer, view=view)
    return digest.hexdigest()


class HashPath:
    _hash_name: ClassVar[str] = "md5"

    def __init__(self, path: Path, buffer_size: int = 2**18) -> None:
        if not path.is_file() and not path.is_dir():
            raise OSError(f"{path} is not a file or directory")

        self._path = path.resolve()
        self._scratch_buffer_size = buffer_size
        """Scratch buffer size for reading files for hashing.

        Value comes from `hashlib.file_digest()`.
        """

    @property
    def path(self) -> Path:
        return self._path

    @functools.lru_cache()
    def hash_filenames(self) -> str:
        """Hash of all the file names in the path.

        This is faster, but not as thorough as `hash_contents()`. This does not check
        file contents, just all the file names.
        """
        digest = self._new_hash()
        for item in self._get_sorted_filenames():
            digest.update(item.encode("utf-8"))
        return digest.hexdigest()

    @functools.lru_cache()
    def hash_contents(self) -> str:
        """Hash all files and their contents in the path.

        This is slower, but more thorough than `hash_filenames()`.
        """
        # Hash everything with worker threads
        # Similar to how ThreadPoolExecutor does it except we max at 12 not 32
        max_workers = min(12, (os.cpu_count() or 1) + 4)
        hash_sum = self._new_hash()
        with concurrent.futures.ThreadPoolExecutor(max_workers=max_workers) as pool:
            for file_digest in pool.map(
                self._hash_contents_pool_worker,
                self._get_sorted_filenames(),
                itertools.repeat(self._scratch_buffer_size),
            ):
                hash_sum.update(file_digest)
        return hash_sum.hexdigest()

    @classmethod
    def _hash_contents_pool_worker(cls, file_name: str, buffer_size: int) -> bytes:
        tls = threading.local()
        # Init
        buf_view: Tuple[bytearray, memoryview]
        try:
            buf_view = tls.hash_file_buffer
        except AttributeError:
            _buffer = bytearray(buffer_size)
            buf_view = _buffer, memoryview(_buffer)
            tls.hash_file_buffer = buf_view

        buffer, view = buf_view

        digest = cls._new_hash()
        with open(file_name, "rb") as fb:
            # Add filename first
            digest.update(str(file_name).encode("utf-8"))
            # Then add file contents
            hash_file_digest(fb, hash_obj=digest, buffer=buffer, view=view)
        return digest.digest()

    @classmethod
    def _new_hash(cls) -> HASH:
        while cls._hash_name is None:
            failed_algo = set()
            # Prefer MD5
            for name in itertools.chain(("md5",), hashlib.algorithms_guaranteed):
                try:
                    hash_obj = hashlib_new(name, usedforsecurity=False)
                    cls._hash_name = name
                    return hash_obj
                except Exception as e:
                    failed_algo.add((name, str(e)))
            # how??
            raise RuntimeError(f"Failed to find working hash algorithms: {failed_algo}")
        return hashlib_new(cls._hash_name, usedforsecurity=False)

    @functools.lru_cache()
    def _get_sorted_filenames(self, skip_hidden: bool = True) -> List[str]:
        """Return sorted list of all filenames in path.

        Sorted to ensure no changes
        """
        if self._path.is_file():
            return [str(self._path)]
        else:
            return sorted(
                str(p.resolve())
                for p in find(
                    self._path,
                    kind="file",
                    skip_hidden_file=skip_hidden,
                    skip_hidden_dir=skip_hidden,
                )
            )
