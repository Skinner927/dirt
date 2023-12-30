from __future__ import annotations

import dataclasses
import hashlib
import logging
import os
import subprocess
import sys
import venv
from pathlib import Path
from typing import (
    ClassVar,
    Collection,
    List,
    Literal,
    Optional,
    Sequence,
    Set,
    Tuple,
    Union,
    cast,
)

import simple_parsing.utils

import dirt.utils
import dirt.utils.fs
from dirt import const
from dirt.args import AuditArgumentParser, field
from dirt.ini_parser import IniParser

logger = logging.getLogger(__name__)


@dataclasses.dataclass()
class BootstrapConfig(simple_parsing.utils.Dataclass):
    # Specify specific dirt.ini file to use.
    config: Optional[str] = field(
        alias=["-c"], default=None, action="store", nargs=1, metavar="file"
    )


def bootstrap() -> None:
    """Entrypoint for Dirt when invoked directly.

    1. Find dirt.ini or use --config argument.
    2. Create .dirt working dir relative to dirt.ini.
    3. Read `tasks_package` and `tasks_pipeline` from `[dirt]` section of ini.
    4. Hash key files in `tasks_package` for potential changes.
    4. Create, re-create, or use existing virtualenv (venv) by hashing `tasks_package` for changes.
    5. If
    """
    # Parse args for bootstrap options
    parser = AuditArgumentParser(add_help=False)
    parser.add_arguments(BootstrapConfig, dest="bootstrap")
    all_args, _ = parser.parse_known_args()
    args: BootstrapConfig = all_args.bootstrap

    # TODO: Use prefix= to segment options
    # TODO: Figure out how to incorporate env and config files?
    # TODO: ENV variables like this: DIRT_CONF_0='--foo bar -vvv'

    origin = Path(os.getcwd()).resolve()
    dirt_ini_file_path: Path
    if args.config:
        logger.debug("Bootstrapping with --config %s", args.config)
        dirt_ini_file_path = Path(args.config).resolve()
        if not dirt_ini_file_path.is_file():
            raise RuntimeError(f"Specified config {dirt_ini_file_path} is not a file")
    else:
        logger.debug("Bootstrapping from dir %s", origin)
        tmp_path = dirt.utils.fs.find_walking_up(
            origin, names=const.DEFAULT_DIRT_INI_FNAMES, kind="file"
        )
        if tmp_path is None or not tmp_path.is_file():
            raise RuntimeError(
                f"Could not find {const.DEFAULT_DIRT_INI_FNAMES} files "
                f"in {origin} and all parent directories"
            )
        dirt_ini_file_path = tmp_path
        logger.debug("Found dirt.ini file %s", dirt_ini_file_path)


class Bootstrapper:
    """Entry point for Dirt.

    1. Finds `dirt.ini`
    2. Finds `tasks_module`
    3. Creates venv (if needed)
    4. Installs `tasks_module`
    5. Runs Dirt.

    `start()` is where the magic happens.
    """

    DIRT_INI_NAMES: ClassVar[Tuple[str, ...]] = ("dirt.ini", ".dirt.ini")
    """Names of the dirt.ini files to search for.

    First match wins.
    """
    PY_REQUIREMENT_FILES: ClassVar[Tuple[str, ...]] = (
        "setup.py",
        "setup.cfg",
        "pyproject.toml",
        "requirements.txt",
    )
    """Files used to hash a tasks_module project for changes.

    If these files are changed, the environment is re-created.
    """
    DIRT_DIR_NAME: ClassVar[str] = ".dirt"
    """Working directory for Dirt."""
    VENV_DIR_NAME: ClassVar[str] = "venv"
    """Directory that stores all cached virtualenvs inside DIRT_DIR_NAME."""
    DEFAULT_TASKS_MODULES: ClassVar[Tuple[str, ...]] = (
        f"{DIRT_DIR_NAME}/tasks = tasks",
        "tasks = tasks",
    )
    """If tasks_module is not set, these are the defaults to check.

    Format: DIRECTORY_PATH = MODULE[:FUNCTION]
    """
    PY_EXE: ClassVar[Tuple[str, ...]] = (
        "python3",
        "python3.exe",
        "python",
        "python.exe",
    )
    """Python binaries to attempt to use in each venv."""

    log: ClassVar[logging.Logger] = logger.getChild("Bootstrapper")

    def __init__(
        self, name: Optional[str] = None, *, start_dir: Union[None, Path, str] = None
    ) -> None:
        self.name: str = name or const.NAME
        self.start_dir: Path = Path(start_dir or os.getcwd())

    def start(self, argv: Optional[Sequence[str]] = None) -> None:
        """Search for dirt.ini, create any environments and run tasks.

        :param argv: Override default args from `sys.argv`.
        """
        self.log.debug("Starting bootstrap")
        if argv is None:
            # Use sys args by default
            argv = sys.argv

        # Find dirt.ini
        dirt_ini_file_path = self.search_path_for(
            self.start_dir, names=self.DIRT_INI_NAMES, kind="file"
        )
        if not dirt_ini_file_path:
            raise RuntimeError(
                f"Could not find dirt.ini file in {self.start_dir} and all parents"
            )
        if not dirt_ini_file_path.is_file():
            raise RuntimeError(f"Resolved dirt.ini is not a file: {dirt_ini_file_path}")
        self.log.debug("Found dirt.ini file at %s", dirt_ini_file_path)

        # Prepare the environment
        self.prepare_environment(dirt_ini_file_path)

    @classmethod
    def prepare_environment(
        cls,
        dirt_ini_file_path: Path,
        create_gitignore: Union[None, Literal[True, False]] = None,
        create_parents: bool = False,
    ) -> None:
        # Function creates the directories and venv Dirt needs to run.
        # This function will likely be useful for bootstrapping test directories
        # thus all the options.
        if create_gitignore is None:
            # Create .gitignores if in a git repo
            create_gitignore = not not cls.search_path_for(
                dirt_ini_file_path.parent, names=[".git"], kind="dir"
            )

        # Make .dirt directory for us to work in
        dot_dirt = dirt_ini_file_path.parent / cls.DIRT_DIR_NAME
        created_dot_dirt_gitignore = False
        if not dot_dirt.is_dir():
            dot_dirt.mkdir(parents=create_parents, exist_ok=False)
            if create_gitignore:
                # Create .gitignore to ignore everything
                (dot_dirt / ".gitignore").write_text("*\n!.gitignore\n")
                created_dot_dirt_gitignore = True

        # .dirt/venv is where all cached virtualenvs are stored
        venv_dir = dot_dirt / cls.VENV_DIR_NAME
        if not venv_dir.is_dir():
            venv_dir.mkdir(parents=False, exist_ok=False)
            if not created_dot_dirt_gitignore and create_gitignore:
                # Create .gitignore to ignore everything
                (venv_dir / ".gitignore").write_text("*\n!.gitignore\n")

        # Load dirt.ini
        dirt_ini = IniParser(dirt_ini_file_path)
        # Find task_module
        pkg_path, mod_name = cls.resolve_valid_task_module_path(dirt_ini)
        cls.log.debug("pkg_path=%s mod_name=%s", pkg_path, mod_name)

        # Get the hash
        pkg_hash = cls.hash_project_dir(pkg_path)
        # Dir that will exist if we don't believe there are changes
        env_dir = venv_dir / f"{pkg_path.name}-{mod_name}-{pkg_hash}"
        if not env_dir.is_dir():
            # Need to make the env
            venv.create(env_dir, with_pip=True, symlinks=("nt" != os.name))
        cls.log.debug("Creating venv %s", env_dir)

        cls.venv_run(
            env_dir,
            cls.PY_EXE,
            ["-m", "pip", "install", "-e", str(pkg_path.absolute())],
        )
        # self.venv_install_package(env_dir, pkg_path)

        # TODO: track env hashes and purge old envs

    @classmethod
    def search_path_for(
        cls,
        start: Path,
        *,
        names: Collection[str],
        kind: Optional[Literal["dir", "file"]] = None,
        on_recursion: Optional[Literal["raise", "ignore"]] = "ignore",
    ) -> Union[Path, None]:
        """Walk directory tree from `start` to root looking for `names`.

        :param start: Where to start the search.
        :param names: One or more items to find.
        :param kind: Specify "file" or "dir" to limit search to specific types.
         `None` only checks if it exists.
        :param on_recursion: "raise" will raise a RecursionError if a loop in
         the file system is detected. "ignore" or `None` will return `None.
        :return: Found Path or `None` if not found. Returned path will be
         resolved with `pathlib.resolve()` which makes the path
         absolute, resolving all symlinks on the way and also normalizing it.
        :raises: RecursionError if a loop in the file system is detected.
        """
        if isinstance(names, str):
            names = [names]
        seen: Set[str] = set()
        last: Optional[Path] = None
        current: Optional[Path] = start.resolve()
        while current and current != last:
            last = current
            current_str = str(current)
            # Check for loops
            if current_str in seen:
                msg = f"{cls.search_path_for.__name__}() - circular pathing detected: {current}"
                cls.log.debug(msg)
                if "raise" == on_recursion:
                    raise RecursionError(msg)
                return None
            seen.add(current_str)

            # Check for dirt.ini or .dirt.ini file
            for target_name in names:
                target = current / target_name
                if "dir" == kind:
                    if target.is_dir():
                        return target.resolve()
                elif "file" == kind:
                    if target.is_file():
                        return target.resolve()
                else:
                    if target.exists():
                        return target.resolve()
            # Crawl up
            current = current.parent.resolve()
        return None

    @staticmethod
    def split_task_module(
        task_module_name: str,
    ) -> Tuple[Optional[Path], Optional[str]]:
        """Split the task_module string and verify path exists.

        :param task_module_name: Should be a string in the form "path" or "path:module"
        :return: `(path_to_package*, module_name)`
            **On failure:** both are `None`.
            **On success:**
                - *path_to_package* is verified to be a valid directory.
                - *module_name* falls back to package directory's name.
        """
        path_str, _, mod_str = task_module_name.partition(":")
        path = Path(path_str)
        if not path.is_dir():
            # Failure
            return None, None

        if not mod_str:
            # Module name falls back to directory's name
            mod_str = path.name
        # Success
        return path.resolve(), mod_str

    @classmethod
    def resolve_valid_task_module_path(cls, dirt_ini: IniParser) -> Tuple[Path, str]:
        """Resolve a valid task package path and module name.

        :param dirt_ini:
        :raises RuntimeError: If package path is invalid
        :return: Existing package directory and module name
        """
        pkg_path, mod_name = None, None
        tried_modules: Sequence[str] | str

        task_module_name = dirt_ini.dirt_task_module()
        if task_module_name is not None:
            # Try value from dirt.ini
            tried_modules = task_module_name
            pkg_path, mod_name = cls.split_task_module(task_module_name)
        else:
            # Try defaults
            tried_modules = cls.DEFAULT_TASKS_MODULES
            for task_module_name in cls.DEFAULT_TASKS_MODULES:
                pkg_path, mod_name = cls.split_task_module(task_module_name)
                if pkg_path and mod_name:
                    break

        # Validate
        if not pkg_path or not mod_name:
            raise RuntimeError(
                f"Failed to find module {tried_modules} from {IniParser.TASK_MODULE} in dirt.ini {dirt_ini.filename}"
            )

        return pkg_path, mod_name

    @classmethod
    def hash_project_dir(cls, project_dir: Path) -> str:
        # Copied Py3.11 hashlib.file_digest()
        # https://github.com/python/cpython/blob/0b13575e74ff3321364a3389eda6b4e92792afe1/Lib/hashlib.py
        buffer_size = 2**18
        buffer = bytearray(buffer_size)  # Reusable
        view = memoryview(buffer)

        digest = hashlib.md5()
        # Start digest with project path
        digest.update(str(project_dir).encode("utf-8"))

        for req_name in cls.PY_REQUIREMENT_FILES:
            file = project_dir / req_name
            if not file.exists():
                continue
            # Add this file's path
            digest.update(str(file).encode("utf-8"))
            with file.open("rb") as fb:
                # Read file into digest
                while True:
                    size = fb.readinto(buffer)
                    if 0 == size:
                        break  # EOF
                    digest.update(view[:size])

        return digest.hexdigest()

    @classmethod
    def venv_run(
        cls,
        venv_dir: Path,
        exe: str | Sequence[str],
        args: Sequence[str],
        check: bool = True,
    ) -> subprocess.CompletedProcess[str]:
        if not venv_dir.is_dir():
            raise ValueError(f"venv directory {venv_dir} does not exist")
        # Put the venv's bin path at front of PATH
        bin_name = "Scripts" if "nt" == os.name else "bin"
        venv_bin = (venv_dir / bin_name).absolute()
        new_path = str(venv_bin)
        if old_path := os.getenv("PATH"):
            # Append existing path
            new_path += os.pathsep + old_path

        # Copy current env (but don't use .copy() because it's an os._Environ)
        new_env = dict(os.environ)
        # Update PATH
        new_env["PATH"] = new_path
        # Drop VIRTUAL_ENV
        if "VIRTUAL_ENV" in new_env:
            del new_env["VIRTUAL_ENV"]

        if isinstance(exe, str):
            use_exe = exe
        else:
            if not isinstance(exe, List):
                raise TypeError(f"Exe should be a list or string, got {type(exe)}")
            if 0 == len(exe):
                raise ValueError("No executable specified")
            use_exe = ""
            for candidate in exe:
                new_exe = venv_dir / bin_name / candidate
                if new_exe.exists():
                    # Do not resolve
                    use_exe = str(new_exe.absolute())
            if not use_exe:
                use_exe = exe[0]

        # -B: Don't write .pyc bytecode
        full_args = [use_exe, "-B", *args]
        cls.log.debug("venv_run %s", full_args)
        r = subprocess.run(full_args, env=new_env, check=check)
        return cast(subprocess.CompletedProcess[str], r)
