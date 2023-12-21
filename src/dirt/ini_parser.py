from __future__ import annotations

import configparser
from os import PathLike
from typing import Optional, Iterable, Union, ClassVar

_DEFAULT_INTERP = configparser.ExtendedInterpolation()


class IniParser(configparser.ConfigParser):
    """Wraps ConfigParser to more easily deal with reading .ini files."""

    DIRT_SECTION: ClassVar[str] = "dirt"

    def __init__(
        self,
        filenames: Union[
            str,
            bytes,
            PathLike[str],
            PathLike[bytes],
            Iterable[Union[str, bytes, PathLike[bytes]]],
        ],
        encoding: Optional[str] = "utf-8",
        *,
        default_section: str = "]",
        interpolation: Optional[configparser.Interpolation] = _DEFAULT_INTERP,
        **kwargs,
    ) -> None:
        """Create an IniParser.

        :param file:
        :param default_section: No default section by default.
        :param interpolation: Use ExtendedInterpolation by default.
        :param kwargs:
        """
        if interpolation is _DEFAULT_INTERP:
            # Is new instance required/preferred?
            interpolation = configparser.ExtendedInterpolation()
        super().__init__(
            default_section=default_section, interpolation=interpolation, **kwargs
        )
        self.filenames = filenames
        self.read(self.filenames, encoding)

    def dirt_task_module(self, fallback: Optional[str] = None) -> Optional[str]:
        """Get [dirt] task_module's value."""
        return self.get(self.DIRT_SECTION, "task_module", fallback=fallback)
