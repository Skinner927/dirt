from __future__ import annotations

import logging
import os
import subprocess
import sys
from pathlib import Path
from typing import Final, Tuple

from rich.markup import escape

import dirt.session
import dirt.settings
import dirt.settings.parsing
import dirt.utils
from dirt import const, utils
from dirt.ini_parser import IniParser
from dirt.settings.options import CoreOptions
from dirt.settings.parsing import DirtArgParser

PY_VERSION: Final[str] = ".".join(str(x) for x in sys.version_info[:2])
logger = logging.getLogger(__name__)


class KnownError(RuntimeError):
    def __init__(self, message: str, as_exception: bool = False) -> None:
        super().__init__(message)
        self.message = message
        self.as_exception = as_exception


class IgnoreThisError(Exception):
    pass


def _parse_core_options() -> Tuple[CoreOptions, DirtArgParser]:
    parser = DirtArgParser()
    parser.add_arguments(CoreOptions, dest=CoreOptions.key_)
    known_args, _ = parser.parse_known_args()
    core_settings: CoreOptions = getattr(known_args, CoreOptions.key_)
    return core_settings, parser


def _find_root_dirt_ini(origin: Path, core_options: CoreOptions) -> Path:
    """Return the resolved `dirt.ini` file or raise `FileNotFoundError`."""
    if core_options.config:
        # TODO: No need to do this because our type=arg_path_type does it
        # User passed a config file path, ensure it's legit
        try:
            return Path(core_options.config).resolve(strict=True)
        except FileNotFoundError:
            raise FileNotFoundError(
                f"File path set with --config `{core_options.config!s}` does not exist"
            )
    else:
        # Search for the config
        if found := dirt.utils.fs.walk_up_find(const.DIRT_INI_FNAMES, origin):
            try:
                return found.resolve(strict=True)
            except FileNotFoundError:
                pass
        raise FileNotFoundError(
            f"Failed to find {const.DIRT_INI_FNAMES} in '{origin!s}' and parents"
        )


def bootstrap() -> int:
    """Entrypoint for Dirt when invoked directly.

    1. Find dirt.ini or use --config argument.
    2. Create .dirt working dir relative to dirt.ini.
    3. Read `tasks_package` and `tasks_pipeline` from `[dirt]` section of ini.
    4. Hash key files in `tasks_package` for potential changes.
    4. Create, re-create, or use existing virtualenv (venv) by hashing `tasks_package` for changes.
    5. If
    """
    # TODO: Use prefix= to segment options
    # TODO: Figure out how to incorporate env and config files?
    # TODO: ENV variables like this: DIRT_CONF_0='--foo bar -vvv'
    # TODO: Make .gitignore if not exists? Need to consider tasks_package

    origin = Path(os.getcwd()).resolve()
    opts, parser = _parse_core_options()

    def render_error_help() -> None:
        # Print help if there was an error (meaning dirt.cli wasn't able to
        # parse --help)
        if not opts.help:
            return
        # TODO: how flush logger?
        logger.error("Unhandled error; stacktrace will be printed after help")
        sys.stderr.flush()
        sys.stdout.flush()

        parser.print_help(sys.stdout)
        print("\n")
        sys.stdout.flush()

    try:
        # TODO: Merge user's overrides
        # Find the ini file to use
        dirt_ini = _find_root_dirt_ini(origin, opts)
        logger.debug("Found dirt.ini file %s", dirt_ini)

        # Read dirt.ini and extract needed config
        ini = IniParser(dirt_ini, origin)
        project_path = ini.dirt_tasks_project()
        tasks_main_str = ini.dirt_tasks_main()
        # TODO: Will actually want this at some point. Can parse from setup.py?
        #  at worse dirt.ini
        py_version = PY_VERSION

        # Build the main virtualenv
        # TODO: Need to figure how to clean up old venvs
        # TODO: prob skip creating hashes and just let the user destroy if needed
        project_venv_id = dirt.session.VirtualEnv.venv_id_for_project(project_path)
        project_venv_dir = ini.venv_dir / project_venv_id
        proj_venv = dirt.session.VirtualEnv(project_venv_dir, interpreter=py_version)
        # Pass dirt.ini and origin to all venv invocations
        proj_venv.env[const.ENV_DIRT_INI_FILE] = str(dirt_ini)
        proj_venv.env[const.ENV_DIRT_ORIGIN] = str(origin)
        # with console.status("[bold green]Creating base virtualenv"):
        with utils.out.progress() as progress:
            t1 = progress.add_task("[blue]Creating base virtualenv", total=None)
            try:
                venv_is_new = proj_venv.create()
            except Exception:
                raise RuntimeError(f"Failed to create project venv: {project_venv_dir}")
            finally:
                progress.stop_task(t1)

        # Install tasks project
        python = dirt.utils.cmd.which("python", paths=proj_venv.bin_paths)
        cwd = str(dirt_ini.parent)
        logger.debug("python=%s cwd=%s", python, cwd)
        # Install the project if new venv
        if venv_is_new:
            with utils.out.progress() as progress:
                progress.add_task(
                    f"[green]Installing tasks project to primary virtualenv: [/][purple]{escape(str(project_path))}",
                    total=None,
                )
                subprocess.run(
                    [python, "-m", "pip", "install", "-e", str(project_path)],
                    env=proj_venv.env,
                    cwd=cwd,
                    check=True,
                )
        # Run
        # proj_venv.env already contains venv.bin_paths in PATH.
        if tasks_main_str.endswith(".py") and os.path.isfile(tasks_main_str):
            cmd = [python, tasks_main_str]
        else:
            cmd = [python, "-m", tasks_main_str]
        logger.debug("Starting tasks: %r", cmd)
        subprocess.run(cmd, env=proj_venv.env, cwd=cwd, check=True)

    except Exception as e:
        if isinstance(e, IgnoreThisError):
            return 1

        render_error_help()

        if isinstance(e, KnownError):
            if e.as_exception:
                logger.exception(e.message)
            else:
                logger.error(e.message)
        else:
            logger.exception("Unexpected fatal error")
        return 1

    return 0  # success
