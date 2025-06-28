"""Tests for clipboard utilities."""

import os
import subprocess
import sys
import tempfile
import threading
import time
from unittest import mock

import pytest

from DockTUI.utils.clipboard import copy_to_clipboard_async, copy_to_clipboard_sync


class TestCopyToClipboardSync:
    """Tests for copy_to_clipboard_sync function."""

    def test_pyperclip_success_not_in_container(self):
        """Test successful copy using pyperclip when not in container."""
        with mock.patch.dict(os.environ, {}, clear=True):
            mock_pyperclip = mock.Mock()
            mock_pyperclip.copy.return_value = None
            with mock.patch.dict("sys.modules", {"pyperclip": mock_pyperclip}):
                result = copy_to_clipboard_sync("test text")

                assert result is True
                mock_pyperclip.copy.assert_called_once_with("test text")

    def test_pyperclip_fallback_to_xclip(self):
        """Test fallback to xclip when pyperclip fails."""
        with mock.patch.dict(os.environ, {}, clear=True):
            mock_pyperclip = mock.Mock()
            mock_pyperclip.copy.side_effect = Exception("pyperclip failed")
            with mock.patch.dict("sys.modules", {"pyperclip": mock_pyperclip}):
                with mock.patch("subprocess.Popen") as mock_popen:
                    mock_process = mock.Mock()
                    mock_process.communicate.return_value = ("", "")
                    mock_process.returncode = 0
                    mock_popen.return_value = mock_process

                    result = copy_to_clipboard_sync("test text")

                    assert result is True
                    mock_popen.assert_called_once()
                    args = mock_popen.call_args[0][0]
                    assert args == ["xclip", "-selection", "clipboard"]

    def test_xclip_timeout(self):
        """Test xclip timeout handling."""
        with mock.patch.dict(os.environ, {"DOCKTUI_IN_CONTAINER": "true"}):
            with mock.patch("subprocess.Popen") as mock_popen:
                mock_process = mock.Mock()
                mock_process.communicate.side_effect = subprocess.TimeoutExpired(
                    "xclip", 1.0
                )
                mock_popen.return_value = mock_process

                result = copy_to_clipboard_sync("test text")

                assert result is False

    def test_xclip_not_found(self):
        """Test xclip not found handling."""
        with mock.patch.dict(os.environ, {"DOCKTUI_IN_CONTAINER": "true"}):
            with mock.patch(
                "subprocess.Popen", side_effect=FileNotFoundError("xclip not found")
            ):
                result = copy_to_clipboard_sync("test text")

                assert result is False

    def test_clipboard_file_success(self):
        """Test successful copy using clipboard file."""
        with tempfile.NamedTemporaryFile(mode="w", delete=False) as tmp:
            tmp_path = tmp.name

        try:
            with mock.patch.dict(
                os.environ,
                {
                    "DOCKTUI_IN_CONTAINER": "true",
                    "DOCKTUI_CLIPBOARD_FILE": tmp_path,
                },
            ):
                with mock.patch(
                    "subprocess.Popen", side_effect=FileNotFoundError("xclip not found")
                ):
                    result = copy_to_clipboard_sync("test clipboard text")

                    assert result is True

                    # Verify content was written
                    with open(tmp_path, "r") as f:
                        assert f.read() == "test clipboard text"
        finally:
            os.unlink(tmp_path)

    def test_clipboard_file_write_error(self):
        """Test clipboard file write error handling."""
        with mock.patch.dict(
            os.environ,
            {
                "DOCKTUI_IN_CONTAINER": "true",
                "DOCKTUI_CLIPBOARD_FILE": "/invalid/path/clipboard.txt",
            },
        ):
            with mock.patch(
                "subprocess.Popen", side_effect=FileNotFoundError("xclip not found")
            ):
                result = copy_to_clipboard_sync("test text")

                assert result is False

    def test_all_methods_fail(self):
        """Test when all clipboard methods fail."""
        with mock.patch.dict(os.environ, {"DOCKTUI_IN_CONTAINER": "true"}):
            with mock.patch(
                "subprocess.Popen", side_effect=Exception("Subprocess failed")
            ):
                result = copy_to_clipboard_sync("test text")

                assert result is False

    @pytest.mark.parametrize(
        "container_value",
        ["1", "true", "True", "TRUE", "yes", "Yes", "YES"],
    )
    def test_container_detection(self, container_value):
        """Test container environment detection with various values."""
        with mock.patch.dict(
            os.environ, {"DOCKTUI_IN_CONTAINER": container_value}, clear=True
        ):
            # Should skip pyperclip when in container
            with mock.patch("subprocess.Popen") as mock_popen:
                mock_process = mock.Mock()
                mock_process.communicate.return_value = ("", "")
                mock_process.returncode = 0
                mock_popen.return_value = mock_process

                # pyperclip shouldn't even be imported in container mode
                result = copy_to_clipboard_sync("test")

                # xclip should be called instead
                mock_popen.assert_called_once()


class TestCopyToClipboardAsync:
    """Tests for copy_to_clipboard_async function."""

    def test_async_copy_success_with_callback(self):
        """Test async copy with successful callback."""
        callback_result = {"called": False, "success": None}

        def test_callback(success):
            callback_result["called"] = True
            callback_result["success"] = success

        with mock.patch(
            "DockTUI.utils.clipboard.copy_to_clipboard_sync", return_value=True
        ):
            copy_to_clipboard_async("test text", callback=test_callback)

            # Wait for thread to complete
            time.sleep(0.1)

            assert callback_result["called"] is True
            assert callback_result["success"] is True

    def test_async_copy_failure_with_callback(self):
        """Test async copy with failed callback."""
        callback_result = {"called": False, "success": None}

        def test_callback(success):
            callback_result["called"] = True
            callback_result["success"] = success

        with mock.patch(
            "DockTUI.utils.clipboard.copy_to_clipboard_sync", return_value=False
        ):
            copy_to_clipboard_async("test text", callback=test_callback)

            # Wait for thread to complete
            time.sleep(0.1)

            assert callback_result["called"] is True
            assert callback_result["success"] is False

    def test_async_copy_without_callback(self):
        """Test async copy without callback doesn't raise errors."""
        with mock.patch(
            "DockTUI.utils.clipboard.copy_to_clipboard_sync", return_value=True
        ) as mock_sync:
            copy_to_clipboard_async("test text")

            # Wait for thread to complete
            time.sleep(0.1)

            mock_sync.assert_called_once_with("test text")

    def test_async_copy_thread_is_daemon(self):
        """Test that async copy creates a daemon thread."""
        original_thread_init = threading.Thread.__init__
        thread_kwargs = {}

        def capture_thread_init(self, **kwargs):
            thread_kwargs.update(kwargs)
            original_thread_init(self, **kwargs)

        with mock.patch.object(threading.Thread, "__init__", capture_thread_init):
            with mock.patch(
                "DockTUI.utils.clipboard.copy_to_clipboard_sync", return_value=True
            ):
                copy_to_clipboard_async("test text")

                # Verify daemon=True was passed
                assert thread_kwargs.get("daemon") is True