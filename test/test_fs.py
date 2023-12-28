from __future__ import annotations

from pathlib import Path
from typing import Iterable, Set

from dirt.utils import fs


def _assert_no_dupes(paths: Iterable[Path], base: Path | None = None) -> Set[Path]:
    if base:
        as_list = [p for p in paths if base in p.parents]
    else:
        as_list = list(paths)

    as_set = set(as_list)
    if len(as_list) != len(as_set):
        dedupe_list = [p for i, p in enumerate(as_list) if i == as_list.index(p)]
        # This should show the diff
        assert dedupe_list == as_list
    return as_set


def test_fs_find_up(tmp_path: Path) -> None:
    tmp_path.mkdir(parents=True, exist_ok=True)
    tmp_path = tmp_path.resolve()
    # Dirs
    d1 = tmp_path / "one"
    d2 = d1 / "two"
    d3 = d2 / "three"
    d3.mkdir(parents=True, exist_ok=False)
    # Files
    f1 = d1 / "f1.txt"
    f1.write_text("file 1")
    f2 = d2 / "f2.log"
    f2.write_text("file 2")
    f3 = d3 / "f3.ini"
    f3.write_text("file 3")
    # Hidden files
    h1 = d1 / ".hidden1"
    h1.write_text("hidden h1")
    h2 = d2 / ".hidden2"
    h2.write_text("hidden h2")

    hd2 = d2 / ".hidden_dir"
    hd2.mkdir(parents=True, exist_ok=False)
    hd2h1 = hd2 / ".another_hidden"
    hd2h1.write_text("another hidden hd2h1")
    hd2f1 = hd2 / "legal.ini"
    hd2f1.write_text("legal hd2f1")

    up1 = _assert_no_dupes(fs.find(d2, down=False), tmp_path)

    assert d1 in up1
    assert f1 in up1
    assert d2 in up1
    assert f2 in up1
    assert d3 in up1

    assert f3 not in up1
    assert h1 not in up1
    assert h2 not in up1
    assert hd2 not in up1
    assert hd2h1 not in up1
    assert hd2f1 not in up1

    # Includes hidden
    up2 = _assert_no_dupes(
        fs.find(d2, down=False, skip_hidden_dir=False, skip_hidden_file=False), tmp_path
    )
    assert d1 in up2
    assert f1 in up2
    assert d2 in up2
    assert f2 in up2
    assert d3 in up2
    assert f3 not in up2
    assert h1 in up2
    assert h2 in up2
    assert hd2 in up2
    assert hd2h1 not in up2
    assert hd2f1 not in up2

    # Only hidden files
    up3 = _assert_no_dupes(
        fs.find(
            d2,
            ".*",
            down=False,
            skip_hidden_dir=False,
            skip_hidden_file=False,
            kind={"file"},
        ),
        tmp_path,
    )
    assert d1 not in up3
    assert f1 not in up3
    assert d2 not in up3
    assert f2 not in up3
    assert d3 not in up3
    assert f3 not in up3
    assert h1 in up3
    assert h2 in up3
    assert hd2 not in up3
    assert hd2h1 not in up3
    assert hd2f1 not in up3


def test_fs_find_down(tmp_path: Path) -> None:
    tmp_path.mkdir(parents=True, exist_ok=True)
    tmp_path = tmp_path.resolve()
    # Dirs
    d1 = tmp_path / "one"
    d2 = d1 / "two"
    d3 = d2 / "three"
    d3.mkdir(parents=True, exist_ok=False)
    # Files
    f1 = d1 / "f1.txt"
    f1.write_text("file 1")
    f2 = d2 / "f2.log"
    f2.write_text("file 2")
    f3 = d3 / "f3.ini"
    f3.write_text("file 3")
    # Hidden files
    h1 = d1 / ".hidden1"
    h1.write_text("hidden h1")
    h2 = d2 / ".hidden2"
    h2.write_text("hidden h2")

    hd2 = d2 / ".hidden_dir"
    hd2.mkdir(parents=True, exist_ok=False)
    hd2h1 = hd2 / ".another_hidden"
    hd2h1.write_text("another hidden hd2h1")
    hd2f1 = hd2 / "legal.ini"
    hd2f1.write_text("legal hd2f1")

    down1 = _assert_no_dupes(fs.find(d2, down=True), tmp_path)
    assert d1 not in down1
    assert f1 not in down1
    assert d2 in down1
    assert f2 in down1
    assert d3 in down1
    assert f3 in down1
    assert h1 not in down1
    assert h2 not in down1
    assert hd2 not in down1
    assert hd2h1 not in down1
    assert hd2f1 not in down1

    # Only hidden
    down2 = _assert_no_dupes(
        fs.find(d2, ".*", down=True, skip_hidden_dir=False, skip_hidden_file=False),
        tmp_path,
    )
    assert d1 not in down2
    assert f1 not in down2
    assert d2 not in down2
    assert f2 not in down2
    assert d3 not in down2
    assert f3 not in down2
    assert h1 not in down2
    assert h2 in down2
    assert hd2 in down2
    assert hd2h1 in down2
    assert hd2f1 not in down2

    # Only hidden dirs
    down3 = _assert_no_dupes(
        fs.find(
            d1,
            ".*",
            down=True,
            skip_hidden_dir=False,
            skip_hidden_file=False,
            kind={"dir"},
        ),
        tmp_path,
    )
    assert d1 not in down3
    assert f1 not in down3
    assert d2 not in down3
    assert f2 not in down3
    assert d3 not in down3
    assert f3 not in down3
    assert h1 not in down3
    assert h2 not in down3
    assert hd2 in down3
    assert hd2h1 not in down3
    assert hd2f1 not in down3
