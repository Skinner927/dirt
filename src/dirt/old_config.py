from __future__ import annotations

import dataclasses
from pathlib import Path
from typing import (
    Any,
    Callable,
    ClassVar,
    Dict,
    Generic,
    Mapping,
    Optional,
    Protocol,
    Type,
    TypeVar,
    Union,
)

from dirt import const

T = TypeVar("T")
MISSING = dataclasses.MISSING
_MISSING_TYPE = dataclasses._MISSING_TYPE


class OptionValidator(Protocol[T]):
    def __call__(
        self,
        value: Any,
        section: Section,
        attribute_name: str,
        field: dataclasses.Field,
    ) -> T:
        ...


@dataclasses.dataclass()
class Section:
    section_: ClassVar[str] = "<REPLACE>"

    def __init_subclass__(cls, section: str, **kwargs) -> None:
        cls.section_ = section
        super().__init_subclass__(**kwargs)


@dataclasses.dataclass()
class _OptionMeta(Generic[T]):
    key_: ClassVar[str] = "__OptionMeta"
    cmd: Union[None, bool]
    env: Union[None, bool]
    file: Union[None, bool]
    help: Optional[str]
    validator: Optional[OptionValidator[T]]


class _OptionDescriptor(dataclasses.Field):
    def __set__(self, obj, value):
        self.validate(obj, value)
        setattr(obj, self.name, value)

    def validate(self, obj, value) -> None:
        if isinstance(obj, Section) and self.metadata is not None:
            if opt_meta := self.metadata.get(_OptionMeta.key_):
                if isinstance(opt_meta.validator, Callable):
                    opt_meta.validator(value, obj, self.name, self)


def option(
    *,
    default: Union[T, _MISSING_TYPE] = MISSING,
    default_factory: Union[Callable[[], T], Type[T], _MISSING_TYPE] = MISSING,
    init: bool = True,
    repr: bool = True,
    hash: Optional[bool] = None,
    compare: bool = True,
    metadata: Optional[Mapping[Any, Any]] = None,
    kw_only: Union[bool, _MISSING_TYPE] = MISSING,
    # Begin our _OptionMeta params
    cmd: Union[None, bool] = None,
    env: Union[None, bool] = None,
    file: Union[None, bool] = None,
    help: Optional[str] = None,
    validator: Optional[OptionValidator[T]] = None,
    **field_kwargs: Any,
) -> T:
    if const.PY_GE_310:
        # kw_only added in Python 3.10
        field_kwargs["kw_only"] = kw_only

    # Save our options into metadata so we can retrieve them later
    metadata = dict() if metadata is None else metadata
    if _OptionMeta.key_ in metadata:
        raise KeyError(f"'{_OptionMeta.key_}' already exists in metadata")
    metadata[_OptionMeta.key_] = _OptionMeta(
        cmd=cmd, env=env, file=file, help=help, validator=validator
    )

    field: T = _OptionDescriptor(  # type: ignore
        default=default,
        default_factory=default_factory,
        init=init,
        repr=repr,
        hash=hash,
        compare=compare,
        metadata=metadata,
        **field_kwargs,
    )
    return field


class xOption(dataclasses.Field, Generic[T]):
    def __init__(
        self,
        *,
        default: Union[T, _MISSING_TYPE] = MISSING,
        default_factory: Union[Callable[[], T], Type[T], _MISSING_TYPE] = MISSING,
        init: bool = True,
        repr: bool = True,
        hash: Optional[bool] = None,
        compare: bool = True,
        metadata: Optional[Mapping[Any, Any]] = None,
        kw_only: Union[bool, _MISSING_TYPE] = MISSING,
        **kwargs: Any,
    ) -> None:
        if const.PY_GE_310:
            # kw_only added in Python 3.10
            kwargs["kw_only"] = kw_only

        super().__init__(
            default=default,
            default_factory=default_factory,  # type: ignore
            init=init,
            repr=repr,
            hash=hash,
            compare=compare,
            metadata=dict() if metadata is None else metadata,
            **kwargs,
        )

    def __set_name__(self, _owner, name):
        self.name = "_" + name

    def __get__(self, obj, _type):
        if obj is None:
            return self.default

        return getattr(obj, self.name, self.default)

    def __set__(self, obj, value):
        setattr(obj, self.name, value)


@dataclasses.dataclass
class DirtSection(Section, section="dirt"):
    tasks_project: Optional[Path] = None
    bacon: str = option(default="potato")
    cheese: Dict[str, str] = option(default_factory=dict)


def main():
    ds = DirtSection()
    print(f"{ds.tasks_project=}")
    print(f"{ds.bacon=}")

    print("-----")
    ds = DirtSection(bacon="ham")
    print(f"{ds.tasks_project=}")
    print(f"{ds.bacon=}")


if __name__ == "__main__":
    main()
