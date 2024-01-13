from __future__ import annotations

import os
import shutil
from typing import Mapping, Optional, Sequence, Union

# Problematic environment variables that are stripped from all commands inside
# of a virtualenv. See https://github.com/theacodes/nox/issues/44
# https://github.com/wntrblm/nox/blob/5c82dc553bd04ee017784fc16193da0b35a44ab6/nox/virtualenv.py
BLACKLISTED_ENV_VARS = frozenset(
    ["PIP_RESPECT_VIRTUALENV", "PIP_REQUIRE_VIRTUALENV", "__PYVENV_LAUNCHER__"]
)


class CmdError(RuntimeError):
    pass


class CommandNotFound(CmdError):
    def __init__(self, *args, command: str) -> None:
        super().__init__(*args)
        self.command = command


def which(cmd: str | os.PathLike[str], paths: Optional[Sequence[str]] = None) -> str:
    """Resolve path to cmd or raise.

    :param cmd: Executable command/binary to find.
    :param paths: Optionally specify paths to search first before checking `env['PATH']`
    :return:
    """
    # DO NOT RESOLVE PATHS. Preserving symlinks is potentially important.
    try:
        if not cmd:
            raise ValueError("Command is empty")
        cmd = str(cmd)
        if paths:
            if full := shutil.which(cmd, path=os.pathsep.join(paths)):
                return os.fspath(full)
        if full := shutil.which(cmd):
            return os.fspath(full)
    except Exception as e:
        raise CommandNotFound(f"Failed to find command {cmd}", command=str(cmd)) from e
    raise CommandNotFound(f"Failed to find command {cmd}", command=cmd)


def new_env(
    env: Mapping[str, str] | None = None,
    path: str | Sequence[str] | None = None,
    path_prefix: str | Sequence[str] | None = None,
) -> Mapping[str, str]:
    base = os.environ.copy()

    # Remove potentially "bad" entries
    for key in BLACKLISTED_ENV_VARS:
        _ = base.pop(key, None)
    _ = base.pop("VIRTUAL_ENV", None)

    if env is not None:
        base.update(env)

    if isinstance(path, str):
        base["PATH"] = path
    elif path is not None:
        base["PATH"] = os.path.pathsep.join(path)

    if isinstance(path_prefix, str):
        base["PATH"] = os.path.pathsep.join([path_prefix, base["PATH"]])
    elif path_prefix is not None:
        base["PATH"] = os.path.pathsep.join(list(path_prefix) + [base["PATH"]])

    return base
