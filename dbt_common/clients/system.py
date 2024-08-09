import dbt_common.exceptions.base
import dataclasses
import errno
import fnmatch
import functools
import json
import os
import os.path
import re
import shutil
import stat
import subprocess
import sys
import tarfile
from pathlib import Path
from typing import Any, Callable, Dict, List, NoReturn, Optional, Tuple, Type, Union

import dbt_common.exceptions
import requests
from dbt_common.events.functions import fire_event
from dbt_common.events.types import (
    SystemCouldNotWrite,
    SystemExecutingCmd,
    SystemStdOut,
    SystemStdErr,
    SystemReportReturnCode,
)
from dbt_common.exceptions import DbtInternalError
from dbt_common.record import record_function, Recorder, Record
from dbt_common.utils.connection import connection_exception_retry

from pathspec import PathSpec  # type: ignore

if sys.platform == "win32":
    from ctypes import WinDLL, c_bool
else:
    WinDLL = None
    c_bool = None


def _record_path(path: str) -> bool:
    return (
        # TODO: The first check here obviates the next two checks but is probably too coarse?
        "dbt/include" not in path
        and "dbt/include/global_project" not in path
        and "/plugins/postgres/dbt/include/" not in path
    )


@dataclasses.dataclass
class FindMatchingParams:
    root_path: str
    relative_paths_to_search: List[str]
    file_pattern: str

    # ignore_spec: Optional[PathSpec] = None

    def __init__(
        self,
        root_path: str,
        relative_paths_to_search: List[str],
        file_pattern: str,
        ignore_spec: Optional[Any] = None,
    ):
        self.root_path = root_path
        rps = list(relative_paths_to_search)
        rps.sort()
        self.relative_paths_to_search = rps
        self.file_pattern = file_pattern

    def _include(self) -> bool:
        # Do not record or replay filesystem searches that were performed against
        # files which are actually part of dbt's implementation.
        return _record_path(self.root_path)


@dataclasses.dataclass
class FindMatchingResult:
    matches: List[Dict[str, Any]]


@Recorder.register_record_type
class FindMatchingRecord(Record):
    """Record of calls to the directory search function find_matching()"""

    params_cls = FindMatchingParams
    result_cls = FindMatchingResult


@record_function(FindMatchingRecord)
def find_matching(
    root_path: str,
    relative_paths_to_search: List[str],
    file_pattern: str,
    ignore_spec: Optional[PathSpec] = None,
) -> List[Dict[str, Any]]:
    """Return file info from paths and patterns.

    Given an absolute `root_path`, a list of relative paths to that
    absolute root path (`relative_paths_to_search`), and a `file_pattern`
    like '*.sql', returns information about the files. For example:

    > find_matching('/root/path', ['models'], '*.sql')

      [ { 'absolute_path': '/root/path/models/model_one.sql',
          'relative_path': 'model_one.sql',
          'searched_path': 'models' },
        { 'absolute_path': '/root/path/models/subdirectory/model_two.sql',
          'relative_path': 'subdirectory/model_two.sql',
          'searched_path': 'models' } ]
    """
    matching = []
    root_path = os.path.normpath(root_path)
    regex = fnmatch.translate(file_pattern)
    reobj = re.compile(regex, re.IGNORECASE)

    for relative_path_to_search in relative_paths_to_search:
        # potential speedup for ignore_spec
        # if ignore_spec.matches(relative_path_to_search):
        #     continue
        absolute_path_to_search = os.path.join(root_path, relative_path_to_search)
        walk_results = os.walk(absolute_path_to_search)

        for current_path, subdirectories, local_files in walk_results:
            # potential speedup for ignore_spec
            # relative_dir = os.path.relpath(current_path, root_path) + os.sep
            # if ignore_spec.match(relative_dir):
            #     continue
            for local_file in local_files:
                absolute_path = os.path.join(current_path, local_file)
                relative_path = os.path.relpath(absolute_path, absolute_path_to_search)
                relative_path_to_root = os.path.join(relative_path_to_search, relative_path)

                modification_time = os.path.getmtime(absolute_path)
                if reobj.match(local_file) and (
                    not ignore_spec or not ignore_spec.match_file(relative_path_to_root)
                ):
                    matching.append(
                        {
                            "searched_path": relative_path_to_search,
                            "absolute_path": absolute_path,
                            "relative_path": relative_path,
                            "modification_time": modification_time,
                        }
                    )

    return matching


@dataclasses.dataclass
class LoadFileParams:
    path: str
    strip: bool = True

    def _include(self) -> bool:
        # Do not record or replay file reads that were performed against files
        # which are actually part of dbt's implementation.
        return _record_path(self.path)


@dataclasses.dataclass
class LoadFileResult:
    contents: str


@Recorder.register_record_type
class LoadFileRecord(Record):
    """Record of file load operation"""

    params_cls = LoadFileParams
    result_cls = LoadFileResult


@record_function(LoadFileRecord)
def load_file_contents(path: str, strip: bool = True) -> str:
    path = convert_path(path)
    with open(path, "rb") as handle:
        to_return = handle.read().decode("utf-8")

    if strip:
        to_return = to_return.strip()

    return to_return


@functools.singledispatch
def make_directory(path=None) -> None:
    """Handle directory creation with threading.

    Make a directory and any intermediate directories that don't already
    exist. This function handles the case where two threads try to create
    a directory at once.
    """
    raise DbtInternalError(f"Can not create directory from {type(path)} ")


@make_directory.register
def _(path: str) -> None:
    path = convert_path(path)
    if not os.path.exists(path):
        # concurrent writes that try to create the same dir can fail
        try:
            os.makedirs(path)

        except OSError as e:
            if e.errno == errno.EEXIST:
                pass
            else:
                raise e


@make_directory.register
def _(path: Path) -> None:
    path.mkdir(parents=True, exist_ok=True)


def make_file(path: str, contents: str = "", overwrite: bool = False) -> bool:
    """Make a file with `contents` at `path`.

    Make a file at `path` assuming that the directory it resides in already
    exists. The file is saved with contents `contents`
    """
    if overwrite or not os.path.exists(path):
        path = convert_path(path)
        with open(path, "w") as fh:
            fh.write(contents)
        return True

    return False


def make_symlink(source: str, link_path: str) -> None:
    """Create a symlink at `link_path` referring to `source`."""
    if not supports_symlinks():
        # TODO: why not import these at top?
        raise dbt_common.exceptions.SymbolicLinkError()

    os.symlink(source, link_path)


def supports_symlinks() -> bool:
    return getattr(os, "symlink", None) is not None


@dataclasses.dataclass
class WriteFileParams:
    path: str
    contents: str

    def _include(self) -> bool:
        # Do not record or replay file reads that were performed against files
        # which are actually part of dbt's implementation.
        return _record_path(self.path)


@Recorder.register_record_type
class WriteFileRecord(Record):
    """Record of a file write operation."""

    params_cls = WriteFileParams
    result_cls = None


@record_function(WriteFileRecord)
def write_file(path: str, contents: str = "") -> bool:
    path = convert_path(path)
    try:
        make_directory(os.path.dirname(path))
        with open(path, "w", encoding="utf-8") as f:
            f.write(str(contents))
    except Exception as exc:
        # note that you can't just catch FileNotFound, because sometimes
        # windows apparently raises something else.
        # It's also not sufficient to look at the path length, because
        # sometimes windows fails to write paths that are less than the length
        # limit. So on windows, suppress all errors that happen from writing
        # to disk.
        if os.name == "nt":
            # sometimes we get a winerror of 3 which means the path was
            # definitely too long, but other times we don't and it means the
            # path was just probably too long. This is probably based on the
            # windows/python version.
            if getattr(exc, "winerror", 0) == 3:
                reason = "Path was too long"
            else:
                reason = "Path was possibly too long"
            # all our hard work and the path was still too long. Log and
            # continue.
            fire_event(SystemCouldNotWrite(path=path, reason=reason, exc=str(exc)))
        else:
            raise
    return True


def read_json(path: str) -> Dict[str, Any]:
    path = convert_path(path)
    with open(path, "r") as f:
        return json.load(f)


def write_json(path: str, data: Dict[str, Any]) -> bool:
    path = convert_path(path)
    try:
        make_directory(os.path.dirname(path))
        with open(path, "w", encoding="utf-8") as f:
            json.dump(data, f, cls=dbt_common.utils.encoding.JSONEncoder)
    except Exception as exc:
        # See write_file() for an explanation of this error handling.
        if os.name == "nt":
            if getattr(exc, "winerror", 0) == 3:
                reason = "Path was too long"
            else:
                reason = "Path was possibly too long"
            fire_event(SystemCouldNotWrite(path=path, reason=reason, exc=str(exc)))
        else:
            raise
    return True


def _windows_rmdir_readonly(func: Callable[[str], Any], path: str, exc: Tuple[Any, OSError, Any]):
    exception_val = exc[1]
    if exception_val.errno == errno.EACCES:
        os.chmod(path, stat.S_IWUSR)
        func(path)
    else:
        raise


def resolve_path_from_base(path_to_resolve: str, base_path: str) -> str:
    """If path_to_resolve is a relative path, create an absolute path with base_path as the base.

    If path_to_resolve is an absolute path or a user path (~), just
    resolve it to an absolute path and return.
    """
    return os.path.abspath(os.path.join(base_path, os.path.expanduser(path_to_resolve)))


def rmdir(path: str) -> None:
    """Recursively deletes a directory.

    Includes an error handler to retry with
    different permissions on Windows. Otherwise, removing directories (eg.
    cloned via git) can cause rmtree to throw a PermissionError exception
    """
    path = convert_path(path)
    if sys.platform == "win32":
        onerror = _windows_rmdir_readonly
    else:
        onerror = None

    shutil.rmtree(path, onerror=onerror)


def _win_prepare_path(path: str) -> str:
    """Given a windows path, prepare it for use by making sure it is absolute and normalized."""
    path = os.path.normpath(path)

    # if a path starts with '\', splitdrive() on it will return '' for the
    # drive, but the prefix requires a drive letter. So let's add the drive
    # letter back in.
    # Unless it starts with '\\'. In that case, the path is a UNC mount point
    # and splitdrive will be fine.
    if not path.startswith("\\\\") and path.startswith("\\"):
        curdrive = os.path.splitdrive(os.getcwd())[0]
        path = curdrive + path

    # now our path is either an absolute UNC path or relative to the current
    # directory. If it's relative, we need to make it absolute or the prefix
    # won't work. `ntpath.abspath` allegedly doesn't always play nice with long
    # paths, so do this instead.
    if not os.path.splitdrive(path)[0]:
        path = os.path.join(os.getcwd(), path)

    return path


def _supports_long_paths() -> bool:
    if sys.platform != "win32":
        return True
    # Eryk Sun says to use `WinDLL('ntdll')` instead of `windll.ntdll` because
    # of pointer caching in a comment here:
    # https://stackoverflow.com/a/35097999/11262881
    # I don't know exaclty what he means, but I am inclined to believe him as
    # he's pretty active on Python windows bugs!
    else:
        try:
            dll = WinDLL("ntdll")
        except OSError:  # I don't think this happens? you need ntdll to run python
            return False
        # not all windows versions have it at all
        if not hasattr(dll, "RtlAreLongPathsEnabled"):
            return False
        # tell windows we want to get back a single unsigned byte (a bool).
        dll.RtlAreLongPathsEnabled.restype = c_bool
        return dll.RtlAreLongPathsEnabled()


def convert_path(path: str) -> str:
    """Handle path length for windows.

    Convert a path that dbt has, which might be >260 characters long, to one
    that will be writable/readable on Windows.

    On other platforms, this is a no-op.
    """
    # some parts of python seem to append '\*.*' to strings, better safe than
    # sorry.
    if len(path) < 250:
        return path
    if _supports_long_paths():
        return path

    prefix = "\\\\?\\"
    # Nothing to do
    if path.startswith(prefix):
        return path

    path = _win_prepare_path(path)

    # add the prefix. The check is just in case os.getcwd() does something
    # unexpected - I believe this if-state should always be True though!
    if not path.startswith(prefix):
        path = prefix + path
    return path


def remove_file(path: str) -> None:
    path = convert_path(path)
    os.remove(path)


def path_exists(path: str) -> bool:
    path = convert_path(path)
    return os.path.lexists(path)


def path_is_symlink(path: str) -> bool:
    path = convert_path(path)
    return os.path.islink(path)


def open_dir_cmd() -> str:
    # https://docs.python.org/2/library/sys.html#sys.platform
    if sys.platform == "win32":
        return "start"

    elif sys.platform == "darwin":
        return "open"

    else:
        return "xdg-open"


def _handle_posix_cwd_error(exc: OSError, cwd: str, cmd: List[str]) -> NoReturn:
    if exc.errno == errno.ENOENT:
        message = "Directory does not exist"
    elif exc.errno == errno.EACCES:
        message = "Current user cannot access directory, check permissions"
    elif exc.errno == errno.ENOTDIR:
        message = "Not a directory"
    else:
        message = "Unknown OSError: {} - cwd".format(str(exc))
    raise dbt_common.exceptions.WorkingDirectoryError(cwd, cmd, message)


def _handle_posix_cmd_error(exc: OSError, cwd: str, cmd: List[str]) -> NoReturn:
    if exc.errno == errno.ENOENT:
        message = "Could not find command, ensure it is in the user's PATH"
    elif exc.errno == errno.EACCES:
        message = "User does not have permissions for this command"
    else:
        message = "Unknown OSError: {} - cmd".format(str(exc))
    raise dbt_common.exceptions.ExecutableError(cwd, cmd, message)


def _handle_posix_error(exc: OSError, cwd: str, cmd: List[str]) -> NoReturn:
    """OSError handling for POSIX systems.

    Some things that could happen to trigger an OSError:
        - cwd could not exist
            - exc.errno == ENOENT
            - exc.filename == cwd
        - cwd could have permissions that prevent the current user moving to it
            - exc.errno == EACCES
            - exc.filename == cwd
        - cwd could exist but not be a directory
            - exc.errno == ENOTDIR
            - exc.filename == cwd
        - cmd[0] could not exist
            - exc.errno == ENOENT
            - exc.filename == None(?)
        - cmd[0] could exist but have permissions that prevents the current
            user from executing it (executable bit not set for the user)
            - exc.errno == EACCES
            - exc.filename == None(?)
    """
    if getattr(exc, "filename", None) == cwd:
        _handle_posix_cwd_error(exc, cwd, cmd)
    else:
        _handle_posix_cmd_error(exc, cwd, cmd)


def _handle_windows_error(exc: OSError, cwd: str, cmd: List[str]) -> NoReturn:
    cls: Type[dbt_common.exceptions.DbtBaseException] = dbt_common.exceptions.base.CommandError
    if exc.errno == errno.ENOENT:
        message = (
            "Could not find command, ensure it is in the user's PATH "
            "and that the user has permissions to run it"
        )
        cls = dbt_common.exceptions.ExecutableError
    elif exc.errno == errno.ENOEXEC:
        message = "Command was not executable, ensure it is valid"
        cls = dbt_common.exceptions.ExecutableError
    elif exc.errno == errno.ENOTDIR:
        message = (
            "Unable to cd: path does not exist, user does not have"
            " permissions, or not a directory"
        )
        cls = dbt_common.exceptions.WorkingDirectoryError
    else:
        message = 'Unknown error: {} (errno={}: "{}")'.format(
            str(exc), exc.errno, errno.errorcode.get(exc.errno, "<Unknown!>")
        )
    raise cls(cwd, cmd, message)


def _interpret_oserror(exc: OSError, cwd: str, cmd: List[str]) -> NoReturn:
    """Interpret an OSError exception and raise the appropriate dbt exception."""
    if len(cmd) == 0:
        raise dbt_common.exceptions.base.CommandError(cwd, cmd)

    # all of these functions raise unconditionally
    if os.name == "nt":
        _handle_windows_error(exc, cwd, cmd)
    else:
        _handle_posix_error(exc, cwd, cmd)

    # this should not be reachable, raise _something_ at least!
    raise dbt_common.exceptions.DbtInternalError(
        "Unhandled exception in _interpret_oserror: {}".format(exc)
    )


def run_cmd(cwd: str, cmd: List[str], env: Optional[Dict[str, Any]] = None) -> Tuple[bytes, bytes]:
    fire_event(SystemExecutingCmd(cmd=cmd))
    if len(cmd) == 0:
        raise dbt_common.exceptions.base.CommandError(cwd, cmd)

    # the env argument replaces the environment entirely, which has exciting
    # consequences on Windows! Do an update instead.
    full_env = env
    if env is not None:
        full_env = os.environ.copy()
        full_env.update(env)

    try:
        exe_pth = shutil.which(cmd[0])
        if exe_pth:
            cmd = [os.path.abspath(exe_pth)] + list(cmd[1:])
        proc = subprocess.Popen(
            cmd, cwd=cwd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, env=full_env
        )

        out, err = proc.communicate()
    except OSError as exc:
        _interpret_oserror(exc, cwd, cmd)

    fire_event(SystemStdOut(bmsg=str(out)))
    fire_event(SystemStdErr(bmsg=str(err)))

    if proc.returncode != 0:
        fire_event(SystemReportReturnCode(returncode=proc.returncode))
        raise dbt_common.exceptions.CommandResultError(cwd, cmd, proc.returncode, out, err)

    return out, err


def download_with_retries(
    url: str, path: str, timeout: Optional[Union[float, tuple]] = None
) -> None:
    download_fn = functools.partial(download, url, path, timeout)
    connection_exception_retry(download_fn, 5)


def download(
    url: str,
    path: str,
    timeout: Optional[Union[float, Tuple[float, float], Tuple[float, None]]] = None,
) -> None:
    path = convert_path(path)
    connection_timeout = timeout or float(os.getenv("DBT_HTTP_TIMEOUT", 10))
    response = requests.get(url, timeout=connection_timeout)
    with open(path, "wb") as handle:
        for block in response.iter_content(1024 * 64):
            handle.write(block)


def rename(from_path: str, to_path: str, force: bool = False) -> None:
    from_path = convert_path(from_path)
    to_path = convert_path(to_path)
    is_symlink = path_is_symlink(to_path)

    if os.path.exists(to_path) and force:
        if is_symlink:
            remove_file(to_path)
        else:
            rmdir(to_path)

    shutil.move(from_path, to_path)


def safe_extract(tarball: tarfile.TarFile, path: str = ".") -> None:
    """
    Fix for CWE-22: Improper Limitation of a Pathname to a Restricted Directory ('Path Traversal')
    Solution copied from https://github.com/mindsdb/mindsdb/blob/main/mindsdb/utilities/fs.py
    """

    def _is_within_directory(directory, target):
        abs_directory = os.path.abspath(directory)
        abs_target = os.path.abspath(target)
        prefix = os.path.commonprefix([abs_directory, abs_target])
        return prefix == abs_directory

    # for py >= 3.12
    if hasattr(tarball, "data_filter"):
        tarball.extractall(path, filter="data")
    else:
        members = tarball.getmembers()
        for member in members:
            member_path = os.path.join(path, member.name)
            if not _is_within_directory(path, member_path):
                raise tarfile.OutsideDestinationError(member, path)

        tarball.extractall(path, members=members)


def untar_package(tar_path: str, dest_dir: str, rename_to: Optional[str] = None) -> None:
    tar_path = convert_path(tar_path)
    tar_dir_name = None
    with tarfile.open(tar_path, "r:gz") as tarball:
        safe_extract(tarball, dest_dir)
        tar_dir_name = os.path.commonprefix(tarball.getnames())
    if rename_to:
        downloaded_path = os.path.join(dest_dir, tar_dir_name)
        desired_path = os.path.join(dest_dir, rename_to)
        dbt_common.clients.system.rename(downloaded_path, desired_path, force=True)


def chmod_and_retry(func, path, exc_info):
    """Define an error handler to pass to shutil.rmtree.

    On Windows, when a file is marked read-only as git likes to do, rmtree will
    fail. To handle that, on errors try to make the file writable.
    We want to retry most operations here, but listdir is one that we know will
    be useless.
    """
    if func is os.listdir or os.name != "nt":
        raise
    os.chmod(path, stat.S_IREAD | stat.S_IWRITE)
    # on error,this will raise.
    func(path)


def _absnorm(path):
    return os.path.normcase(os.path.abspath(path))


def move(src, dst):
    """A re-implementation of shutil.move for windows fun.

    A re-implementation of shutil.move that properly removes the source
    directory on windows when it has read-only files in it and the move is
    between two drives.

    This is almost identical to the real shutil.move, except it, uses our rmtree
    and skips handling non-windows OSes since the existing one works ok there.
    """
    src = convert_path(src)
    dst = convert_path(dst)
    if os.name != "nt":
        return shutil.move(src, dst)

    if os.path.isdir(dst):
        if _absnorm(src) == _absnorm(dst):
            os.rename(src, dst)
            return

        dst = os.path.join(dst, os.path.basename(src.rstrip("/\\")))
        if os.path.exists(dst):
            raise EnvironmentError("Path '{}' already exists".format(dst))

    try:
        os.rename(src, dst)
    except OSError:
        # probably different drives
        if os.path.isdir(src):
            if _absnorm(dst + "\\").startswith(_absnorm(src + "\\")):
                # dst is inside src
                raise EnvironmentError(
                    "Cannot move a directory '{}' into itself '{}'".format(src, dst)
                )
            shutil.copytree(src, dst, symlinks=True)
            rmtree(src)
        else:
            shutil.copy2(src, dst)
            os.unlink(src)


def rmtree(path):
    """Recursively remove the path.

    On permissions errors on windows, try to remove the read-only flag and try again.
    """
    path = convert_path(path)
    return shutil.rmtree(path, onerror=chmod_and_retry)


@dataclasses.dataclass
class GetEnvParams:
    pass


@dataclasses.dataclass
class GetEnvResult:
    env: Dict[str, str]


@Recorder.register_record_type
class GetEnvRecord(Record):
    params_cls = GetEnvParams
    result_cls = GetEnvResult


@record_function(GetEnvRecord)
def get_env() -> Dict[str, str]:
    return dict(os.environ)
