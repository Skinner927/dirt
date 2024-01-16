import dataclasses

import pytest

from dirt import config


def test_smoke() -> None:
    @dataclasses.dataclass(frozen=True)
    class AppConf(config.Section):
        source: str = config.option(default="nowhere")
