"""Tests for qmk_hid module."""

import subprocess
from unittest.mock import Mock, patch, MagicMock

import pytest

from keychron_via_hue import qmk_hid


class TestFindQmkHid:
    """Tests for find_qmk_hid function."""

    @patch("shutil.which")
    def test_found(self, mock_which):
        mock_which.return_value = "/usr/bin/qmk_hid"
        result = qmk_hid.find_qmk_hid()
        assert result == "qmk_hid"
        mock_which.assert_called_once_with("qmk_hid")

    @patch("shutil.which")
    def test_not_found(self, mock_which):
        mock_which.return_value = None
        with pytest.raises(FileNotFoundError, match="qmk_hid not found"):
            qmk_hid.find_qmk_hid()


class TestGetCurrentHue:
    """Tests for get_current_hue function."""

    @patch("keychron_via_hue.qmk_hid.find_qmk_hid")
    @patch("subprocess.run")
    def test_success(self, mock_run, mock_find):
        mock_find.return_value = "qmk_hid"
        mock_run.return_value = Mock(
            stdout="128\n",
            stderr="",
            returncode=0
        )

        hue = qmk_hid.get_current_hue("0x3434", "0x0011")
        assert hue == 128

        mock_run.assert_called_once()
        args = mock_run.call_args[0][0]
        assert args[0] == "qmk_hid"
        assert "--vid" in args
        assert "--pid" in args
        assert "--rgb-hue" in args

    @patch("keychron_via_hue.qmk_hid.find_qmk_hid")
    @patch("subprocess.run")
    def test_normalize_vid_pid(self, mock_run, mock_find):
        mock_find.return_value = "qmk_hid"
        mock_run.return_value = Mock(stdout="0\n", stderr="", returncode=0)

        qmk_hid.get_current_hue("3434", "0011")
        args = mock_run.call_args[0][0]
        vid_idx = args.index("--vid")
        pid_idx = args.index("--pid")
        assert args[vid_idx + 1] == "3434"
        assert args[pid_idx + 1] == "0011"

        # С 0x префиксом
        qmk_hid.get_current_hue("0x3434", "0x0011")
        args = mock_run.call_args[0][0]
        vid_idx = args.index("--vid")
        pid_idx = args.index("--pid")
        assert args[vid_idx + 1] == "3434"
        assert args[pid_idx + 1] == "0011"

    @patch("keychron_via_hue.qmk_hid.find_qmk_hid")
    @patch("subprocess.run")
    def test_invalid_hue_value(self, mock_run, mock_find):
        mock_find.return_value = "qmk_hid"
        mock_run.return_value = Mock(
            stdout="300\n",  # > 255
            stderr="",
            returncode=0
        )

        with pytest.raises(ValueError, match="Invalid hue value"):
            qmk_hid.get_current_hue("3434", "0011")

    @patch("keychron_via_hue.qmk_hid.find_qmk_hid")
    @patch("subprocess.run")
    def test_unparseable_output(self, mock_run, mock_find):
        mock_find.return_value = "qmk_hid"
        mock_run.return_value = Mock(
            stdout="not a number\n",
            stderr="",
            returncode=0
        )

        with pytest.raises(ValueError, match="Could not parse hue value"):
            qmk_hid.get_current_hue("3434", "0011")

    @patch("keychron_via_hue.qmk_hid.find_qmk_hid")
    @patch("subprocess.run")
    def test_process_error(self, mock_run, mock_find):
        mock_find.return_value = "qmk_hid"
        error = subprocess.CalledProcessError(1, ["qmk_hid"], stderr="Device not found")
        mock_run.side_effect = error

        with pytest.raises(subprocess.CalledProcessError) as exc_info:
            qmk_hid.get_current_hue("3434", "0011")
        # Проверяем что исключение было поднято и что это наш обработанный вариант
        # (проверяем что функция обработала исходное исключение)
        assert exc_info.value.returncode == 1

    @patch("keychron_via_hue.qmk_hid.find_qmk_hid")
    def test_qmk_hid_not_found(self, mock_find):
        mock_find.side_effect = FileNotFoundError("qmk_hid not found")
        with pytest.raises(FileNotFoundError):
            qmk_hid.get_current_hue("3434", "0011")


class TestSetHueStep:
    """Tests for set_hue_step function."""

    @patch("keychron_via_hue.qmk_hid.find_qmk_hid")
    @patch("subprocess.run")
    def test_up_direction(self, mock_run, mock_find):
        mock_find.return_value = "qmk_hid"
        mock_run.return_value = Mock(stdout="", stderr="", returncode=0)

        qmk_hid.set_hue_step("3434", "0011", "up", count=5)

        # Должно быть 5 вызовов
        assert mock_run.call_count == 5
        for call in mock_run.call_args_list:
            args = call[0][0]
            assert "--rgb-hue-up" in args

    @patch("keychron_via_hue.qmk_hid.find_qmk_hid")
    @patch("subprocess.run")
    def test_down_direction(self, mock_run, mock_find):
        mock_find.return_value = "qmk_hid"
        mock_run.return_value = Mock(stdout="", stderr="", returncode=0)

        qmk_hid.set_hue_step("3434", "0011", "down", count=3)

        assert mock_run.call_count == 3
        for call in mock_run.call_args_list:
            args = call[0][0]
            assert "--rgb-hue-down" in args

    def test_invalid_direction(self):
        with pytest.raises(ValueError, match="Invalid direction"):
            qmk_hid.set_hue_step("3434", "0011", "invalid", count=1)

    @patch("keychron_via_hue.qmk_hid.find_qmk_hid")
    @patch("subprocess.run")
    def test_process_error(self, mock_run, mock_find):
        mock_find.return_value = "qmk_hid"
        error = subprocess.CalledProcessError(1, ["qmk_hid"], stderr="Device not found")
        mock_run.side_effect = error

        with pytest.raises(subprocess.CalledProcessError) as exc_info:
            qmk_hid.set_hue_step("3434", "0011", "up", count=1)
        assert exc_info.value.returncode == 1


class TestSaveHue:
    """Tests for save_hue function."""

    @patch("keychron_via_hue.qmk_hid.find_qmk_hid")
    @patch("subprocess.run")
    def test_success(self, mock_run, mock_find):
        mock_find.return_value = "qmk_hid"
        mock_run.return_value = Mock(stdout="", stderr="", returncode=0)

        qmk_hid.save_hue("3434", "0011")

        mock_run.assert_called_once()
        args = mock_run.call_args[0][0]
        assert "--rgb-hue-save" in args

    @patch("keychron_via_hue.qmk_hid.find_qmk_hid")
    @patch("subprocess.run")
    def test_process_error(self, mock_run, mock_find):
        mock_find.return_value = "qmk_hid"
        error = subprocess.CalledProcessError(1, ["qmk_hid"], stderr="Save failed")
        mock_run.side_effect = error

        with pytest.raises(subprocess.CalledProcessError) as exc_info:
            qmk_hid.save_hue("3434", "0011")
        assert exc_info.value.returncode == 1

