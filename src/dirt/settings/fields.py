from __future__ import annotations

import argparse
from pathlib import Path
from argparse import ArgumentTypeError
from typing import Any, Callable, Literal, Optional, Type, TypeVar, Union, overload

import simple_parsing.helpers.fields

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


def ResolvedPath(
    ensure_path: Literal["exists", "dir", "file"] | None = None
) -> Callable[[str], Path]:
    def resolve_path(value: str) -> Path:
        path_val: Path
        if isinstance(value, str):
            if not value:
                raise ArgumentTypeError("Cannot convert empty string to Path")
            path_val = Path(value).expanduser()
        elif isinstance(value, Path):
            path_val = value
        else:
            raise ArgumentTypeError(f"Unsupported type passed to Path type: {type(value)}")

        if not ensure_path:
            return path_val.resolve()

        # Ensure resolves to an existing path
        try:
            path_val = path_val.resolve(strict=True)
        except PermissionError:
            raise ArgumentTypeError(f"Invalid permissions for Path '{path_val}'")
        except (FileNotFoundError, OSError):
            raise ArgumentTypeError(f"Path '{path_val}' does not exist")

        if "exists" == ensure_path:
            return path_val
        if "dir" == ensure_path:
            if path_val.is_dir():
                return path_val
            raise ArgumentTypeError(f"Path {path_val} is not a directory")
        if "file" == ensure_path:
            if path_val.is_file():
                return path_val
            raise ArgumentTypeError(f"Path {path_val} is not a file")

        raise ArgumentTypeError(f"Unknown {ensure_path=} for Path type")

    resolve_path.__name__ = "Path"
    return resolve_path


_file_path_defaults = dict(init=True, repr=True, hash=True, compare=True)


@overload
def file_path(
    *,
    default: Union[None, _MISSING_TYPE] = MISSING,
    alias: str | list[str] | None = None,
    cmd: bool = True,
    positional: bool = False,
    ensure_path: None = None,
    type: Callable[[str], Path] | None = None,
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
    type: Callable[[str], Path] | None = None,
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
    type: Callable[[str], Path] | None = None,
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
    type: Callable[[str], Path] | None = None,
    **kwargs: Any,
) -> FpT:
    # Defaults that I don't care to add to args
    for key, val in _file_path_defaults.items():
        if key not in kwargs:
            kwargs[key] = val

    if type is None:
        type = ResolvedPath(ensure_path)

    return field(
        default=default,
        alias=alias,
        cmd=cmd,
        positional=positional,
        type=type,
        to_dict=True,
        encoding_fn=lambda pp: str(pp) if pp else None,
        decoding_fn=lambda aa: Path(aa).resolve() if aa else None,
        **kwargs,
    )
