from __future__ import annotations

import argparse
import configparser
from pathlib import Path
from typing import Dict, Iterable, List, Optional, Sequence, Tuple, TypedDict, cast

import attrs
import typed_settings as ts

from dirt import const

__all__ = [
    "IniFormat",
    "Core",
    "bootstrap_parse_args",
]


# TODO: Merge this to upstream typed-settings
class IniFormat(ts.loaders.FileFormat):
    """Ini file format for typed_settings.

    Implements typed_settings.loaders.FileFormat.
    """

    def __init__(
        self,
        section: str,
        default_section: str = "",
        interpolation: configparser.Interpolation = configparser.ExtendedInterpolation(),
    ) -> None:
        self.section = section
        self.default_section = default_section or ""
        self.interpolation = interpolation

    def __call__(
        self,
        path: Path,
        settings_cls: ts.types.SettingsClass,
        options: ts.types.OptionList,
    ) -> ts.types.SettingsDict:
        parser = configparser.ConfigParser(
            default_section=self.default_section, interpolation=self.interpolation
        )
        try:
            with path.open("r") as f:
                parser.read_file(f)
        except FileNotFoundError as e:
            raise ts.ConfigFileNotFoundError(str(e)) from e
        except (PermissionError, configparser.Error) as e:
            raise ts.ConfigFileLoadError(str(e)) from e

        try:
            settings = dict(parser[self.section])
        except KeyError:
            settings = dict()

        return cast(ts.types.SettingsDict, settings)


# TODO: Possibly extend upstream ts.find() to accept a list
def _find_multi(filenames: Iterable[str], start: Optional[Path] = None) -> Path:
    """Basically `ts.find()` but accepts multiple filenames."""
    if not isinstance(filenames, (list, tuple)):
        filenames = tuple(filenames)

    if start is None:
        start = Path.cwd()
    start = start.resolve()
    if not start.is_dir():
        # A dir should have been passed
        start = start.parent
    if start.is_dir():
        # Start needs to be a file because we iterate `.parents`
        # (does not need to exist) and a file that we'll search for because it
        # will be returned as default if one was not found.
        start = start / filenames[0]

    for path in start.parents:
        for name in filenames:
            p = path / name
            if p.is_file():
                return p.resolve()
    return start


class _LoadersConverterT(TypedDict):
    loaders: Sequence[ts.loaders.Loader]
    converter: ts.converters.Converter


def _loaders_converter(*, origin: Path) -> _LoadersConverterT:
    """Return our customized default loaders."""
    loaders = [
        ts.loaders.FileLoader(
            files=[_find_multi(const.DIRT_INI_FNAMES, origin), const.USER_DIRT_INI],
            formats={"*.ini": IniFormat(const.DEFAULT_PROG_NAME_SNAKE)},
            env_var=None,
        )
    ]
    return dict(
        loaders=loaders, converter=ts.converters.default_converter(resolve_paths=True)
    )


class WhateverConstAction(argparse.Action):
    """'const' action but allows unneeded args."""

    def __init__(
        self,
        option_strings,
        dest,
        const,
        default=None,
        required=False,
        help=None,
        *__,
        **_,
    ) -> None:
        super().__init__(
            option_strings=option_strings,
            dest=dest,
            nargs=0,
            const=const,
            default=default,
            required=required,
            help=help,
        )

    def __call__(self, parser, namespace, values, option_string=None, *__, **_):
        setattr(namespace, self.dest, self.const)


@attrs.frozen()
class Core:
    help: Optional[bool] = ts.option(
        default=None,  # None so [default: False] is not shown
        argparse={
            "param_decls": ("--help", "-h"),
            "const": True,
            "default": False,
            "action": WhateverConstAction,
            "help": "Show this help message and exit.",
        },
    )
    config: Optional[str] = ts.option(
        default=None,
        help="Specify specific dirt.ini file to use.",
        argparse={"metavar": "INI_FILE"},
    )
    tasks_path: Optional[str] = ts.option(
        default="./.dirt/tasks", argparse={"metavar": "PATH_OR_PKG"}
    )
    tasks_main: Optional[str] = ts.option(
        default="tasks", argparse={"metavar": "MODULE"}
    )


def bootstrap_parse_args(origin: Path) -> Tuple[Core, List[str]]:
    parser, ldr = ts.cli_argparse.make_parser(
        Core,
        **_loaders_converter(origin=origin),
        add_help=False,
        allow_abbrev=False,
    )
    print(f"{ldr=}")
    # Where an option is loaded from: ldr['tasks_main'].loader_meta.name
    known, unknown = parser.parse_known_args()
    merged_settings: Dict[str, ts.types.LoadedValue] = dict()
    resolved = ts.cli_argparse.namespace2settings(
        Core,
        known,
        merged_settings=merged_settings,
    )
    if resolved.help:
        parser.print_help()
    print(f"{ldr=}")
    return resolved, unknown
