from __future__ import annotations

import os
import sys
from pathlib import Path
from typing import Union, Optional, List


class Bootstrapper:
    def __init__(self, start_dir: Union[None, Path, str] = None) -> None:
        self.start_dir: Path = Path(start_dir or os.getcwd())

    def start(self, argv: Optional[List[str]] = None) -> None:
        if argv is None:
            argv = sys.argv

        dot_dirt: Optional[Path] = self.find_dot_dirt(self.start_dir)
        if dot_dirt is None:
            raise RuntimeError(f"Could not find .dirt directory from {self.start_dir}")

        # TODO: track env hashes and purge old envs

    @staticmethod
    def find_dot_dirt(start: Path) -> Optional[Path]:
        """Walk up the tree looking for the first .dirt directory with a dart.ini init"""
        seen = set()
        current = start
        while current:
            # Check for loops
            if current in seen:
                raise RecursionError(f"Circular pathing for {current}")
            seen.add(current)

            # Check for .dirt dir with dirt.ini inside
            dot_dirt = current / ".dirt"
            if dot_dirt.is_dir() and (dot_dirt / "dirt.ini").is_file():
                return dot_dirt
            # Next
            current = current.parent
        return None
