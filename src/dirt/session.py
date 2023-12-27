from __future__ import annotations

from pathlib import Path
from typing import Optional


class Session:
    def __init__(self, name: str, dirt_ini_file_path: Path) -> None:
        self.name = name
        self.dirt_init_file_path = dirt_ini_file_path
