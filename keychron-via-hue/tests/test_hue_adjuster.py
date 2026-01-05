"""Tests for hue_adjuster module."""

import time
from unittest.mock import patch, Mock

import pytest

from keychron_via_hue import hue_adjuster
from keychron_via_hue import qmk_hid


class TestAdjustHue:
    """Tests for adjust_hue function."""

    @patch("keychron_via_hue.hue_adjuster.qmk_hid.get_current_hue")
    @patch("keychron_via_hue.hue_adjuster.qmk_hid.set_hue_step")
    def test_no_change_needed(self, mock_set_step, mock_get_hue):
        mock_get_hue.return_value = 128

        hue_adjuster.adjust_hue(128, "3434", "0011", step=8, delay_ms=15)

        mock_get_hue.assert_called_once()
        mock_set_step.assert_not_called()

    @patch("keychron_via_hue.hue_adjuster.qmk_hid.get_current_hue")
    @patch("keychron_via_hue.hue_adjuster.qmk_hid.set_hue_step")
    @patch("time.sleep")
    def test_forward_adjustment(self, mock_sleep, mock_set_step, mock_get_hue):
        mock_get_hue.return_value = 100
        target = 110

        hue_adjuster.adjust_hue(target, "3434", "0011", step=8, delay_ms=15)

        # Должно быть 10 вызовов (110 - 100 = 10 шагов)
        assert mock_set_step.call_count == 10
        for call in mock_set_step.call_args_list:
            assert call[0][2] == "up"  # direction
            assert call[0][3] == 1  # count
        # Должно быть 10 задержек (по одной после каждого шага)
        assert mock_sleep.call_count == 10
        assert all(abs(call[0][0] - 0.015) < 0.001 for call in mock_sleep.call_args_list)

    @patch("keychron_via_hue.hue_adjuster.qmk_hid.get_current_hue")
    @patch("keychron_via_hue.hue_adjuster.qmk_hid.set_hue_step")
    @patch("time.sleep")
    def test_backward_adjustment(self, mock_sleep, mock_set_step, mock_get_hue):
        mock_get_hue.return_value = 200
        target = 190

        hue_adjuster.adjust_hue(target, "3434", "0011", step=8, delay_ms=15)

        assert mock_set_step.call_count == 10
        for call in mock_set_step.call_args_list:
            assert call[0][2] == "down"
            assert call[0][3] == 1

    @patch("keychron_via_hue.hue_adjuster.qmk_hid.get_current_hue")
    @patch("keychron_via_hue.hue_adjuster.qmk_hid.set_hue_step")
    @patch("time.sleep")
    def test_wrap_around_forward(self, mock_sleep, mock_set_step, mock_get_hue):
        # 250 -> 10 (через границу 255/0)
        # Кратчайший путь: 250 -> 256 (wrap) -> 10 = 16 шагов вперед
        mock_get_hue.return_value = 250
        target = 10

        hue_adjuster.adjust_hue(target, "3434", "0011", step=8, delay_ms=15)

        # (10 - 250) % 256 = 16 шагов вперед
        assert mock_set_step.call_count == 16
        for call in mock_set_step.call_args_list:
            assert call[0][2] == "up"

    @patch("keychron_via_hue.hue_adjuster.qmk_hid.get_current_hue")
    @patch("keychron_via_hue.hue_adjuster.qmk_hid.set_hue_step")
    @patch("time.sleep")
    def test_wrap_around_backward(self, mock_sleep, mock_set_step, mock_get_hue):
        # 10 -> 250 (через границу 0/255)
        # Кратчайший путь: назад (10 -> 0 -> 255 -> 250 = 16 шагов назад)
        mock_get_hue.return_value = 10
        target = 250

        hue_adjuster.adjust_hue(target, "3434", "0011", step=8, delay_ms=15)

        # (10 - 250) % 256 = 16, но это вперед, а нам нужно выбрать кратчайший путь
        # На самом деле: diff_forward = (250 - 10) % 256 = 240
        # diff_backward = (10 - 250) % 256 = 16
        # 16 < 240, поэтому выбираем backward (16 шагов)
        assert mock_set_step.call_count == 16
        for call in mock_set_step.call_args_list:
            assert call[0][2] == "down"

    @patch("keychron_via_hue.hue_adjuster.qmk_hid.get_current_hue")
    @patch("keychron_via_hue.hue_adjuster.qmk_hid.set_hue_step")
    def test_no_delay(self, mock_set_step, mock_get_hue):
        mock_get_hue.return_value = 100
        target = 105

        with patch("time.sleep") as mock_sleep:
            hue_adjuster.adjust_hue(target, "3434", "0011", step=8, delay_ms=0)

        assert mock_set_step.call_count == 5
        mock_sleep.assert_not_called()

    def test_invalid_target_hue(self):
        with pytest.raises(ValueError, match="target_hue must be in range"):
            hue_adjuster.adjust_hue(-1, "3434", "0011")
        with pytest.raises(ValueError, match="target_hue must be in range"):
            hue_adjuster.adjust_hue(256, "3434", "0011")

    def test_invalid_step(self):
        with pytest.raises(ValueError, match="step must be in range"):
            hue_adjuster.adjust_hue(100, "3434", "0011", step=0)
        with pytest.raises(ValueError, match="step must be in range"):
            hue_adjuster.adjust_hue(100, "3434", "0011", step=256)

    def test_invalid_delay(self):
        with pytest.raises(ValueError, match="delay_ms must be non-negative"):
            hue_adjuster.adjust_hue(100, "3434", "0011", delay_ms=-1)

    @patch("keychron_via_hue.hue_adjuster.qmk_hid.get_current_hue")
    def test_qmk_hid_error_propagates(self, mock_get_hue):
        mock_get_hue.side_effect = FileNotFoundError("qmk_hid not found")

        with pytest.raises(FileNotFoundError):
            hue_adjuster.adjust_hue(100, "3434", "0011")




