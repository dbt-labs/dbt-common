import gzip
import io
import itertools
import os
import shutil
import stat
import sys
import unittest
import tarfile
import types
import pathspec
import pytest
import requests
from pathlib import Path
from tempfile import mkdtemp, NamedTemporaryFile
from typing import Dict, Iterable, Iterator, Optional

from dbt_common.exceptions import (
    DbtRuntimeError,
    ExecutableError,
    PackageTooLargeError,
    WorkingDirectoryError,
)
import dbt_common.clients.system


class SystemClient(unittest.TestCase):
    def setUp(self) -> None:
        super().setUp()
        self.tmp_dir = mkdtemp()
        self.profiles_path = "{}/profiles.yml".format(self.tmp_dir)

    def set_up_profile(self) -> None:
        with open(self.profiles_path, "w") as f:
            f.write("ORIGINAL_TEXT")

    def get_profile_text(self) -> str:
        with open(self.profiles_path, "r") as f:
            return f.read()

    def tearDown(self) -> None:
        try:
            shutil.rmtree(self.tmp_dir)
        except Exception as e:  # noqa: F841
            pass

    def test__make_file_when_exists(self) -> None:
        self.set_up_profile()
        written = dbt_common.clients.system.make_file(self.profiles_path, contents="NEW_TEXT")

        self.assertFalse(written)
        self.assertEqual(self.get_profile_text(), "ORIGINAL_TEXT")

    def test__make_file_when_not_exists(self) -> None:
        written = dbt_common.clients.system.make_file(self.profiles_path, contents="NEW_TEXT")

        self.assertTrue(written)
        self.assertEqual(self.get_profile_text(), "NEW_TEXT")

    def test__make_file_with_overwrite(self) -> None:
        self.set_up_profile()
        written = dbt_common.clients.system.make_file(
            self.profiles_path, contents="NEW_TEXT", overwrite=True
        )

        self.assertTrue(written)
        self.assertEqual(self.get_profile_text(), "NEW_TEXT")

    def test__make_dir_from_str(self) -> None:
        test_dir_str = self.tmp_dir + "/test_make_from_str/sub_dir"
        dbt_common.clients.system.make_directory(test_dir_str)
        self.assertTrue(Path(test_dir_str).is_dir())

    def test__make_dir_from_pathobj(self) -> None:
        test_dir_pathobj = Path(self.tmp_dir + "/test_make_from_pathobj/sub_dir")
        dbt_common.clients.system.make_directory(test_dir_pathobj)
        self.assertTrue(test_dir_pathobj.is_dir())

    def test__rename_same_path(self) -> None:
        test_file_path = os.path.join(self.tmp_dir, "rename_test.txt")
        test_content = "test content"

        with open(test_file_path, "w") as f:
            f.write(test_content)

        dbt_common.clients.system.rename(test_file_path, test_file_path)

        self.assertTrue(os.path.exists(test_file_path))
        with open(test_file_path, "r") as f:
            self.assertEqual(f.read(), test_content)


class TestRunCmd(unittest.TestCase):
    """Test `run_cmd`.

    Don't mock out subprocess, in order to expose any OS-level differences.
    """

    not_a_file = "zzzbbfasdfasdfsdaq"

    def setUp(self) -> None:
        self.tempdir = mkdtemp()
        self.run_dir = os.path.join(self.tempdir, "run_dir")
        self.does_not_exist = os.path.join(self.tempdir, "does_not_exist")
        self.empty_file = os.path.join(self.tempdir, "empty_file")
        if os.name == "nt":
            self.exists_cmd = ["cmd", "/C", "echo", "hello"]
        else:
            self.exists_cmd = ["echo", "hello"]

        os.mkdir(self.run_dir)
        with open(self.empty_file, "w") as fp:  # noqa: F841
            pass  # "touch"

    def tearDown(self) -> None:
        shutil.rmtree(self.tempdir)

    def test__executable_does_not_exist(self) -> None:
        with self.assertRaises(ExecutableError) as exc:
            dbt_common.clients.system.run_cmd(self.run_dir, [self.does_not_exist])

        msg = str(exc.exception).lower()

        self.assertIn("path", msg)
        self.assertIn("could not find", msg)
        self.assertIn(self.does_not_exist.lower(), msg)

    def test__not_exe(self) -> None:
        with self.assertRaises(ExecutableError) as exc:
            dbt_common.clients.system.run_cmd(self.run_dir, [self.empty_file])

        msg = str(exc.exception).lower()
        if os.name == "nt":
            # on windows, this means it's not an executable at all!
            self.assertIn("not executable", msg)
        else:
            # on linux, this means you don't have executable permissions on it
            self.assertIn("permissions", msg)
        self.assertIn(self.empty_file.lower(), msg)

    def test__cwd_does_not_exist(self) -> None:
        with self.assertRaises(WorkingDirectoryError) as exc:
            dbt_common.clients.system.run_cmd(self.does_not_exist, self.exists_cmd)
        msg = str(exc.exception).lower()
        self.assertIn("does not exist", msg)
        self.assertIn(self.does_not_exist.lower(), msg)

    def test__cwd_not_directory(self) -> None:
        with self.assertRaises(WorkingDirectoryError) as exc:
            dbt_common.clients.system.run_cmd(self.empty_file, self.exists_cmd)

        msg = str(exc.exception).lower()
        self.assertIn("not a directory", msg)
        self.assertIn(self.empty_file.lower(), msg)

    def test__cwd_no_permissions(self) -> None:
        # it would be nice to add a windows test. Possible path to that is via
        # `psexec` (to get SYSTEM privs), use `icacls` to set permissions on
        # the directory for the test user. I'm pretty sure windows users can't
        # create files that they themselves cannot access.
        if os.name == "nt":
            return

        # read-only -> cannot cd to it
        os.chmod(self.run_dir, stat.S_IRUSR)

        with self.assertRaises(WorkingDirectoryError) as exc:
            dbt_common.clients.system.run_cmd(self.run_dir, self.exists_cmd)

        msg = str(exc.exception).lower()
        self.assertIn("permissions", msg)
        self.assertIn(self.run_dir.lower(), msg)

    def test__ok(self) -> None:
        out, err = dbt_common.clients.system.run_cmd(self.run_dir, self.exists_cmd)
        self.assertEqual(out.strip(), b"hello")
        self.assertEqual(err.strip(), b"")


class TestFindMatching(unittest.TestCase):
    def setUp(self) -> None:
        self.base_dir = mkdtemp()
        self.tempdir = mkdtemp(dir=self.base_dir)

    def test_find_matching_lowercase_file_pattern(self) -> None:
        with NamedTemporaryFile(prefix="sql-files", suffix=".sql", dir=self.tempdir) as named_file:
            file_path = os.path.dirname(named_file.name)
            relative_path = os.path.basename(file_path)
            out = dbt_common.clients.system.find_matching(
                self.base_dir,
                [relative_path],
                "*.sql",
            )
            expected_output = [
                {
                    "searched_path": relative_path,
                    "absolute_path": named_file.name,
                    "relative_path": os.path.basename(named_file.name),
                    "modification_time": out[0]["modification_time"],
                }
            ]
            self.assertEqual(out, expected_output)

    def test_find_matching_uppercase_file_pattern(self) -> None:
        with NamedTemporaryFile(prefix="sql-files", suffix=".SQL", dir=self.tempdir) as named_file:
            file_path = os.path.dirname(named_file.name)
            relative_path = os.path.basename(file_path)
            out = dbt_common.clients.system.find_matching(self.base_dir, [relative_path], "*.sql")
            expected_output = [
                {
                    "searched_path": relative_path,
                    "absolute_path": named_file.name,
                    "relative_path": os.path.basename(named_file.name),
                    "modification_time": out[0]["modification_time"],
                }
            ]
            self.assertEqual(out, expected_output)

    def test_find_matching_file_pattern_not_found(self) -> None:
        with NamedTemporaryFile(prefix="sql-files", suffix=".SQLT", dir=self.tempdir):
            out = dbt_common.clients.system.find_matching(self.tempdir, [""], "*.sql")
            self.assertEqual(out, [])

    def test_ignore_spec(self) -> None:
        with NamedTemporaryFile(prefix="sql-files", suffix=".sql", dir=self.tempdir):
            out = dbt_common.clients.system.find_matching(
                self.tempdir,
                [""],
                "*.sql",
                pathspec.PathSpec.from_lines(
                    pathspec.patterns.GitWildMatchPattern, "sql-files*".splitlines()
                ),
            )
            self.assertEqual(out, [])

    def tearDown(self) -> None:
        try:
            shutil.rmtree(self.base_dir)
        except Exception as e:  # noqa: F841
            pass


class TestUntarPackage(unittest.TestCase):
    def setUp(self) -> None:
        self.base_dir = mkdtemp()
        self.tempdir = mkdtemp(dir=self.base_dir)
        self.tempdest = mkdtemp(dir=self.base_dir)

    def tearDown(self) -> None:
        try:
            shutil.rmtree(self.base_dir)
        except Exception as e:  # noqa: F841
            pass

    def test_untar_package_success(self) -> None:
        #  set up a valid tarball to test against
        with NamedTemporaryFile(
            prefix="my-package.2", suffix=".tar.gz", dir=self.tempdir, delete=False
        ) as named_tar_file:
            tar_file_full_path = named_tar_file.name
            with NamedTemporaryFile(prefix="a", suffix=".txt", dir=self.tempdir) as file_a:
                file_a.write(b"some text in the text file")
                relative_file_a = os.path.basename(file_a.name)
                with tarfile.open(fileobj=named_tar_file, mode="w:gz") as tar:
                    tar.addfile(tarfile.TarInfo(relative_file_a), open(file_a.name))

        #  now we test can test that we can untar the file successfully
        assert tarfile.is_tarfile(tar.name)
        dbt_common.clients.system.untar_package(tar_file_full_path, self.tempdest)
        path = Path(os.path.join(self.tempdest, relative_file_a))
        assert path.is_file()

    def test_untar_package_failure(self) -> None:
        #  create a text file then rename it as a tar (so it's invalid)
        with NamedTemporaryFile(
            prefix="a", suffix=".txt", dir=self.tempdir, delete=False
        ) as file_a:
            file_a.write(b"some text in the text file")
            txt_file_name = file_a.name
            file_path = os.path.dirname(txt_file_name)
            tar_file_path = os.path.join(file_path, "mypackage.2.tar.gz")
        os.rename(txt_file_name, tar_file_path)

        #  now that we're set up, test that untarring the file fails
        with self.assertRaises(tarfile.ReadError) as exc:  # noqa: F841
            dbt_common.clients.system.untar_package(tar_file_path, self.tempdest)

    def test_untar_package_empty(self) -> None:
        #  create a tarball with nothing in it
        with NamedTemporaryFile(
            prefix="my-empty-package.2", suffix=".tar.gz", dir=self.tempdir
        ) as named_file:
            #  make sure we throw an error for the empty file
            with self.assertRaises(tarfile.ReadError) as exc:
                dbt_common.clients.system.untar_package(named_file.name, self.tempdest)
            self.assertEqual("empty file", str(exc.exception))

    def test_untar_package_outside_directory(self) -> None:
        with NamedTemporaryFile(
            prefix="my-package.2", suffix=".tar.gz", dir=self.tempdir, delete=False
        ) as named_tar_file:
            tar_file_full_path = named_tar_file.name
            with NamedTemporaryFile(prefix="a", suffix=".txt", dir=self.tempdir) as file_a:
                file_a.write(b"some text in the text file")
                relative_file_a = "/../" + os.path.basename(file_a.name)
                with tarfile.open(fileobj=named_tar_file, mode="w:gz") as tar:
                    tar.addfile(tarfile.TarInfo(relative_file_a), open(file_a.name))

        assert tarfile.is_tarfile(tar.name)
        with self.assertRaises(tarfile.OutsideDestinationError):
            dbt_common.clients.system.untar_package(tar_file_full_path, self.tempdest)

    def test_untar_package_sibling_path_traversal(self) -> None:
        # A malicious tarball with a path that is a string prefix of the destination
        # but not actually within it (e.g., "dest" vs "destevil")
        with NamedTemporaryFile(
            prefix="my-package.2", suffix=".tar.gz", dir=self.tempdir, delete=False
        ) as named_tar_file:
            tar_file_full_path = named_tar_file.name
            with NamedTemporaryFile(prefix="a", suffix=".txt", dir=self.tempdir) as file_a:
                file_a.write(b"malicious content")
                # Create path that escapes to a sibling directory with matching prefix
                # e.g., extracting to "/tmp/dest" but writing to "/tmp/destevil/file.txt"
                sibling_path = "../" + os.path.basename(self.tempdest) + "evil/malicious.txt"
                with tarfile.open(fileobj=named_tar_file, mode="w:gz") as tar:
                    tar.addfile(tarfile.TarInfo(sibling_path), open(file_a.name))

        assert tarfile.is_tarfile(tar.name)
        with self.assertRaises(tarfile.OutsideDestinationError):
            dbt_common.clients.system.untar_package(tar_file_full_path, self.tempdest)


@pytest.mark.skipif(
    sys.version_info < (3, 12), reason="Tests Python 3.12+ tarfile filter='data' path"
)
def test_safe_extract_py312_path(tmp_path) -> None:
    """Test that Python 3.12+ uses filter='data' for extraction."""
    import warnings

    tar_file_path = tmp_path / "test.tar.gz"
    content_file = tmp_path / "content.txt"
    content_file.write_bytes(b"test content")

    with tarfile.open(tar_file_path, "w:gz") as tar:
        tar.add(content_file, arcname="content.txt")

    dest_dir = tmp_path / "dest"
    dest_dir.mkdir()

    # On Python 3.12+, safe_extract should use filter="data" and not emit
    # a DeprecationWarning about the filter argument
    with warnings.catch_warnings():
        warnings.simplefilter("error", DeprecationWarning)
        with tarfile.open(tar_file_path, "r:gz") as tarball:
            dbt_common.clients.system.safe_extract(tarball, str(dest_dir))

    # Verify extraction worked
    assert (dest_dir / "content.txt").exists()


@pytest.mark.skipif(
    sys.version_info >= (3, 12), reason="Tests Python <3.12 manual validation path"
)
def test_safe_extract_pre_py312_path(tmp_path) -> None:
    """Test that Python <3.12 uses manual member validation."""
    tar_file_path = tmp_path / "test.tar.gz"
    content_file = tmp_path / "content.txt"
    content_file.write_bytes(b"test content")

    with tarfile.open(tar_file_path, "w:gz") as tar:
        tar.add(content_file, arcname="content.txt")

    dest_dir = tmp_path / "dest"
    dest_dir.mkdir()

    with tarfile.open(tar_file_path, "r:gz") as tarball:
        dbt_common.clients.system.safe_extract(tarball, str(dest_dir))

    # Verify extraction worked
    assert (dest_dir / "content.txt").exists()


# --- Package archive limits -------------------------------------------------------------


def _make_tar_gz(path: Path, files: Dict[str, bytes]) -> Path:
    with tarfile.open(path, "w:gz") as tar:
        for name, data in files.items():
            info = tarfile.TarInfo(name)
            info.size = len(data)
            tar.addfile(info, io.BytesIO(data))
    return path


@pytest.fixture(params=["data_filter", "fallback"])
def extract_branch(request, monkeypatch) -> str:
    """Run a test against both branches of safe_extract.

    The fallback branch is forced by hiding `data_filter` from the `tarfile` module that
    system.py sees, rather than deleting it from the real module: on Python 3.14+
    tarfile's own extractall looks up `data_filter` as its default filter.
    """
    if request.param == "fallback":
        proxy = types.SimpleNamespace(
            **{name: getattr(tarfile, name) for name in dir(tarfile) if name != "data_filter"}
        )
        monkeypatch.setattr(dbt_common.clients.system, "tarfile", proxy)
    return request.param


@pytest.fixture
def dest(tmp_path) -> Path:
    dest_dir = tmp_path / "dest"
    dest_dir.mkdir()
    return dest_dir


def _extract(tar_path: Path, dest_dir: Path) -> None:
    with tarfile.open(tar_path, "r:gz") as tarball:
        dbt_common.clients.system.safe_extract(tarball, str(dest_dir))


def test_safe_extract_within_limits_extracts_everything(tmp_path, dest, extract_branch) -> None:
    files = {f"pkg/models/model_{i}.sql": f"select {i}".encode() for i in range(50)}
    files["pkg/seeds/big.csv"] = b"a,b\n" * 10_000
    tar_path = _make_tar_gz(tmp_path / "pkg.tar.gz", files)

    _extract(tar_path, dest)

    extracted = {
        p.relative_to(dest).as_posix(): p.read_bytes() for p in dest.rglob("*") if p.is_file()
    }
    assert extracted == files


def test_safe_extract_limits_checked_before_extractall_keeps_all_members(tmp_path) -> None:
    # _check_tar_limits iterates the archive; extractall must still see every member.
    files = {f"f{i}.txt": b"x" for i in range(20)}
    tar_path = _make_tar_gz(tmp_path / "pkg.tar.gz", files)
    with tarfile.open(tar_path, "r:gz") as tarball:
        dbt_common.clients.system._check_tar_limits(tarball)
        assert tarball.getnames() == list(files)


def test_safe_extract_too_many_members(tmp_path, dest, extract_branch, monkeypatch) -> None:
    monkeypatch.setenv("DBT_PACKAGE_MAX_FILES", "3")
    tar_path = _make_tar_gz(tmp_path / "pkg.tar.gz", {f"f{i}.txt": b"x" for i in range(5)})

    with pytest.raises(PackageTooLargeError, match="DBT_PACKAGE_MAX_FILES") as exc:
        _extract(tar_path, dest)

    assert exc.value.limit == 3
    assert exc.value.observed == 4  # stops at the first member over the limit
    assert list(dest.iterdir()) == []


def test_safe_extract_total_size_too_large(tmp_path, dest, extract_branch, monkeypatch) -> None:
    monkeypatch.setenv("DBT_PACKAGE_MAX_UNCOMPRESSED_BYTES", "100")
    files = {"a.txt": b"a" * 40, "b.txt": b"b" * 40, "c.txt": b"c" * 40}
    tar_path = _make_tar_gz(tmp_path / "pkg.tar.gz", files)

    with pytest.raises(PackageTooLargeError, match="DBT_PACKAGE_MAX_UNCOMPRESSED_BYTES") as exc:
        _extract(tar_path, dest)

    assert exc.value.observed == 120
    assert exc.value.limit == 100
    assert list(dest.iterdir()) == []


def test_safe_extract_declared_huge_member_rejected_before_any_write(
    tmp_path, dest, extract_branch
) -> None:
    # A header that declares a 2 GiB member, followed by only a few bytes of data.
    # With the default 1 GiB limit this must be rejected from the header alone.
    info = tarfile.TarInfo("pkg/huge.csv")
    info.size = 2 * 1024**3
    tar_path = tmp_path / "pkg.tar.gz"
    with gzip.open(tar_path, "wb") as gz:
        gz.write(info.tobuf(format=tarfile.GNU_FORMAT) + b"x" * 1024)
    assert tar_path.stat().st_size < 4096

    with pytest.raises(PackageTooLargeError) as exc:
        _extract(tar_path, dest)

    assert exc.value.observed == 2 * 1024**3
    assert exc.value.limit == dbt_common.clients.system.DEFAULT_PACKAGE_MAX_UNCOMPRESSED_BYTES
    assert list(dest.iterdir()) == []


def test_safe_extract_counts_link_targets(tmp_path, dest, extract_branch, monkeypatch) -> None:
    # If links can't be created, tarfile extracts a copy of the target instead, so a
    # link counts as its target's size. Include a chain and a link to a later member.
    monkeypatch.setenv("DBT_PACKAGE_MAX_UNCOMPRESSED_BYTES", "200")
    tar_path = tmp_path / "pkg.tar.gz"
    with tarfile.open(tar_path, "w:gz") as tar:

        def link(name: str, target: str, type: bytes) -> None:
            info = tarfile.TarInfo(name)
            info.type = type
            info.linkname = target
            tar.addfile(info)

        link("pkg/early.csv", "data.csv", tarfile.SYMTYPE)  # target appears later
        data = tarfile.TarInfo("pkg/data.csv")
        data.size = 60
        tar.addfile(data, io.BytesIO(b"d" * 60))
        link("pkg/hard.csv", "pkg/data.csv", tarfile.LNKTYPE)
        link("pkg/chain.csv", "hard.csv", tarfile.SYMTYPE)

    with pytest.raises(PackageTooLargeError) as exc:
        _extract(tar_path, dest)

    assert exc.value.observed == 240
    assert list(dest.iterdir()) == []


def test_check_tar_limits_link_cycle_terminates(tmp_path) -> None:
    tar_path = tmp_path / "pkg.tar.gz"
    with tarfile.open(tar_path, "w:gz") as tar:
        for name, target in [("a", "b"), ("b", "c"), ("c", "a"), ("d", "a")]:
            info = tarfile.TarInfo(name)
            info.type = tarfile.SYMTYPE
            info.linkname = target
            tar.addfile(info)
    with tarfile.open(tar_path, "r:gz") as tarball:
        dbt_common.clients.system._check_tar_limits(tarball)


@pytest.mark.parametrize("value", ["abc", "0", "-5", "1.5", "1e9"])
def test_package_limit_invalid_env_var(tmp_path, dest, monkeypatch, value) -> None:
    monkeypatch.setenv("DBT_PACKAGE_MAX_FILES", value)
    tar_path = _make_tar_gz(tmp_path / "pkg.tar.gz", {"a.txt": b"a"})

    with pytest.raises(DbtRuntimeError, match="DBT_PACKAGE_MAX_FILES") as exc:
        _extract(tar_path, dest)

    assert not isinstance(exc.value, PackageTooLargeError)
    assert list(dest.iterdir()) == []


def test_package_limit_empty_env_var_uses_default(monkeypatch) -> None:
    monkeypatch.setenv("DBT_PACKAGE_MAX_FILES", "")
    assert dbt_common.clients.system._get_package_limit("DBT_PACKAGE_MAX_FILES", 7) == 7


def test_package_too_large_error_message() -> None:
    err = PackageTooLargeError("entry count", 100_001, 100_000, "DBT_PACKAGE_MAX_FILES")
    assert isinstance(err, DbtRuntimeError)
    assert "entry count" in str(err)
    assert "100,001" in str(err)
    assert "100,000" in str(err)
    assert "DBT_PACKAGE_MAX_FILES" in str(err)


class _FakeStreamResponse:
    """Stands in for a streamed requests.Response."""

    def __init__(self, chunks: Iterable[bytes], headers: Optional[Dict[str, str]] = None):
        self._chunks = chunks
        self.headers = headers or {}
        self.chunks_read = 0
        self.closed = False

    def iter_content(self, chunk_size: int) -> Iterator[bytes]:
        for chunk in self._chunks:
            self.chunks_read += 1
            yield chunk

    def close(self) -> None:
        self.closed = True


@pytest.fixture
def fake_get(mocker):
    def _install(response: _FakeStreamResponse):
        return mocker.patch.object(
            dbt_common.clients.system.requests, "get", return_value=response
        )

    return _install


def test_download_writes_body(tmp_path, fake_get) -> None:
    body = [b"a" * 1000, b"b" * 1000, b"c" * 10]
    response = _FakeStreamResponse(body, {"Content-Length": "2010"})
    get = fake_get(response)
    path = tmp_path / "pkg.tar.gz"

    dbt_common.clients.system.download("https://example.com/pkg.tar.gz", str(path))

    assert path.read_bytes() == b"".join(body)
    assert get.call_args.kwargs["stream"] is True
    assert response.closed


def test_download_rejects_large_content_length(tmp_path, fake_get, monkeypatch) -> None:
    monkeypatch.setenv("DBT_PACKAGE_MAX_DOWNLOAD_BYTES", "100")
    response = _FakeStreamResponse([b"x" * 1000], {"Content-Length": "1000"})
    fake_get(response)
    path = tmp_path / "pkg.tar.gz"

    with pytest.raises(PackageTooLargeError, match="DBT_PACKAGE_MAX_DOWNLOAD_BYTES") as exc:
        dbt_common.clients.system.download("https://example.com/pkg.tar.gz", str(path))

    assert exc.value.observed == 1000
    assert response.chunks_read == 0  # rejected before reading the body
    assert not path.exists()
    assert response.closed


@pytest.mark.parametrize("headers", [{}, {"Content-Length": "10"}], ids=["no-length", "lying"])
def test_download_rejects_body_growing_past_limit(
    tmp_path, fake_get, monkeypatch, headers
) -> None:
    monkeypatch.setenv("DBT_PACKAGE_MAX_DOWNLOAD_BYTES", "100")
    # An endless body: the download must stop on its own once it passes the limit.
    response = _FakeStreamResponse(itertools.repeat(b"x" * 64), headers)
    fake_get(response)
    path = tmp_path / "pkg.tar.gz"

    with pytest.raises(PackageTooLargeError) as exc:
        dbt_common.clients.system.download("https://example.com/pkg.tar.gz", str(path))

    assert exc.value.observed == 128
    assert response.chunks_read == 2
    assert not path.exists()  # partial file removed
    assert response.closed


def test_download_removes_partial_file_on_transfer_error(tmp_path, fake_get) -> None:
    def chunks() -> Iterator[bytes]:
        yield b"x" * 64
        raise requests.exceptions.ChunkedEncodingError("connection broken")

    response = _FakeStreamResponse(chunks())
    fake_get(response)
    path = tmp_path / "pkg.tar.gz"

    with pytest.raises(requests.exceptions.ChunkedEncodingError):
        dbt_common.clients.system.download("https://example.com/pkg.tar.gz", str(path))

    assert not path.exists()
    assert response.closed


def test_download_invalid_limit_env_var(tmp_path, fake_get, monkeypatch) -> None:
    monkeypatch.setenv("DBT_PACKAGE_MAX_DOWNLOAD_BYTES", "1GB")
    get = fake_get(_FakeStreamResponse([b"x"]))

    with pytest.raises(DbtRuntimeError, match="DBT_PACKAGE_MAX_DOWNLOAD_BYTES"):
        dbt_common.clients.system.download("https://example.com/pkg.tar.gz", str(tmp_path / "p"))

    get.assert_not_called()


def test_download_with_retries_does_not_retry_too_large(
    tmp_path, fake_get, monkeypatch, mocker
) -> None:
    monkeypatch.setenv("DBT_PACKAGE_MAX_DOWNLOAD_BYTES", "100")
    sleep = mocker.patch("dbt_common.utils.connection.time.sleep")
    get = fake_get(_FakeStreamResponse([b"x" * 1000], {"Content-Length": "1000"}))

    with pytest.raises(PackageTooLargeError):
        dbt_common.clients.system.download_with_retries(
            "https://example.com/pkg.tar.gz", str(tmp_path / "pkg.tar.gz")
        )

    assert get.call_count == 1
    sleep.assert_not_called()


def _write_raw_tar_gz(path: Path, *blocks: bytes) -> Path:
    """Write header blocks (and a little trailing data) without tarfile validating sizes."""
    with gzip.open(path, "wb") as gz:
        for block in blocks:
            gz.write(block)
        gz.write(b"\0" * 1024)
    return path


@pytest.mark.parametrize("header_type", [tarfile.GNUTYPE_LONGNAME, tarfile.XHDTYPE])
def test_untar_package_rejects_huge_extended_header(
    tmp_path, dest, header_type, monkeypatch
) -> None:
    # A long-name / PAX header that declares 2 GiB. tarfile reads extended headers into
    # memory while opening the archive, before any member reaches _check_tar_limits.
    # 100 entries gives a header budget of ~1.1 MiB, so a 2 MiB payload is enough to show
    # the read is cut off at the budget rather than read whole.
    monkeypatch.setenv("DBT_PACKAGE_MAX_FILES", "100")
    header = tarfile.TarInfo("././@LongLink")
    header.type = header_type
    header.size = 2 * 1024**3
    tar_path = _write_raw_tar_gz(
        tmp_path / "pkg.tar.gz", header.tobuf(format=tarfile.GNU_FORMAT), b"x" * (2 * 1024**2)
    )

    with pytest.raises(PackageTooLargeError, match="tar header data") as exc:
        dbt_common.clients.system.untar_package(str(tar_path), str(dest))

    system = dbt_common.clients.system
    assert exc.value.limit == (
        100 * system.PACKAGE_HEADER_BYTES_PER_ENTRY + system.PACKAGE_HEADER_BYTES_ALLOWANCE
    )
    assert exc.value.observed == exc.value.limit + 1  # never read past the budget
    assert list(dest.iterdir()) == []


def _long_name_archive(path: Path, count: int, fmt: int) -> Dict[str, bytes]:
    files = {f"pkg/{'d' * 150}/{'é' * 20}_{i}.sql": f"select {i}".encode() for i in range(count)}
    with tarfile.open(path, "w:gz", format=fmt) as tar:
        for name, data in files.items():
            info = tarfile.TarInfo(name)
            info.size = len(data)
            tar.addfile(info, io.BytesIO(data))
    return files


@pytest.mark.parametrize("fmt", [tarfile.GNU_FORMAT, tarfile.PAX_FORMAT], ids=["gnu", "pax"])
def test_untar_package_long_names_extract(tmp_path, dest, fmt) -> None:
    # Long and non-ASCII paths need extended headers; ordinary ones must still work.
    files = _long_name_archive(tmp_path / "pkg.tar.gz", 20, fmt)

    dbt_common.clients.system.untar_package(str(tmp_path / "pkg.tar.gz"), str(dest))

    extracted = {
        p.relative_to(dest).as_posix(): p.read_bytes() for p in dest.rglob("*") if p.is_file()
    }
    assert extracted == files


@pytest.mark.parametrize("fmt", [tarfile.GNU_FORMAT, tarfile.PAX_FORMAT], ids=["gnu", "pax"])
def test_untar_package_header_budget_fits_long_path_at_every_entry(
    tmp_path, dest, fmt, monkeypatch
) -> None:
    # An archive at the entry limit where every path needs an extended header must fit
    # in the default per-entry header budget (with no fixed allowance to lean on).
    monkeypatch.setenv("DBT_PACKAGE_MAX_FILES", "10")
    monkeypatch.setattr(dbt_common.clients.system, "PACKAGE_HEADER_BYTES_ALLOWANCE", 0)
    files = _long_name_archive(tmp_path / "pkg.tar.gz", 10, fmt)

    dbt_common.clients.system.untar_package(str(tmp_path / "pkg.tar.gz"), str(dest))

    assert len([p for p in dest.rglob("*") if p.is_file()]) == len(files)


@pytest.fixture
def tight_header_budget(monkeypatch) -> None:
    """Allow 10 entries and 1 KiB of header data per entry, with no fixed allowance."""
    monkeypatch.setenv("DBT_PACKAGE_MAX_FILES", "10")
    monkeypatch.setattr(dbt_common.clients.system, "PACKAGE_HEADER_BYTES_ALLOWANCE", 0)
    monkeypatch.setattr(dbt_common.clients.system, "PACKAGE_HEADER_BYTES_PER_ENTRY", 1024)


@pytest.mark.parametrize("fmt", [tarfile.GNU_FORMAT, tarfile.PAX_FORMAT], ids=["gnu", "pax"])
def test_untar_package_header_budget_counts_all_headers(
    tmp_path, dest, fmt, tight_header_budget
) -> None:
    # 10 entries is within the entry limit, but each needs ~1.5 KiB of headers.
    tar_path = tmp_path / "pkg.tar.gz"
    _long_name_archive(tar_path, 10, fmt)

    with pytest.raises(PackageTooLargeError, match="DBT_PACKAGE_MAX_FILES") as exc:
        dbt_common.clients.system.untar_package(str(tar_path), str(dest))

    assert exc.value.limit == 10 * 1024
    assert list(dest.iterdir()) == []


def test_untar_package_header_budget_ignores_member_data(
    tmp_path, dest, tight_header_budget
) -> None:
    # The budget covers headers only: member data far larger than it still extracts.
    files = {"pkg/seeds/big.csv": os.urandom(3 * 1024**2), "pkg/a.sql": b"select 1"}
    tar_path = _make_tar_gz(tmp_path / "pkg.tar.gz", files)

    dbt_common.clients.system.untar_package(str(tar_path), str(dest))

    assert (dest / "pkg/seeds/big.csv").read_bytes() == files["pkg/seeds/big.csv"]
    assert (dest / "pkg/a.sql").read_bytes() == b"select 1"


def test_read_budget() -> None:
    reader = dbt_common.clients.system._ReadBudget(io.BytesIO(b"x" * 10), 10)
    assert reader.read(4) == b"xxxx"
    assert reader.read(100) == b"x" * 6  # a short read at EOF is fine
    assert reader.read() == b""

    reader = dbt_common.clients.system._ReadBudget(io.BytesIO(b"x" * 100), 10)
    reader.seek(50)  # seeking does not count
    with pytest.raises(PackageTooLargeError) as exc:
        reader.read(1000)
    assert exc.value.observed == 11  # asked the file for at most one byte past the budget

    reader = dbt_common.clients.system._ReadBudget(io.BytesIO(b"x" * 100), 10)
    reader.limit = None
    assert reader.read() == b"x" * 100


def test_download_ignores_malformed_content_length(tmp_path, fake_get) -> None:
    fake_get(_FakeStreamResponse([b"abc"], {"Content-Length": "not-a-number"}))
    path = tmp_path / "pkg.tar.gz"

    dbt_common.clients.system.download("https://example.com/pkg.tar.gz", str(path))

    assert path.read_bytes() == b"abc"


@pytest.mark.skipif(
    sys.platform == "win32" or (hasattr(os, "geteuid") and os.geteuid() == 0),
    reason="needs POSIX permissions that apply to the current user",
)
def test_download_does_not_delete_existing_file_it_cannot_open(tmp_path, fake_get) -> None:
    path = tmp_path / "pkg.tar.gz"
    path.write_bytes(b"keep me")
    path.chmod(stat.S_IRUSR)
    fake_get(_FakeStreamResponse([b"new"]))

    try:
        with pytest.raises(PermissionError):
            dbt_common.clients.system.download("https://example.com/pkg.tar.gz", str(path))
        assert path.read_bytes() == b"keep me"
    finally:
        path.chmod(stat.S_IRUSR | stat.S_IWUSR)
