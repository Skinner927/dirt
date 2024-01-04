from __future__ import annotations

import dataclasses
from pathlib import Path
from typing import ClassVar, Optional

import simple_parsing.utils

from dirt.settings import fields


class DirtOptionBase(simple_parsing.Serializable, simple_parsing.utils.Dataclass):
    pass


@dataclasses.dataclass()
class CoreOptions(DirtOptionBase):
    key_: ClassVar[str] = "core"

    help: bool = fields.field(
        default=False,
        nargs=None,
        action="store_true",
        alias=["-h"],
        help="print this help message and exit",
    )
    # Specify specific dirt.ini file to use.
    # config: Optional[str] = fields.field(
    #     default=None,
    #     action="store",
    #     nargs=1,
    #     # metavar="ini_file",
    #     required=False,
    #     help="specify specific .ini file to use",
    # )

    config: Optional[Path] = fields.file_path(
        default=None,
        help="specify specific dirt.ini file to use",
        ensure_path="file",
    )
