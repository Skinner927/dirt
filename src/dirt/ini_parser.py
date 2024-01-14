from __future__ import annotations

import configparser
import enum
from os import PathLike
from pathlib import Path
from typing import Any, ClassVar, Literal, Optional, Type, TypeVar, Union, overload

from dirt import const
from dirt.utils import fix

T = TypeVar("T")

# TODO: Implement fever dream? config.py :D
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
_NO_PATH = Path()
# rng
_NO_STRING = "D;qn:QyC$M_7Db_LSagu3nXyQ9d!V#N$1+HEfxwk6z%**C*bzEa#TFr*$}TK"


class Sections(str, enum.Enum):
    DIRT = "dirt"


class Options(enum.Enum):
    TASKS_PROJECT = (Sections.DIRT, "tasks_project")
    """tasks_project is a relative path to a python project to install."""
    TASKS_MAIN = (Sections.DIRT, "tasks_main")

    def __init__(self, section: str, option: str) -> None:
        self.section = section
        self.option = option


class IniParser(configparser.ConfigParser):
    """Wraps ConfigParser to more easily deal with reading .ini files."""

    Sections: ClassVar[Type[Sections]] = Sections
    Options: ClassVar[Type[Options]] = Options

    def __init__(
        self,
        filename: PathLike[str] | str,
        origin: PathLike[str] | str | None = None,
    ) -> None:
        """Create an IniParser with strict defaults."""
        super().__init__(
            default_section="",
            allow_no_value=True,
            interpolation=configparser.ExtendedInterpolation(),
        )
        self.filename = Path(filename).resolve()
        if origin is None:
            origin = Path.cwd()
        self.origin = Path(origin).resolve()
        self.read(self.filename, encoding="utf-8")

        # Create dirt_dir
        _ = self.dirt_dir

    @fix.cached_property
    def dirt_dir(self) -> Path:
        """Directory where all dirt state is stored.

        .dirt directory is a sibling of the dirt.ini.
        """
        # Make .dirt/ relative to dirt.ini
        dirt_dir = self.filename.parent / const.DOT_DIRT_NAME
        if not dirt_dir.is_dir():
            dirt_dir.mkdir(parents=True, exist_ok=False)
            # TODO: Only git for now; change later depending on resolved vcs?
            git_ignore = dirt_dir / ".gitignore"
            if not git_ignore.exists():
                git_ignore.write_text("*\n")
        return dirt_dir

    @fix.cached_property
    def venv_dir(self) -> Path:
        """Where all our virtual envs will be stored."""
        # Make .dirt/venv
        venv_dir = self.dirt_dir / const.VENV_DIR_NAME
        if not venv_dir.is_dir():
            venv_dir.mkdir(parents=True, exist_ok=False)
        return venv_dir

    @overload
    def dirt_tasks_project(
        self,
        *,
        fallback_path: Union[None, PathLike[str], str] = const.DEFAULT_TASKS_PROJECT,
        fallback: Union[PathLike[str], str] = _NO_PATH,
    ) -> Path:
        ...

    @overload
    def dirt_tasks_project(
        self,
        *,
        fallback_path: Union[None, PathLike[str], str] = const.DEFAULT_TASKS_PROJECT,
        fallback: None,
    ) -> None:
        ...

    def dirt_tasks_project(
        self,
        *,
        fallback_path: Union[None, PathLike[str], str] = const.DEFAULT_TASKS_PROJECT,
        fallback: Union[None, PathLike[str], str] = _NO_PATH,
    ) -> Optional[Path]:
        """tasks_project as a resolved absolute Path.

        :param fallback_path: Validated fallback path to use.
        :param fallback: Will be returned on all errors if specified.
        :return:
        """
        section, option = self.Options.TASKS_PROJECT.value
        try:
            if isinstance(fallback_path, (PathLike, str)):
                # Pathlike and NoVal raise exceptions if not found
                return self.get_path(section, option, fallback=fallback_path)

            # fallback_path is None or something unexpected so user is probably using
            # as a sentinel.
            return self.get_path(section, option)
        except Exception as e:
            if fallback is None:
                return None
            if fallback is not _NO_PATH:
                if isinstance(fallback, Path):
                    return fallback
                return Path(fallback)

            if isinstance(e, OSError):
                raise FileNotFoundError(
                    f"File does not exist/invalid access for '[{section}]' '{option}' in '{self.filename}'"
                ) from e
            # Basically wrap all exexceptions with some context
            raise FileNotFoundError(
                f"Failed to find '[{section}]' '{option}' in '{self.filename}'"
            ) from e

    @overload
    def dirt_tasks_main(self, default: str = const.DEFAULT_TASKS_MAIN) -> str:
        ...

    @overload
    def dirt_tasks_main(self, default: None) -> None:
        ...

    def dirt_tasks_main(
        self, default: Union[None, str] = const.DEFAULT_TASKS_MAIN
    ) -> Union[None, str]:
        """From `[dirt]` section, get `tasks_main` value."""
        section, option = self.Options.TASKS_MAIN.value
        try:
            return self.get(section, option)
        except Exception as e:
            if not isinstance(default, NoVal):
                return default
            raise FileNotFoundError(
                f"Failed to find '[{section}]' '{option}' in '{self.filename}'"
            ) from e

    @overload
    def get_path(
        self,
        section: str,
        option: str,
        *,
        raise_if_invalid: Literal[False],
        fallback: Union[NoVal, T] = _NO_VAL,
        **kw: Any,
    ) -> Union[Path, T, None]:
        ...

    @overload
    def get_path(
        self,
        section: str,
        option: str,
        *,
        raise_if_invalid: Literal[True] = True,
        fallback: Union[NoVal, str, PathLike[str]] = _NO_VAL,
        **kw: Any,
    ) -> Path:
        ...

    def get_path(
        self,
        section: str,
        option: str,
        *,
        raise_if_invalid: bool = True,
        fallback: Union[NoVal, T] = _NO_VAL,
        **kw: Any,
    ) -> Union[Path, T, None]:
        """Resolve Path from ini file.

        If path from ini file is relative, it will be converted to absolute
        relative to the ini file's directory.

        :param section: Section name.
        :param option: Option name.
        :param raise_if_invalid: If `False`: `None` will be returned when an
            exception would have been raised for an invalid `Path`.
        :param fallback: Optional fallback to use if option does not exist.
          `fallback` is only used if a value cannot be retrieved from the
          ini file. If `fallback` is a `str` or `PathLike`, it is validated
          as if it came from the ini file. Any other value is simply returned.
        :param kw: Extra keyword arguments to pass to `ConfigParser.get()`.
        :return: Absolute `Path` that exists.
        """
        try:
            try:
                val: Union[str, PathLike[str], NoVal] = self.get(
                    section, option, fallback=_NO_VAL, **kw
                )
                if isinstance(val, NoVal):
                    # No value in ini
                    raise configparser.NoOptionError(option, section)
                if not val:
                    # Value from ini is empty string
                    raise ValueError(f"Option {option} in section {section} is empty")
            except Exception:
                # Attempt to use fallback
                if isinstance(fallback, NoVal):
                    raise
                if isinstance(fallback, (str, PathLike)):
                    # Validate fallback value and return as Path
                    val = fallback
                else:
                    # Fallback isn't a str or Path
                    return fallback

            # Convert to path
            if isinstance(val, (str, PathLike)):
                path = Path(val).expanduser()
            elif isinstance(val, Path):
                path = val
            else:
                raise TypeError(f"Expected str, PathLike, or Path; got: {type(val)}")

            if not path.is_absolute():
                # If path is relative, make it absolute relative to the dirt.ini
                path = self.filename.parent / path
            return path.resolve(strict=True)
        except Exception:
            if raise_if_invalid:
                raise
            return None
