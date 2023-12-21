from __future__ import annotations

import hashlib
import logging
import os
import subprocess
import sys
import venv
from pathlib import Path
from typing import Union, Optional, List, ClassVar, Set, Tuple

from dirt.ini_parser import IniParser


class Bootstrapper:
    """Creates Dirt environments to run task projects."""

    DIRT_INI: ClassVar[List[str]] = ["dirt.ini", ".dirt.ini"]
    PY_REQUIREMENT_FILES: ClassVar[Set[str]] = {
        "setup.py",
        "setup.cfg",
        "pyproject.toml",
        "requirements.txt",
    }
    DEFAULT_TASKS_MODULES: ClassVar[List[str]] = [".dirt/tasks:tasks", "tasks:tasks"]
    PY_EXE: ClassVar[List[str]] = ["python3", "python3.exe", "python", "python.exe"]

    log: ClassVar[logging.Logger] = logging.getLogger(f"{__name__}.Bootstrapper")

    def __init__(self, start_dir: Union[None, Path, str] = None) -> None:
        self.start_dir: Path = Path(start_dir or os.getcwd())

    def start(self, argv: Optional[List[str]] = None) -> None:
        """Search for dirt.ini, create any environments and run tasks.

        :param argv: Override default args from `sys.argv`.
        """
        self.log.debug("Starting bootstrap")
        if argv is None:
            # Use sys args by default
            argv = sys.argv

        # Find dirt.ini
        dirt_ini_path: Optional[Path] = self.find_dirt_ini(self.start_dir)
        if not dirt_ini_path:
            raise RuntimeError(
                f"Could not find dirt.ini file in {self.start_dir} and all parents"
            )
        if not dirt_ini_path.is_file():
            raise RuntimeError(f"Resolved dirt.ini is not a file: {dirt_ini_path}")
        self.log.debug("Found dirt.ini file at %s", dirt_ini_path)

        # Make .dirt directory for us to work in
        dot_dirt = dirt_ini_path.parent / ".dirt"
        dot_env = dot_dirt / ".env"
        dot_env.mkdir(parents=True, exist_ok=True)

        # Load dirt.ini
        dirt_ini = IniParser(dirt_ini_path)
        # Find task_module
        pkg_path, mod_name = self.resolve_valid_task_module_path(dirt_ini)
        self.log.debug("pkg_path=%s mod_name=%s", pkg_path, mod_name)

        # Get the hash
        pkg_hash = self.hash_project_dir(pkg_path)
        # Dir that will exist if we don't believe there are changes
        env_dir = dot_env / f"{pkg_path.name}-{mod_name}-{pkg_hash}"
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
    def find_dirt_ini(cls, start: Path) -> Optional[Path]:
        """Walk up the directory tree looking for the first dirt.ini file.

        :param start: Where to start searching
        :return: None if not found
        """
        seen = set()
        current = start
        while current:
            # Check for loops
            if current in seen:
                raise RecursionError(f"Circular pathing detected: {current}")
            seen.add(current)

            # Check for dirt.ini or .dirt.ini file
            for ini_file in cls.DIRT_INI:
                dirt_ini = current / ini_file
                if dirt_ini.is_file():
                    return dirt_ini.resolve()
            # Crawl up
            current = current.parent
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
        tried_modules: List[str] | str

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
        exe: str | List[str],
        args: List[str],
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

        full_args = [use_exe, *args]
        cls.log.debug("venv_run %s", full_args)
        return subprocess.run(full_args, env=new_env, check=check)
