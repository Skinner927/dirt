from __future__ import annotations

import configparser
from os import PathLike
from typing import ClassVar, TypeVar, Union

T = TypeVar("T")

# TODO: Implement fever dream?
_fever_dream = """
class IniParser(TypedIniParser)

    @dataclass
    class dirt(TypedIniSection)
        tasks_project: str = ""
        tasks_main: str = ""
        
"""


class IniParser(configparser.ConfigParser):
    """Wraps ConfigParser to more easily deal with reading .ini files."""

    DIRT_SECTION: ClassVar[str] = "dirt"
    TASKS_PROJECT: ClassVar[str] = "tasks_project"
    TASKS_MAIN: ClassVar[str] = "tasks_main"

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

    def dirt_tasks_project(
        self, fallback: Union[T, None, str] = None
    ) -> Union[T, None, str]:
        """From `[dirt]` section, get `tasks_project` value."""
        return self.get(self.DIRT_SECTION, self.TASKS_PROJECT, fallback=fallback)

    def dirt_tasks_main(
        self, fallback: Union[T, None, str] = None
    ) -> Union[T, None, str]:
        """From `[dirt]` section, get `tasks_main` value."""
        return self.get(self.DIRT_SECTION, self.TASKS_MAIN, fallback=fallback)
