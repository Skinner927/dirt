from __future__ import annotations

import configparser
import enum
from os import PathLike
from pathlib import Path
from typing import ClassVar, TypeVar, Union, overload

T = TypeVar("T")

# TODO: Implement fever dream?
_fever_dream = """
class IniParser(TypedIniParser)

    @dataclass
    class dirt(TypedIniSection)
        tasks_project: str = ""
        tasks_main: str = ""
        
"""


class NoVal:
    pass


_NO_VAL = NoVal()


class Section(str, enum.Enum):
    DIRT = "dirt"


class Option(enum.Enum):
    TASKS_PROJECT = (Section.SECTION_DIRT, "tasks_project")

    def __init__(self, section: str, option: str) -> None:
        self.section = section
        self.option = option


class IniParser(configparser.ConfigParser):
    """Wraps ConfigParser to more easily deal with reading .ini files."""

    Sections = Section
    Option = Option

    DIRT_SECTION: ClassVar[str] = "dirt"
    TASKS_PROJECT: ClassVar[str] = "tasks_project"
    """tasks_project is a relative path to a python project to install."""
    TASKS_MAIN: ClassVar[str] = "tasks_main"

    def __init__(
        self,
        filename: PathLike[str] | str,
    ) -> None:
        """Create an IniParser with strict defaults."""
        super().__init__(
            default_section="",
            allow_no_value=True,
            interpolation=configparser.ExtendedInterpolation(),
        )
        self.filename = Path(filename).resolve()
        self.read(self.filename, encoding="utf-8")

    @overload
    def dirt_tasks_project(self, fallback: NoVal = _NO_VAL) -> Path:
        ...

    @overload
    def dirt_tasks_project(self, fallback: T) -> Union[Path, T]:
        ...

    def dirt_tasks_project(self, fallback: Union[T, NoVal] = _NO_VAL) -> Union[Path, T]:
        """From `[dirt]` section, get `tasks_project` value."""
        try:
            return self.get_path(self.DIRT_SECTION, self.TASKS_PROJECT)
        except Exception:
            if not isinstance(fallback, NoVal):
                return fallback
            raise

    def dirt_tasks_main(self, fallback: Union[T, NoVal] = _NO_VAL) -> Union[T, str]:
        """From `[dirt]` section, get `tasks_main` value."""
        try:
            return self.get(self.DIRT_SECTION, self.TASKS_MAIN)
        except Exception:
            if not isinstance(fallback, NoVal):
                return fallback
            raise

    @overload
    def get_path(
        self,
        section: str,
        option: str,
        *,
        strict: bool = True,
        relative_to_ini: bool = True,
        fallback: NoVal = _NO_VAL,
        **kw,
    ) -> Path:
        ...

    @overload
    def get_path(
        self,
        section: str,
        option: str,
        *,
        strict: bool = True,
        relative_to_ini: bool = True,
        fallback: T,
        **kw,
    ) -> Union[Path, T]:
        ...

    def get_path(
        self,
        section: str,
        option: str,
        *,
        strict: bool = True,
        relative_to_ini: bool = True,
        fallback: Union[NoVal, T] = _NO_VAL,
        **kw,
    ) -> Union[Path, T]:
        val = self.get(section, option, fallback=_NO_VAL, **kw)
        try:
            if isinstance(fallback, NoVal):
                # No value in ini
                raise configparser.NoOptionError(option, section)
            if not val:
                # Value from ini is empty string
                raise ValueError(f"Option {option} in section {section} is empty")

            path = Path(val).expanduser()
            if relative_to_ini and not path.is_absolute():
                # If path is relative, make it absolute relative to the dirt.ini
                path = self.filename / path
            return path.resolve(strict=strict)
        except Exception:
            if not isinstance(fallback, NoVal):
                return fallback
            # else
            raise
