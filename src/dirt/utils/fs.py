"""Filesystem utility functions."""
from __future__ import annotations

import concurrent.futures
import contextlib
import functools
import hashlib
import io
import logging
import os
import queue
from pathlib import Path
from typing import (
    TYPE_CHECKING,
    BinaryIO,
    Collection,
    Iterable,
    List,
    Literal,
    NamedTuple,
    Optional,
    Set,
    Tuple,
    Union,
)

HashWorkerResult = NamedTuple("HashWorkerResult", [("path", str), ("hash", str)])
HashWorkerExit = NamedTuple(
    "HashWorkerExit", [("worker_id", int), ("error", Union[None, str])]
)

if TYPE_CHECKING:
    hash_t = hashlib._Hash
    hash_worker_work_q_t = queue.Queue[Union[str, None]]
    hash_worker_result_q_t = queue.Queue[Union[HashWorkerResult, HashWorkerExit]]
else:
    hash_t = "hashlib._Hash"
    hash_worker_work_q_t = queue.Queue
    hash_worker_result_q_t = queue.Queue


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
    :param down: True to walk deeper down the file system, False to walk up the file
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

    # need to manually yield first down
    if down and can_yield(start_dir):
        yield start_dir

    dir_stack: List[Path] = [start_dir]
    dir_seen: Set[str] = {str(start_dir)}
    while dir_stack:
        current = dir_stack.pop()
        if not down:
            # Going up, add current's parent to dir_stack if we haven't seen it
            # also yield it if it can be yielded
            parent = current.parent.resolve()
            if parent.is_dir() and is_visible(parent):
                parent_str = str(parent)
                if parent_str not in dir_seen:
                    dir_seen.add(parent_str)
                    dir_stack.append(parent)
                elif parent not in dir_stack and can_yield(
                    parent, check_visibility=False
                ):
                    yield parent

        # Find all the children
        for child in current.glob("*"):
            if not is_visible(child):
                # Skip hidden files and dirs
                continue
            if can_yield(child, check_visibility=False):
                yield child.resolve()

            if down and child.is_dir():
                # Going down
                # is directory, if we haven't seen it, add it to the stack
                child = child.resolve()
                child_str = str(child)
                if child_str not in dir_seen:
                    # Haven't seen it
                    dir_seen.add(child_str)
                    dir_stack.append(child)


def find_walking_up(
    start: Path,
    *,
    names: Collection[str],
    kind: Optional[Literal["dir", "file"]] = None,
    on_circular: Optional[Literal["raise", "ignore"]] = "ignore",
) -> Union[Path, None]:
    """Walk up directory tree from `start` to root looking for `names`.

    :param start: Where to start the search.
    :param names: One or more items to find.
    :param kind: Specify "file" or "dir" to limit search to specific types.
     `None` only checks if it exists.
    :param on_circular: "raise" will raise a RecursionError if a loop in
     the file system is detected. "ignore" or `None` will return `None.
    :return: Found Path or `None` if not found. Returned path will be
     resolved with `pathlib.resolve()` which makes the path
     absolute, resolving all symlinks on the way and also normalizing it.
    :raises: RecursionError if a loop in the file system is detected.
    """
    if isinstance(names, str):
        names = [names]
    seen: Set[str] = set()
    last: Optional[Path] = None
    # Current must be resolved else the `while !=` comparison doesn't work.
    current: Optional[Path] = start.resolve()
    while current and current != last:
        last = current
        current_str = str(current)
        # Check for loops
        if current_str in seen:
            msg = f"{find_walking_up.__name__}() - circular pathing detected: {current}"
            logger.debug(msg)
            if "raise" == on_circular:
                raise RecursionError(msg)
            return None
        seen.add(current_str)

        # Check for dirt.ini or .dirt.ini file
        for target_name in names:
            target = current / target_name
            if "dir" == kind:
                if target.is_dir():
                    return target.resolve()
            elif "file" == kind:
                if target.is_file():
                    return target.resolve()
            else:
                if target.exists():
                    return target.resolve()
        # Crawl up
        current = current.parent.resolve()
    return None


def _xx_hash_file(path: Path, buffer_size: int = 2**18) -> str:
    # Ensure path is absolute
    path = path.absolute()

    # Copied Py3.11 hashlib.file_digest()
    # https://github.com/python/cpython/blob/0b13575e74ff3321364a3389eda6b4e92792afe1/Lib/hashlib.py3
    # binary file, socket.SocketIO object
    # Note: socket I/O uses different syscalls than file I/O.
    buffer = bytearray(buffer_size)  # Reusable
    view = memoryview(buffer)

    digest = hashlib.md5()
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
        digest = self._new_digest()
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
        worker_count = min(12, (os.cpu_count() or 1) + 4)
        # Create reusable buffers our workers will use
        free_buffers: List[Tuple[bytearray, memoryview]] = []
        for _ in range(worker_count):
            buf = bytearray(self._scratch_buffer_size)
            free_buffers.append((buf, memoryview(buf)))

        # workers = []
        # for i in range(worker_count):
        #     t = threading.Thread(
        #         name=f"hash_worker_{i}",
        #         target=self._hash_contents_worker,
        #         kwargs=dict(idx=i, work_q=work_q, result_q=result_q),
        #         daemon=True,
        #     )
        #     t.start()
        #     workers.append(t)

        work_fn = functools.partial(self._hash_contents_pool_worker)
        with concurrent.futures.ThreadPoolExecutor() as pool:
            pass

    @classmethod
    def _hash_contents_pool_worker(
        cls, file_name: str, buf_view: Tuple[bytearray, memoryview]
    ) -> str:
        buffer, view = buf_view
        digest = cls._new_digest()
        with open(file_name, "rb") as fb:
            # Add filename first
            digest.update(str(file_name).encode("utf-8"))
            # Then add file contents
            cls._read_binary_file_into_digest(
                fb, digest=digest, buffer=buffer, view=view
            )
        return digest.hexdigest()

    @staticmethod
    def _new_digest() -> hash_t:
        return hashlib.md5()

    @staticmethod
    def _walk_path_no_hidden_files(
        start: Path, glob_pattern: str = "*", skip_hidden: bool = True
    ) -> Iterable[str]:
        """Return all files in the given path, skipping hidden files and directories."""
        start = start.resolve()
        if start.is_file():
            if not start.name.startswith("."):
                yield str(start)
            return
        if not start.is_dir():
            raise OSError(f"{start} is not a file or directory")

        dir_stack: List[Path] = [start]
        dir_seen: Set[str] = {str(start)}
        with contextlib.suppress(IndexError):
            # Suppress IndexError when .pop() on an empty stack
            for path in dir_stack.pop().glob(glob_pattern):
                if skip_hidden and path.name.startswith("."):
                    # Skip hidden files and dirs
                    continue
                if path.is_file():
                    # Yield files
                    yield str(path)
                    continue
                if not path.is_dir():
                    continue
                # is directory, if we haven't seen it, add it to the stack
                path = path.resolve()
                path_str = str(path)
                if path_str in dir_seen:
                    # Seen it, skip it
                    continue
                dir_seen.add(path_str)
                dir_stack.append(path)

    def _get_sorted_filenames(self) -> List[str]:
        """Return sorted list of all filenames in path.

        Sorted to ensure no changes
        """
        if self.__sorted_filenames is None:
            if self._path.is_file():
                self.__sorted_filenames = [str(self._path)]
            else:
                # rglob = recursive glob (doesn't error on symlink loop)
                self.__sorted_filenames = sorted(
                    self._walk_path_no_hidden_files(self._path)
                )
        return self.__sorted_filenames

    @staticmethod
    def _read_binary_file_into_digest(
        file: BinaryIO | io.BytesIO,
        digest: hash_t,
        buffer: bytearray,
        view: Optional[memoryview] = None,
    ) -> None:
        """Fill digest with hash of open binary file.

        Copied/derived from Python 3.11 hashlib.file_digest()
        https://github.com/python/cpython/blob/0b13575e74ff3321364a3389eda6b4e92792afe1/Lib/hashlib.py3

        :param file: File open in binary read mode ("rb").
        :param digest: Hashlib hash (e.g. `hashlib.md5()`)
        :param buffer: Pre-allocated scratch buffer to read file chunks into.
        :return: When done reading file into digest, nothing is returned.
        """
        if hasattr(file, "getbuffer"):
            # io.BytesIO object, use zero-copy buffer
            digest.update(file.getbuffer())
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
            digest.update(view[:size])
