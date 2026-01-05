"""Tests for CLI module."""

import sys
from io import StringIO
from unittest.mock import patch

import pytest

from keychron_via_hue import cli


class TestParseHexId:
    """Tests for parse_hex_id function."""

    def test_with_0x_prefix(self):
        assert cli.parse_hex_id("0x3434") == "3434"
        assert cli.parse_hex_id("0X0011") == "0011"

    def test_without_prefix(self):
        assert cli.parse_hex_id("3434") == "3434"
        assert cli.parse_hex_id("0011") == "0011"

    def test_case_insensitive(self):
        assert cli.parse_hex_id("0xFF00") == "ff00"
        assert cli.parse_hex_id("FF00") == "ff00"

    def test_strips_whitespace(self):
        assert cli.parse_hex_id("  0x3434  ") == "3434"


class TestCliMain:
    """Tests for main CLI function."""

    @patch("keychron_via_hue.cli.color_parser.parse_color")
    @patch("keychron_via_hue.cli.hue_adjuster.adjust_hue")
    @patch("keychron_via_hue.cli.qmk_hid.save_hue")
    @patch("sys.stdout", new_callable=StringIO)
    def test_success_basic(self, mock_stdout, mock_save, mock_adjust, mock_parse):
        mock_parse.return_value = 85  # green

        test_args = [
            "keychron-via-hue",
            "green",
            "--vid", "0x3434",
            "--pid", "0x0011"
        ]

        with patch("sys.argv", test_args):
            with patch("sys.exit"):
                cli.main()

        mock_parse.assert_called_once_with("green")
        mock_adjust.assert_called_once_with(
            target_hue=85,
            vid="3434",
            pid="0011",
            step=8,
            delay_ms=15
        )
        mock_save.assert_not_called()
        assert "OK:" in mock_stdout.getvalue()

    @patch("keychron_via_hue.cli.color_parser.parse_color")
    @patch("keychron_via_hue.cli.hue_adjuster.adjust_hue")
    @patch("keychron_via_hue.cli.qmk_hid.save_hue")
    @patch("sys.stdout", new_callable=StringIO)
    def test_success_with_save(self, mock_stdout, mock_save, mock_adjust, mock_parse):
        mock_parse.return_value = 0  # red

        test_args = [
            "keychron-via-hue",
            "red",
            "--vid", "3434",
            "--pid", "0011",
            "--save"
        ]

        with patch("sys.argv", test_args):
            with patch("sys.exit"):
                cli.main()

        mock_save.assert_called_once_with("3434", "0011")

    @patch("keychron_via_hue.cli.color_parser.parse_color")
    @patch("keychron_via_hue.cli.hue_adjuster.adjust_hue")
    @patch("keychron_via_hue.cli.qmk_hid.save_hue")
    @patch("sys.stdout", new_callable=StringIO)
    def test_with_custom_step_and_delay(self, mock_stdout, mock_save, mock_adjust, mock_parse):
        mock_parse.return_value = 170  # blue

        test_args = [
            "keychron-via-hue",
            "blue",
            "--vid", "0x3434",
            "--pid", "0x0011",
            "--step", "4",
            "--delay-ms", "20"
        ]

        with patch("sys.argv", test_args):
            with patch("sys.exit"):
                cli.main()

        mock_adjust.assert_called_once_with(
            target_hue=170,
            vid="3434",
            pid="0011",
            step=4,
            delay_ms=20
        )

    @patch("keychron_via_hue.cli.color_parser.parse_color")
    @patch("sys.stderr", new_callable=StringIO)
    @patch("sys.exit")
    def test_invalid_color(self, mock_exit, mock_stderr, mock_parse):
        mock_parse.side_effect = ValueError("Unknown color format: invalid")

        test_args = [
            "keychron-via-hue",
            "invalid",
            "--vid", "0x3434",
            "--pid", "0x0011"
        ]

        with patch("sys.argv", test_args):
            cli.main()

        mock_exit.assert_called_once_with(1)
        assert "Error" in mock_stderr.getvalue()

    @patch("keychron_via_hue.cli.color_parser.parse_color")
    @patch("keychron_via_hue.cli.hue_adjuster.adjust_hue")
    @patch("sys.stderr", new_callable=StringIO)
    @patch("sys.exit")
    def test_file_not_found_error(self, mock_exit, mock_stderr, mock_parse, mock_adjust):
        mock_parse.return_value = 85
        mock_adjust.side_effect = FileNotFoundError("qmk_hid not found")

        test_args = [
            "keychron-via-hue",
            "green",
            "--vid", "0x3434",
            "--pid", "0x0011"
        ]

        with patch("sys.argv", test_args):
            cli.main()

        mock_exit.assert_called_once_with(1)
        assert "Error" in mock_stderr.getvalue()

    @patch("keychron_via_hue.cli.color_parser.parse_color")
    @patch("keychron_via_hue.cli.hue_adjuster.adjust_hue")
    @patch("sys.stderr", new_callable=StringIO)
    @patch("sys.exit")
    def test_subprocess_error(self, mock_exit, mock_stderr, mock_parse, mock_adjust):
        import subprocess
        mock_parse.return_value = 85
        error = subprocess.CalledProcessError(1, ["qmk_hid"], stderr="Device not found")
        mock_adjust.side_effect = error

        test_args = [
            "keychron-via-hue",
            "green",
            "--vid", "0x3434",
            "--pid", "0x0011"
        ]

        with patch("sys.argv", test_args):
            cli.main()

        mock_exit.assert_called_once_with(1)
        assert "Error" in mock_stderr.getvalue()

    @patch("sys.stderr", new_callable=StringIO)
    def test_missing_required_args(self, mock_stderr):
        test_args = [
            "keychron-via-hue",
            "green"
            # Отсутствуют --vid и --pid
        ]

        with patch("sys.argv", test_args):
            with pytest.raises(SystemExit):
                cli.main()

