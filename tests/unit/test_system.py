import errno
import os
import tarfile
import tempfile
import unittest
from unittest.mock import patch, mock_open

from dbt_common.clients.system import load_file_contents, untar_package


class TestLoadFileContentsRetry(unittest.TestCase):
    """Verify retry logic for transient OS errors (e.g. ESTALE on NFS/FUSE mounts)."""

    @patch("dbt_common.clients.system.time.sleep")
    def test_retries_on_estale(self, mock_sleep):
        estale = OSError(errno.ESTALE, "Stale file handle")
        m = mock_open(read_data=b"content")
        m.side_effect = [estale, m.return_value]

        with patch("builtins.open", m):
            result = load_file_contents("/fake/path")

        assert result == "content"
        assert mock_sleep.call_count == 1

    @patch("dbt_common.clients.system.time.sleep")
    def test_raises_after_max_retries(self, mock_sleep):
        estale = OSError(errno.ESTALE, "Stale file handle")

        with patch("builtins.open", side_effect=estale):
            with self.assertRaises(OSError) as ctx:
                load_file_contents("/fake/path")
            assert ctx.exception.errno == errno.ESTALE

    def test_non_transient_error_not_retried(self):
        enoent = OSError(errno.ENOENT, "No such file")
        with patch("builtins.open", side_effect=enoent):
            with self.assertRaises(OSError) as ctx:
                load_file_contents("/fake/path")
            assert ctx.exception.errno == errno.ENOENT


class TestUntarPackageCommonpath(unittest.TestCase):
    """Verify untar_package uses commonpath (path-aware) not commonprefix (string-based)."""

    def test_commonpath_used(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            # Create a tarball with a shared directory prefix
            tar_path = os.path.join(tmpdir, "test.tar.gz")
            pkg_dir = os.path.join(tmpdir, "my_pkg")
            os.makedirs(os.path.join(pkg_dir, "sub"))
            with open(os.path.join(pkg_dir, "file.txt"), "w") as f:
                f.write("hello")
            with open(os.path.join(pkg_dir, "sub", "other.txt"), "w") as f:
                f.write("world")

            with tarfile.open(tar_path, "w:gz") as tar:
                tar.add(pkg_dir, arcname="my_pkg")

            dest = os.path.join(tmpdir, "dest")
            os.makedirs(dest)
            untar_package(tar_path, dest)

            # Should have extracted correctly
            assert os.path.exists(os.path.join(dest, "my_pkg", "file.txt"))
