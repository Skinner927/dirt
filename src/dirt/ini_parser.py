from __future__ import annotations

import configparser
from os import PathLike
from typing import Optional, ClassVar

_DEFAULT_INTERP = configparser.ExtendedInterpolation()


class IniParser(configparser.ConfigParser):
    """Wraps ConfigParser to more easily deal with reading .ini files."""

    DIRT_SECTION: ClassVar[str] = "dirt"
    TASK_MODULE: ClassVar[str] = "task_module"

    def __init__(
        self,
        filename: PathLike[str] | str,
    ) -> None:
        """Create an IniParser with strict defaults."""
        super().__init__(
            default_section="]", interpolation=configparser.ExtendedInterpolation()
        )
        self.filename = filename
        self.read(self.filename, encoding="utf-8")

    def dirt_task_module(self, fallback: Optional[str] = None) -> Optional[str]:
        """From `[dirt]` section, get `task_module` value."""
        return self.get(self.DIRT_SECTION, self.TASK_MODULE, fallback=fallback)
