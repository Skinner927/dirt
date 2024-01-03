from __future__ import annotations

import hashlib
import logging
import os
import re
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

from dirt.ini_parser import IniParser


class Session:
    pass


class Runner:
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

    def __init__(
        self,
        name: str,
        dirt_ini_file_path: Path,
        invoked_path: Path,
        logger: Optional[logging.Logger] = None,
    ) -> None:
        """Init Runner to read dirt.ini and run tasks.

        :param name: Name of the dirt runner. Useful if wanting to rename.
        :param dirt_ini_file_path: Absolute path to dirt.ini file.
        :param invoked_path: Absolute path where dirt was called from.
        :param logger: Optional logger to use.
        """
        self.name = name
        self.lower_name = self.lower_sanitized_name(self.name)
        self.dirt_init_file_path = dirt_ini_file_path
        self.invoked_path = invoked_path
        self.root_log = logger or logging.getLogger(self.lower_name)
        self.log = self.root_log.getChild(self.__class__.__name__)

    @staticmethod
    def lower_sanitized_name(name: str) -> str:
        return re.sub(r"[^a-zA-Z0-9_.]", "_", name.lower())

    @classmethod
    def bootstrap(cls, name: str, start_dir: Union[None, Path, str] = None) -> Runner:
        """Create a Runner by searching current dir and up for dirt.ini.

        :param name:
        :param start_dir:
        :return:
        """
        start: Path = Path(start_dir or os.getcwd())
        lower_name = cls.lower_sanitized_name(name)

        log = logging.getLogger(lower_name)
        log.debug("Starting bootstrap @ %s", start)

        # Find dirt.ini
        ini_files = (f"{lower_name}.ini", f".{lower_name}.ini")
        dirt_ini_file_path: Optional[Path] = cls.search_path_for(
            start, names=ini_files, kind="file"
        )
        if not dirt_ini_file_path:
            raise RuntimeError(
                f"Could not find {ini_files} files in {start} and all parents"
            )
        log.debug("Found dirt.ini file @ %s", dirt_ini_file_path)

        return cls(
            name=name,
            dirt_ini_file_path=dirt_ini_file_path,
            invoked_path=start,
            logger=log,
        )

    def run(self, argv: Optional[Sequence[str]] = None):
        """Create any venvs and run tasks.

        :param argv: Override default args from `sys.argv`.
        """
        self.log.debug("Runner.run()")
        if argv is None:
            # Use sys args by default
            argv = sys.argv

        # Create needed dirs.
        self.create_session(self.dirt_init_file_path)

    @classmethod
    def create_session(
        cls,
        dirt_ini_file_path: Path,
        create_gitignore: Union[None, Literal[True, False]] = None,
        create_parents: bool = False,
    ) -> Session:
        """Create the directories and venv Dirt needs to run.

        This function will likely be useful for bootstrapping test directories
        thus it's static and all the options.

        :param dirt_ini_file_path:
        :param create_gitignore: `None` will determine if dirt.ini is in a git repo.
        :param create_parents: Should parent directories be created?
        :return:
        """
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
        pkg_path, mod_name = self.resolve_valid_task_module_path(dirt_ini)
        self.log.debug("pkg_path=%s mod_name=%s", pkg_path, mod_name)

        # Get the hash
        pkg_hash = self.hash_project_dir(pkg_path)
        # Dir that will exist if we don't believe there are changes
        env_dir = venv_dir / f"{pkg_path.name}-{mod_name}-{pkg_hash}"
        if not env_dir.is_dir():
            # Need to make the env
            venv.create(env_dir, with_pip=True, symlinks=("nt" != os.name))
        self.log.debug("Creating venv %s", env_dir)

        self.venv_run(
            env_dir,
            self.PY_EXE,
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

        task_module_name = dirt_ini.dirt_tasks_project()
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
