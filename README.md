# Dirt

*Dirt is under development. Any claims in this README may not be implemented.*

Dirt is a task runner designed for teams that work on multiple projects who
want to share common workflows with small augments at the project level.
Dirt works with monorepos. It also
targets older technologies for better support for
[legacy systems](#legacy-support).

Tasks can run directly on the user's machine, in a local container, or on a
remote host. The Task writer can suggest or forbid where a Task can and cannot
run. Users have the ability to run a hierarchy of tests.

Tasks, Pipelines, everything are defined in Python -- there's no domain specific
YAML here (there are basic config files, but those will be explained later).

## Naming

Dirt doesn't stand for anything, but if it did, it would be:

> Dirt Intelligently Runs Tasks

Dirt also doesn't care if it's capitalized or not. You may write "dirt", "Dirt",
"DiRt", "DIRT", or anything in-between.

## Legacy support

I hope to rewrite this in C one day for true legacy support, but
for now Python 3.8 is the target for faster development. Python 3.8 can target
back to Windows 7 and Ubuntu 18.04 (wow, neither of those sound very old) and
still supports decent typing support.

## Config

Dirt has some internal options, but Tasks are also supposed to be configured.
Most of the configuration will be done in the local `.dirt/dirt.ini` file. By
default, all options can be configured from the command line, local, global, and
user configuration files, and environment variables, but Task authors have the
ability to forbid configuration from any of these mediums.

Dirt keeps track of everywhere it got configuration from, and you may
display the resolved configuration with the `--print-config` option.

### Command line args

```shell
# Run all build pipelines
dirt pipe :build --no-container --foo-bar
```

```shell
# Run all pipelines for the robot project
dirt pipe robot: --oranges 'please'
```

```shell
# Run all test pipelines for the robot project
dirt pipe robot:test --peanuts one,two,three
```

### Config file

Headers like `ini`, but keys are like command line args (and require `=`).
The `--` prefix is optional.
List values can be expressed using whitespace (including newlines)
or comma-separated just as on the command line.

```ini
[dirt]
# Globals
--no-container

foo-bar=true

peanuts=
  one
  two
  three
```

#### Config file order

When `dirt` is run, it looks in the current directory for a directory named
`.dirt`. If it does not find one, it continues up the directory tree until one
is found or errors (like git). Inside the `.dirt` directory is a file named
`dirt.ini` that describes what Dirt can run (more on this later).

Out of band configuration files will be loaded after the local `dirt.ini` and
may be used to override values. The order in which files are searched and loaded
are as follows (with the last file having the highest precedence).

`XDG_CONFIG_HOME` will default to `~/.config` if undefined.

<!-- This is basically same as how pip does it https://pip.pypa.io/en/stable/topics/configuration/ -->
<!-- TODO: Prob want to verify non-world writable on Unix/Mac? -->

##### Unix (Linux, macOS, embedded)
- `${XDG_CONFIG_DIRS}/dirt/dirt.ini`
- `/Library/Application Support/dirt/dirt.ini` (macOS only)
- `/opt/dirt/dirt.ini`
- `~/.dirt/dirt.ini`
- `${XDG_CONFIG_HOME:-~/.config}/dirt/dirt.ini`
- `~/Library/Application Support/dirt/dirt.ini` (macOS only)

##### Windows
- `C:\dirt\dirt.ini`
- `C:\ProgramData\dirt\dirt.ini`
- `%APPDATA%\dirt.ini`
- `~\.config\dirt\dirt.ini`

### Environment variables

Because POSIX environment variable names leave much to be desired, you may use
any env that starts with `DIRT_ARG_` to define options. All `DIRT_ARG_*` envs
will be concatenated in alphabetical order and parsed as command-line arguments.

```
DIRT_ARG_first='--foo-bar=true'
DIRT_ARG_second='--oranges "no thank you"'
```

## Running Dirt

When Dirt is run, it first checks for the `tasks_module` configuration
(`[dirt] tasks_module=tasks` in the `.ini` file) and defaults to `tasks` if one
does not exist. This means the directory `.dirt/tasks` should exist with an
installable Python package at the root. Specify a deeper path like
`tasks_module=tasks/foo/bar/here`. By default, the module invoked is the same
name as the last directory in `tasks_module`. You may override the module
with a `:module_name` suffix. This is how you would run the "do_work" module
in the "tasks" directory `tasks_module=tasks:do_work`. (TODO: handle `c:\foo\bar:mod`)

Dirt then creates a virtualenv and installs `tasks_module` into it and runs the
module. Dirt detects changes to `tasks_module` two ways:

1. If `tasks_module` is a submodule or git repo, the commit hash is used to
   track changes.
2. All setup files are hashed for changes. Default setup files can be
   overridden with the `task_setup_files` option. The default list is:
   - `pyproject.toml`
   - `setup.cfg`
   - `setup.py`

(TODO: Need flag for installing `tasks_module` as editable)

Dirt will cache up to 5 environments per project to facilitate faster runs.

(TODO: need flag for clearing this. Also, config for overriding.)

## Tasks

### Python requirements

Each Task may specify its own requirements for the task are installed into the
virtualenv when run. If requirements change while developing, it may be needed
to manually delete the cached virtualenvs.

## TODO: Other ideas

- `dirt init`, `dirt init --no-task-repo`
- `dirt --print-config`
- Options can be "secret" so they're masked when printed.
- Tasks can specify optional/required runners that the task should be run in.
- Tasks can specify "input" and "output" file globs to determine if they need to
  be re-run. `--force` skips those checks.
- Tasks can specify dependencies. These can be explicit tasks, global stages, or
  stages only within their pipeline.
- Magic stage `.first` and `.last` to always run first/last, otherwise
  everything *should* be able to be computed as a DAG.
- Show task status with `+` (success), `x` (error), `-` (skipped).
- `--install-all-requirements` to install all requirements without running Tasks.
- Exporters turn the Task DAG into YAML for GitLAB or other CIs.
- You install `dirt` globally then run it when you need it. It will bootstrap
  the .dirt env and then invoke that version of dirt. This way your global dirt
  can be ancient, but not conflict with newer versions.
- We shouldn't auto-delete cached envs because we have no idea what the user
  may be doing (possibly switching between many branches a day). Instead we
  should display a little msg when they start collecting quite a few or 
  have stale envs. The message should follow the primary command they've run.
