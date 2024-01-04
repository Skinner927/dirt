from __future__ import annotations

import argparse
import functools
from pathlib import Path
from typing import Any, Literal, Optional, TypeVar, Union, overload, Callable, Type

import simple_parsing.helpers.fields

from dirt.settings.actions import PathOptionalAction

try:
    from simple_parsing.helpers.fields import _MISSING_TYPE, MISSING
except ImportError:
    # This is what simple_parsing.helpers.fields actually does
    from dataclasses import _MISSING_TYPE, MISSING

__all__ = [
    "field",
    "choice",
    "list_field",
    "dict_field",
    "mutable_field",
    "subparsers",
    "flag",
    "file_path",
]

ActionCls = Union[Callable[..., argparse.Action], Type[argparse.Action]]
T = TypeVar("T")
FpT = Union[Path, None]

# re-export from simple_parsing
field = simple_parsing.helpers.fields.field
choice = simple_parsing.helpers.fields.choice
list_field = simple_parsing.helpers.fields.list_field
dict_field = simple_parsing.helpers.fields.dict_field
mutable_field = simple_parsing.helpers.fields.mutable_field
subparsers = simple_parsing.helpers.fields.subparsers
flag = simple_parsing.helpers.fields.flag


_file_path_defaults = dict(init=True, repr=True, hash=True, compare=True)


@overload
def file_path(
    *,
    default: Union[None, _MISSING_TYPE] = MISSING,
    alias: str | list[str] | None = None,
    cmd: bool = True,
    positional: bool = False,
    ensure_path: None = None,
    action: ActionCls | None = None,
    **kwargs: Any,
) -> Optional[Path]:
    ...


@overload
def file_path(
    *,
    default: Union[None, _MISSING_TYPE] = MISSING,
    alias: str | list[str] | None = None,
    cmd: bool = True,
    positional: bool = False,
    ensure_path: Literal["exists", "dir", "file"],
    action: None = None,
    **kwargs: Any,
) -> Path:
    ...


@overload
def file_path(
    *,
    default: Path,
    alias: str | list[str] | None = None,
    cmd: bool = True,
    positional: bool = False,
    ensure_path: Literal["exists", "dir", "file"] | None = None,
    action: ActionCls | None = None,
    **kwargs: Any,
) -> Path:
    ...


def file_path(
    *,
    default: FpT | _MISSING_TYPE = MISSING,
    alias: str | list[str] | None = None,
    cmd: bool = True,
    positional: bool = False,
    ensure_path: Literal["exists", "dir", "file"] | None = None,
    action: ActionCls | None = None,
    **kwargs: Any,
) -> FpT:
    # Defaults that I don't care to add to args
    for key, val in _file_path_defaults.items():
        if key not in kwargs:
            kwargs[key] = val

    if ensure_path:
        if action is not None:
            raise ValueError("'ensure_path' cannot be set if 'action' is also set")
        action = functools.partial(PathOptionalAction, ensure_path=ensure_path)
    elif action is None:
        action = PathOptionalAction

    return field(
        default=default,
        alias=alias,
        cmd=cmd,
        positional=positional,
        action=action,
        to_dict=True,
        encoding_fn=lambda pp: str(pp) if pp else None,
        decoding_fn=lambda aa: Path(aa).resolve() if aa else None,
        **kwargs,
    )
