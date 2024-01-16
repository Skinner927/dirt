from __future__ import annotations

import collections
import dataclasses
import enum
import sys
from typing import (
    Any,
    Callable,
    ChainMap,
    ClassVar,
    Collection,
    Dict,
    Final,
    Generic,
    List,
    Literal,
    Mapping,
    Optional,
    Protocol,
    Sequence,
    Tuple,
    Type,
    TypedDict,
    TypeVar,
    Union,
    cast,
    overload,
)

_F = TypeVar("_F")
_T = TypeVar("_T")
_T_co = TypeVar("_T_co", covariant=True)

ParserType = Type["Parser"]
ParserGroup = str
OptionName = str
ParserOverrideKey = Union[ParserType, ParserGroup, Tuple[ParserGroup, ParserType]]
ParserSpecificOptions = Any
ParserOverride = Union[bool, Sequence[OptionName], None, ParserSpecificOptions]
ParserOverrideMap = Mapping[ParserOverrideKey, ParserOverride]


# https://github.com/python/typeshed/blob/26e77cbf67ee0e224808a85b18c08c1dda63aaec/stdlib/dataclasses.pyi
class _DefaultFactory(Protocol[_T_co]):
    def __call__(self) -> _T_co:
        ...


class _TypeFormatter(Protocol[_T_co]):
    nargs: int

    @property
    def choices(self) -> Optional[Sequence[_T_co]]:
        return None

    def __call__(
        self, value: str, name: str, instance: object, meta: _OptionMeta
    ) -> _T_co:
        ...


class _MissingType(enum.Enum):
    missing = enum.auto()


# non-private if external needs to use
MISSING = _MissingType.missing
MISSING_T = Literal[_MissingType.missing]


class Parser:
    """Parses from cli/env/file/whatever and returns a dict (or namespace?)."""

    pass


@dataclasses.dataclass(frozen=True)
class Section:
    options_prefix_: ClassVar[Union[str, Sequence[str]]] = ""
    store_at_: ClassVar[str] = ""
    override_: ClassVar[Optional[ParserOverrideMap]] = None

    def __init_subclass__(
        cls, prefix: Union[str, Sequence[str]] = "", store: str = "", **kwargs
    ) -> None:
        if prefix:
            cls.options_prefix_ = prefix
        if store:
            cls.store_at_ = store
        super().__init_subclass__(**kwargs)


class _OptionMeta(TypedDict, Generic[_T]):
    formatter: Optional[_TypeFormatter[_T]]
    override_name: Sequence[OptionName]
    """May be empty."""
    help: str | None
    parsers_override: ParserOverrideMap


class Option(dataclasses.Field[_T]):
    pass


# default: _T | MISSING_T = MISSING,
# default_factory: _DefaultFactory[_T] | MISSING_T = MISSING,
# if sys.version_info > 3,12 expose **field_kwargs


@overload
def option(
    *override_name: OptionName,
    default: _T,
    metadata: Optional[Mapping[Any, Any]] = None,
    formatter: Optional[_TypeFormatter[_F]] = None,
    help: str | None = None,
    cli: ParserOverride = None,
    file: ParserOverride = None,
    env: ParserOverride = None,
    parsers_override: ParserOverrideMap | None = None,
    **field_kwargs: Any,
) -> Union[_T, _F]:
    ...


@overload
def option(
    *override_name: OptionName,
    default_factory: Callable[[], _T],
    metadata: Optional[Mapping[Any, Any]] = None,
    formatter: Optional[_TypeFormatter[_F]] = None,
    help: str | None = None,
    cli: ParserOverride = None,
    file: ParserOverride = None,
    env: ParserOverride = None,
    parsers_override: ParserOverrideMap | None = None,
    **field_kwargs: Any,
) -> Union[_T, _F]:
    ...


# Type is based on TypeFormatter. Maybe drop this?
@overload
def option(
    *override_name: OptionName,
    metadata: Optional[Mapping[Any, Any]] = None,
    formatter: _TypeFormatter[_F],
    help: str | None = None,
    cli: ParserOverride = None,
    file: ParserOverride = None,
    env: ParserOverride = None,
    parsers_override: ParserOverrideMap | None = None,
    **field_kwargs: Any,
) -> _F:
    ...


@overload
def option(
    *override_name: OptionName,
    metadata: Optional[Mapping[Any, Any]] = None,
    formatter: Optional[_TypeFormatter[_T]] = None,
    help: str | None = None,
    cli: ParserOverride = None,
    file: ParserOverride = None,
    env: ParserOverride = None,
    parsers_override: ParserOverrideMap | None = None,
    **field_kwargs: Any,
) -> Optional[Any]:
    ...


# default and default_factory passed through field_kwargs
def option(
    *override_name: OptionName,
    metadata: Optional[Mapping[Any, Any]] = None,
    formatter: Optional[_TypeFormatter[_F]] = None,
    help: str | None = None,
    cli: ParserOverride = None,
    file: ParserOverride = None,
    env: ParserOverride = None,
    parsers_override: ParserOverrideMap | None = None,
    **field_kwargs: Any,
) -> Union[_T, _F]:
    # Copy metadata so we can add our OptionMeta to it
    mutable_metadata = dict() if metadata is None else dict(metadata)

    # Shorthand for the standard parser groups into parsers_override
    mutable_override = dict() if parsers_override is None else dict(parsers_override)
    for key, val in (("cli", cli), ("file", file), ("env", env)):
        if val is not None:
            if mutable_override.get(key, None) is not None:
                raise KeyError(f"duplicate key '{key}' in parsers_override")
            mutable_override[key] = val

    # Slap our _OptionMeta on the metadata mapping
    mutable_metadata[_OptionMeta.__name__] = _OptionMeta(
        formatter=formatter,
        override_name=override_name,
        help=help,
        parsers_override=mutable_override,
    )

    # Create a field and replace its class to make it an Option.
    field = dataclasses.field(metadata=mutable_metadata, **field_kwargs)
    field.__class__ = Option
    return field


class ConfigParserFormatter(Protocol):
    ...


class HelpConfigParserFormatter:
    pass


class ConfigParser:
    def __init__(
        self,
        prog: None | str = None,
        usage: None | str = None,
        description: None | str = None,
        formatter: Union[
            Type[ConfigParserFormatter], ConfigParserFormatter
        ] = HelpConfigParserFormatter,
        parsers: Sequence[Parser] = (),
    ):
        self.prog = prog
        self.usage = usage
        self.description = description
        self.formatter = formatter() if isinstance(formatter, type) else formatter
        self.parsers = parsers
