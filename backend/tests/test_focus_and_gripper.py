"""Both modules are hardware-blocked on this dev machine (no Windows/AMC2XE
card, no gripper/serial port attached) — these tests only verify what's
actually checkable without that hardware: the ported byte frames are exact,
and each module fails loudly/clearly rather than pretending to work."""
from __future__ import annotations

import platform

import pytest

from app.gripper.robotiq_modbus import ACTIVATE_FRAME, CLOSE_FRAME, OPEN_FRAME, RobotiqGripper


def test_gripper_frames_match_legacy_csharp_exactly():
    # Byte-for-byte against RoboDKVisionCalibrator/Gripper.cs
    assert list(ACTIVATE_FRAME) == [0x09, 0x10, 0x03, 0xE8, 0x00, 0x03, 0x06, 0x01, 0x00, 0x00, 0x00, 0x00, 0x00, 0x72, 0xE1]
    assert list(OPEN_FRAME) == [0x09, 0x10, 0x03, 0xE8, 0x00, 0x03, 0x06, 0x09, 0x00, 0x00, 0x00, 0xFF, 0xFF, 0x72, 0x19]
    assert list(CLOSE_FRAME) == [0x09, 0x10, 0x03, 0xE8, 0x00, 0x03, 0x06, 0x09, 0x00, 0x00, 0xFF, 0xFF, 0xFF, 0x42, 0x29]


def test_gripper_rejects_commands_before_connect():
    gripper = RobotiqGripper(port="COM99")
    with pytest.raises(RuntimeError):
        gripper.open()


@pytest.mark.skipif(platform.system() == "Windows", reason="only tests the non-Windows guard")
def test_focus_motor_blocked_on_non_windows():
    from app.focus_motor.amc2xe import AmcFocusMotor
    with pytest.raises(RuntimeError, match="Windows"):
        AmcFocusMotor()
