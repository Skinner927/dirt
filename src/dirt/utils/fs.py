"""Filesystem utility functions."""
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
from typing import (
    BinaryIO,
    ClassVar,
    Iterable,
    List,
    Literal,
    Optional,
    Protocol,
    Set,
    Tuple,
)


class HASH(Protocol):
    # Because hashlib._hashlib.HASH doesn't seem to work
    def digest(self) -> bytes:
        ...

    def hexdigest(self) -> str:
        ...

    def update(self, data: bytes) -> None:
        ...


# Forward compat
def hashlib_new(algo: str) -> "HASH":
    if sys.version_info >= (3, 9, 0):
        return hashlib.new(algo, usedforsecurity=True)
    return hashlib.new(algo)


logger = logging.getLogger(__name__)

find_kind_t = Literal["file", "dir", "symlink", "fifo"]


def find(
    start_dir: Path | str,
    glob_pattern: str = "*",
    *,
    down: bool = True,
    kind: Optional[Set[find_kind_t] | find_kind_t] = None,
    skip_hidden_dir: bool = True,
    skip_hidden_file: bool = True,
) -> Iterable[Path]:
    """Walk the path up/down and yield all files and/or dirs matching the pattern.

    :param start_dir: Directory where to start walking. If this is a file, its parent
        will be used.
    :param glob_pattern: Specify glob to match against name of what will be yielded.
        This does not influence what directories will be traversed.
    :param down: True to walk deeper down the file system. False to walk up the file
        system to root.

    :param kind: Limit what is yielded. `None` yields everything.
    :param skip_hidden_dir: If True, hidden directories will not be yielded and not
        searched.
    :param skip_hidden_file: If True, hidden files (including symlinks, fifo, etc.)
        will not be yielded.
    :return: Matching file system elements
    """
    if isinstance(start_dir, str):
        start_dir = Path(start_dir)
    if isinstance(kind, str):
        kind = {kind}

    if not start_dir.is_dir():
        # Need a dir
        start_dir = start_dir.parent
    start_dir = start_dir.resolve()
    if not start_dir.is_dir():
        raise OSError(f"{start_dir=} is not a file or directory")
    _kind_fns = {f"is_{k}" for k in (kind or ())}

    def is_visible(pp: Path) -> bool:
        pp_is_dir = pp.is_dir()
        if pp.name.startswith(".") and (
            (skip_hidden_dir and pp_is_dir) or (skip_hidden_file and not pp_is_dir)
        ):
            # Skip hidden files and dirs
            return False
        return True

    def can_yield(pp: Path, *, check_visibility: bool = True) -> bool:
        if check_visibility and not is_visible(pp):
            return False
        # Things we yield must match glob and kind
        if not pp.match(glob_pattern):
            # Doesn't match the pattern
            return False
        if kind is not None and not any(getattr(pp, name)() for name in _kind_fns):
            # Only yield those that match kind
            return False
        return True

    # Iterate
    if down:
        # Walking down
        dir_stack: List[Path] = [start_dir]
        dir_seen: Set[str] = {str(start_dir)}

        # need to manually yield first down
        if can_yield(start_dir):
            yield start_dir

        while dir_stack:
            current = dir_stack.pop()
            # Find all the children
            for child in current.iterdir():
                if not is_visible(child):
                    # Skip hidden files and dirs
                    continue
                if can_yield(child, check_visibility=False):
                    yield child

                if child.is_dir():
                    # is directory, if we haven't seen it, add it to the stack
                    child = child.resolve()
                    child_str = str(child)
                    if child_str not in dir_seen:
                        # Haven't seen it
                        dir_seen.add(child_str)
                        dir_stack.append(child)
    else:
        # Walking up
        current = start_dir
        while current:
            # Yield all content of current
            for child in current.iterdir():
                if can_yield(child):
                    yield child
            # Parent is next
            parent = current.parent.resolve()
            if not parent or parent == current:
                # Our parent is ourselves, that usually means we're the root
                # so yield ourselves because we have no parent that will, and
                # exit the loop.
                if can_yield(current):
                    yield current
                break
            current = parent


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

    digest = hashlib_new(algo)
    if add_path_to_hash:
        # Start digest with file name
        digest.update(str(path).encode("utf-8"))

    with path.open("rb") as fb:
        if hasattr(fb, "getbuffer"):
            # io.BytesIO object, use zero-copy buffer
            digest.update(fb.getbuffer())
            return digest.hexdigest()

        # Read file into digest
        while True:
            size = fb.readinto(buffer)
            if 0 == size:
                break  # EOF
            digest.update(view[:size])
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
        with concurrent.futures.ThreadPoolExecutor(
            max_workers=max_workers, initializer=self._init_tls_hash_file_buffer
        ) as pool:
            for file_digest in pool.map(
                self._hash_contents_pool_worker, self._get_sorted_filenames()
            ):
                hash_sum.update(file_digest)
        return hash_sum.hexdigest()

    def _init_tls_hash_file_buffer(self) -> None:
        """Create thread local buffer for reading files."""
        tls = threading.local()
        buffer = bytearray(self._scratch_buffer_size)
        view = memoryview(buffer)
        tls.hash_file_buffer = (buffer, view)

    @classmethod
    def _hash_contents_pool_worker(
        cls,
        file_name: str,
    ) -> bytes:
        buf_view: Tuple[bytearray, memoryview] = threading.local().hash_file_buffer
        buffer, view = buf_view

        digest = cls._new_hash()
        with open(file_name, "rb") as fb:
            # Add filename first
            digest.update(str(file_name).encode("utf-8"))
            # Then add file contents
            cls._read_binary_file_into_hash(fb, digest=digest, buffer=buffer, view=view)
        return digest.digest()

    @classmethod
    def _new_hash(cls) -> HASH:
        while cls._hash_name is None:
            try:
                # Prefer MD5
                for name in itertools.chain(("md5",), hashlib.algorithms_guaranteed):
                    hash_obj = hashlib_new(name)
                    cls._hash_name = name
                    return hash_obj
            except Exception:
                continue
            # how??
            raise RuntimeError("Failed to find working hash algorithm")
        return hashlib_new(cls._hash_name)

    @functools.lru_cache()
    def _get_sorted_filenames(self) -> List[str]:
        """Return sorted list of all filenames in path.

        Sorted to ensure no changes
        """
        if self._path.is_file():
            return [str(self._path)]
        else:
            return sorted(set(str(p.resolve()) for p in find(self._path, kind="file")))

    @staticmethod
    def _read_binary_file_into_hash(
        file: BinaryIO | io.BytesIO,
        hash_obj: HASH,
        buffer: bytearray,
        view: Optional[memoryview] = None,
    ) -> None:
        """Fill digest with hash of open binary file.

        Copied/derived from Python 3.11 hashlib.file_digest()
        https://github.com/python/cpython/blob/0b13575e74ff3321364a3389eda6b4e92792afe1/Lib/hashlib.py3

        :param file: File open in binary read mode ("rb").
        :param hash_obj: Hashlib hash (e.g. `hashlib.md5()`)
        :param buffer: Pre-allocated scratch buffer to read file chunks into.
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

        # TODO: can readinto(view) work? Then this fn would only pass view
        if view is None:
            view = memoryview(buffer)
        while True:
            size: None | int = file.readinto(buffer)
            if not size:
                break  # EOF
            hash_obj.update(view[:size])
