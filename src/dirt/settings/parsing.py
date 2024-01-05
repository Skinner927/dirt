from __future__ import annotations

import argparse
from argparse import HelpFormatter
from pathlib import Path
from typing import Optional, Sequence

from simple_parsing import (
    ArgumentGenerationMode,
    ArgumentParser,
    ConflictResolution,
    DashVariant,
    NestedMode,
    SimpleHelpFormatter,
    help_formatter,
)


class TailoredHelpFormatter(SimpleHelpFormatter):
    def _get_help_string(self, action: argparse.Action) -> Optional[str]:
        # Don't include (default: %(default)s) for boolean flags
        if 0 == action.nargs:
            msg = action.help
        else:
            msg = super()._get_help_string(action=action)
        if msg is not None:
            msg = msg.replace(help_formatter.TEMPORARY_TOKEN, "")
        return msg


class DirtArgParser(ArgumentParser):
    def __init__(
        self,
        *args,
        parents: Sequence[ArgumentParser] = (),
        add_help: bool = False,  # default: True
        conflict_resolution: ConflictResolution = ConflictResolution.AUTO,
        # Was DashVariant.AUTO
        add_option_string_dash_variants: DashVariant = DashVariant.DASH,
        argument_generation_mode=ArgumentGenerationMode.FLAT,
        nested_mode: NestedMode = NestedMode.DEFAULT,
        # Was simple_parsing.SimpleHelpFormatter
        formatter_class: type[HelpFormatter] = TailoredHelpFormatter,
        add_config_path_arg: bool | None = None,
        config_path: Path | str | Sequence[Path | str] | None = None,
        add_dest_to_option_strings: bool | None = None,
        fromfile_prefix_chars: Optional[str] = "@",  # override
        allow_abbrev: bool = False,  # override
        **kwargs,
    ) -> None:
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
            fromfile_prefix_chars=fromfile_prefix_chars,
            allow_abbrev=allow_abbrev,
            **kwargs,
        )
