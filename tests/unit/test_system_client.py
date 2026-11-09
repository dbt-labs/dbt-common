import gzip
import io
import os
import shutil
import stat
import sys
import unittest
import tarfile
import types
import pathspec
import pytest
from pathlib import Path
from tempfile import mkdtemp, NamedTemporaryFile
from typing import Dict

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
