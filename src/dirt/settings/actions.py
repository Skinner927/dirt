from __future__ import annotations

import argparse
from pathlib import Path
from typing import Any, Iterable, Literal, Optional, Union


class PathOptionalAction(argparse.Action):
    def __init__(
        self,
        *args,
        ensure_path: Literal["exists", "dir", "file"] | None = None,
        **kwargs,
    ) -> None:
        self.ensure_path = ensure_path
        super().__init__(*args, **kwargs)

    def check_path(self, value: Path, option_string: str) -> Path:
        if not isinstance(value, Path):
            raise ValueError(f"Unsupported value for {option_string}")
        if not self.ensure_path:
            return value.resolve()

        # Ensure resolves to an existing path
        try:
            value = value.resolve(strict=True)
        except FileNotFoundError as e:
            raise ValueError(f"Path {value} for {option_string} does not exist") from e

        if "exists" == self.ensure_path:
            return value
        if "dir" == self.ensure_path:
            if value.is_dir():
                return value
            raise ValueError(f"Path {value} for {option_string} is not a directory")
        if "file" == self.ensure_path:
            if value.is_file():
                return value
            raise ValueError(f"Path {value} for {option_string} is not a file")

        raise ValueError(
            f"Unknown 'ensure_path' for {option_string}: {self.ensure_path!r}"
        )

    def __call__(
        self,
        parser: argparse.ArgumentParser,
        namespace: argparse.Namespace,
        values: Any,
        option_string: Optional[str] = None,
    ) -> None:
        option_string = option_string or "arg"
        # can_be_none = not self.ensure_path
        # strict = bool(self.required and not isinstance(self.default, Path))

        path_val: Union[None, Path, list[Path]]
        if values is None:
            # if not can_be_none:
            #     raise ValueError(f"Missing {self.metavar} for {option_string}")
            path_val = None
        elif isinstance(values, str):
            path_val = self.check_path(Path(values), option_string)
        elif isinstance(values, Path):
            path_val = self.check_path(values, option_string)
        elif isinstance(values, Iterable):
            path_val = [self.check_path(Path(v), option_string) for v in values if v]
        else:
            raise ValueError(f"Unsupported value for {option_string}")

        setattr(namespace, self.dest, path_val)
