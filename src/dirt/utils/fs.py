"""Filesystem utility functions."""
from __future__ import annotations

import re
from pathlib import Path
from typing import Generator, List, Literal, Optional, Set, Union

find_kind_t = Literal["file", "dir", "symlink", "fifo"]

# TODO: Would be cool if find could return a special type that is Iterable
#   but also has a .first() property to get the first item or None.
def find(
    start_dir: Path | str,
    full_pattern: Union[None, re.Pattern[str], str] = None,
    *,
    down: bool = True,
    kind: Optional[Set[find_kind_t] | find_kind_t] = None,
    skip_hidden_dir: bool = True,
    skip_hidden_file: bool = True,
) -> Generator[Path, None, None]:
    """Walk the path up/down and yield all files and/or dirs matching the pattern.

    :param start_dir: Directory where to start walking. If this is a file, its parent
        will be used.
    :param full_pattern: Specify regular expression to match against name of what
        will be yielded. This compares the absolute path of the object and
        uses `re.search` which allows for partial match. If you require full
        matching, use RegExp `^` and `$` modifiers.
        This does not influence what directories will be traversed.
        `None` ignores the pattern and allows everything (equivalent to `.*`).
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

    if isinstance(full_pattern, str):
        full_pattern = re.compile(full_pattern)

    def can_yield(pp: Path, *, check_visibility: bool = True) -> bool:
        if check_visibility and not is_visible(pp):
            return False
        # Things we yield must match glob and kind
        if full_pattern is not None and full_pattern.search(str(pp)) is None:
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

    return None
