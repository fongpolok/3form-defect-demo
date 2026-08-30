"""
Robotiq 2-finger adaptive gripper control over RS-232, ported directly from
the old app's `Gripper.cs`. The byte frames are pre-computed Modbus RTU
"write multiple registers" commands (function 0x10, register 0x03E8) for
this specific gripper's activate/open/close actions — the original C# code
hardcoded these frames rather than building/CRC-ing them generically, and
this port keeps that same approach for a faithful, verifiable translation.

Not exercised by automated tests — needs the physical gripper and serial
port present, neither of which exist in this dev environment. Written
against `pyserial`'s standard API, which is straightforward enough that
this should work as-is once real hardware is available; treat it as
unverified until then rather than assuming it's been tested.
"""
from __future__ import annotations

import serial

from app.logging_setup import get_logger

logger = get_logger(__name__)

ACTIVATE_FRAME = bytes([0x09, 0x10, 0x03, 0xE8, 0x00, 0x03, 0x06, 0x01, 0x00, 0x00, 0x00, 0x00, 0x00, 0x72, 0xE1])
OPEN_FRAME = bytes([0x09, 0x10, 0x03, 0xE8, 0x00, 0x03, 0x06, 0x09, 0x00, 0x00, 0x00, 0xFF, 0xFF, 0x72, 0x19])
CLOSE_FRAME = bytes([0x09, 0x10, 0x03, 0xE8, 0x00, 0x03, 0x06, 0x09, 0x00, 0x00, 0xFF, 0xFF, 0xFF, 0x42, 0x29])


class RobotiqGripper:
    def __init__(self, port: str = "COM3", baudrate: int = 115200) -> None:
        self.port = port
        self.baudrate = baudrate
        self._serial: serial.Serial | None = None

    def connect(self) -> None:
        self._serial = serial.Serial(
            port=self.port,
            baudrate=self.baudrate,
            bytesize=serial.EIGHTBITS,
            parity=serial.PARITY_NONE,
            stopbits=serial.STOPBITS_ONE,
            timeout=1,
        )
        self._serial.write(ACTIVATE_FRAME)
        logger.info("Gripper activated on %s @ %d baud", self.port, self.baudrate)

    def open(self) -> None:
        self._write(OPEN_FRAME)
        logger.info("Gripper open command sent")

    def close(self) -> None:
        self._write(CLOSE_FRAME)
        logger.info("Gripper close command sent")

    def _write(self, frame: bytes) -> None:
        if self._serial is None or not self._serial.is_open:
            raise RuntimeError("connect() must be called before sending gripper commands")
        self._serial.write(frame)

    def disconnect(self) -> None:
        if self._serial is not None and self._serial.is_open:
            self._serial.close()
        logger.info("Gripper disconnected")
