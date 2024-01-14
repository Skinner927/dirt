from __future__ import annotations

from typing import Callable, Generic, Optional, Type, TypeVar, Union, cast, overload

from typing_extensions import Self

T = TypeVar("T")
R = TypeVar("R")
_NOT_FOUND = object()


class cached_property(Generic[T, R]):
    """`functools.cached_property` without locks.

    Simple "backport" of perf improved cached_property in 3.12.

    Changed in version
    3.12: Prior to Python 3.12, cached_property included an undocumented lock to ensure
    that in multi-threaded usage the getter function was guaranteed to run only once per
    instance. However, the lock was per-property, not per-instance, which could result
    in unacceptably high lock contention. In Python 3.12+ this locking is removed.

    :param func:
    :return:
    """

    def __init__(self, func: Callable[[T], R]) -> None:
        self.func = func
        self.attrname: Optional[str] = None
        self.__doc__ = func.__doc__

    def __set_name__(self, owner: Type[T], name: str) -> None:
        if self.attrname is None:
            self.attrname = name
        elif name != self.attrname:
            raise TypeError(
                "Cannot assign the same cached_property to two different names "
                f"({self.attrname!r} and {name!r})."
            )

    @overload
    def __get__(self, instance: T, owner: None = None) -> Self:
        ...

    @overload
    def __get__(self, instance: T, owner: Type[T]) -> R:
        ...

    def __get__(self, instance: T, owner: Optional[Type[T]] = None) -> Union[Self, R]:
        if instance is None:
            return self
        if self.attrname is None:
            raise TypeError(
                "Cannot use cached_property instance without calling __set_name__ on it."
            )
        try:
            cache = instance.__dict__
        except (
            AttributeError
        ):  # not all objects have __dict__ (e.g. class defines slots)
            msg = (
                f"No '__dict__' attribute on {type(instance).__name__!r} "
                f"instance to cache {self.attrname!r} property."
            )
            raise TypeError(msg) from None
        val = cache.get(self.attrname, _NOT_FOUND)
        if val is _NOT_FOUND:
            val = self.func(instance)
            try:
                cache[self.attrname] = val
            except TypeError:
                msg = (
                    f"The '__dict__' attribute on {type(instance).__name__!r} instance "
                    f"does not support item assignment for caching {self.attrname!r} property."
                )
                raise TypeError(msg) from None
        return cast(R, val)