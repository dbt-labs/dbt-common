from typing import List, Union, Any

from dbt_common.exceptions import (
    CompilationError,
    CommandError,
    DbtRuntimeError,
    scrub_secrets,
    env_secrets,
)


class SymbolicLinkError(CompilationError):
    def __init__(self) -> None:
        super().__init__(msg=self.get_message())

    def get_message(self) -> str:
        msg = (
            "dbt encountered an error when attempting to create a symbolic link. "
            "If this error persists, please create an issue at: \n\n"
            "https://github.com/dbt-labs/dbt-core"
        )

        return msg


class ExecutableError(CommandError):
    def __init__(self, cwd: str, cmd: List[str], msg: str) -> None:
        super().__init__(cwd, cmd, msg)


class WorkingDirectoryError(CommandError):
    def __init__(self, cwd: str, cmd: List[str], msg: str) -> None:
        super().__init__(cwd, cmd, msg)

    def __str__(self, prefix: str = "! ") -> str:
        return f'{self.msg}: "{self.cwd}"'


class CommandResultError(CommandError):
    def __init__(
        self,
        cwd: str,
        cmd: List[str],
        returncode: Union[int, Any],
        stdout: bytes,
        stderr: bytes,
        msg: str = "Got a non-zero returncode",
    ) -> None:
        super().__init__(cwd, cmd, msg)
        self.returncode = returncode
        self.stdout = scrub_secrets(stdout.decode("utf-8"), env_secrets())
        self.stderr = scrub_secrets(stderr.decode("utf-8"), env_secrets())
        self.args = (cwd, self.cmd, returncode, self.stdout, self.stderr, msg)

    def __str__(self, prefix: str = "! ") -> str:
        return f"{self.msg} running: {self.cmd}"


class PackageTooLargeError(DbtRuntimeError):
    """A package archive exceeded a configured download or extraction limit.

    This deliberately subclasses DbtRuntimeError only, and not any of the exception
    types that `connection_exception_retry` retries on (requests exceptions,
    tarfile.ReadError, EOFError, gzip.BadGzipFile): re-downloading an archive that
    is too large will not make it smaller.
    """

    def __init__(self, what: str, observed: int, limit: int, env_var: str) -> None:
        self.what = what
        self.observed = observed
        self.limit = limit
        self.env_var = env_var
        super().__init__(
            f"Package archive {what} ({observed:,}) exceeds the limit of {limit:,}. "
            f"To raise the limit, set the {env_var} environment variable."
        )
