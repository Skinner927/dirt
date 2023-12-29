from __future__ import annotations

from argparse import HelpFormatter
from pathlib import Path
from typing import Sequence

from simple_parsing import (
    ArgumentGenerationMode,
    ArgumentParser,
    ConflictResolution,
    DashVariant,
    NestedMode,
    SimpleHelpFormatter,
    field,
)

__all__ = ["field", "AuditArgumentParser"]


class AuditArgumentParser(ArgumentParser):
    def __init__(
        self,
        *args,
        parents: Sequence[ArgumentParser] = (),
        add_help: bool = True,
        conflict_resolution: ConflictResolution = ConflictResolution.AUTO,
        add_option_string_dash_variants: DashVariant = DashVariant.AUTO,
        argument_generation_mode=ArgumentGenerationMode.BOTH,
        nested_mode: NestedMode = NestedMode.DEFAULT,
        formatter_class: type[HelpFormatter] = SimpleHelpFormatter,
        add_config_path_arg: bool | None = None,
        config_path: Path | str | Sequence[Path | str] | None = None,
        add_dest_to_option_strings: bool | None = None,
        **kwargs,
    ) -> None:
        # Changed argument_generation_mode from FLAT to BOTH
        # Defaults
        if "fromfile_prefix_chars" not in kwargs:
            kwargs["fromfile_prefix_chars"] = "@"
        if "allow_abbrev" not in kwargs:
            kwargs["allow_abbrev"] = False

        super().__init__(
            *args,
            parents=parents,
            add_help=add_help,
            conflict_resolution=conflict_resolution,
            add_option_string_dash_variants=add_option_string_dash_variants,
            argument_generation_mode=argument_generation_mode,
            nested_mode=nested_mode,
            formatter_class=formatter_class,
            add_config_path_arg=add_config_path_arg,
            config_path=config_path,
            add_dest_to_option_strings=add_dest_to_option_strings,
            **kwargs,
        )
