"""
Camera-focus stepper motor control via the AMC 2XE USB motion card, ported
from the old app's `StepperMotion.cs`. That card only has a Windows driver
DLL (`Usb_AMC2XE_Dll.dll`, loaded there via P/Invoke) — this module talks to
the *same* DLL via Python's `ctypes.WinDLL` instead of going through C#, so
no C# process is needed at all going forward.

BLOCKED here on two counts, not just one: this dev machine is macOS (no
`ctypes.WinDLL`, no DLL to load) AND has no AMC2XE card attached even in
principle. `AmcFocusMotor.__init__` raises immediately on import/instantiate
on a non-Windows platform rather than pretending to work — this is
unverified against real hardware and should be tested for real on the
Windows machine that has the card before relying on it.
"""
from __future__ import annotations

import platform
import threading
from ctypes import byref, c_byte, c_int, c_uint
from typing import Callable

from app.logging_setup import get_logger

logger = get_logger(__name__)

DLL_PATH = r"C:\Project\ViDiMachine\UsbMotion\Usb_AMC2XE_Dll.dll"  # same path as StepperMotion.cs

MODULO = 1 << 24
MAX_VALUE = (1 << 23) - 1

# Y-axis index, same convention as the original (axis 1 = focus axis).
Y_AXIS = 1


class MotionState:
    NORMAL_STOP = 0
    MOVING = 1
    HOMING = 2
    PEL = 3  # touching + limit
    NEL = 4  # touching - limit
    EMG = 5


class AmcFocusMotor:
    def __init__(self) -> None:
        if platform.system() != "Windows":
            raise RuntimeError(
                "AmcFocusMotor requires Windows (ctypes.WinDLL) and the AMC2XE USB "
                "motion card driver — neither is available on this machine. This is "
                "an explicitly blocked/unverified module; see its module docstring."
            )
        import ctypes

        self._dll = ctypes.WinDLL(DLL_PATH)
        self._dev = 0
        self._opened = False
        self._monitor_thread: threading.Thread | None = None
        self._keep_monitoring = False
        self.on_position_changed: Callable[[int], None] | None = None

    # -- signed/unsigned pulse-count conversion, same bit trick as the original --
    @staticmethod
    def _uint_to_int(value: int) -> int:
        return value - MODULO if value > MAX_VALUE else value

    @staticmethod
    def _int_to_uint(value: int) -> int:
        if value < 0:
            return (value + 32768) | 0b1111_1111_1000_0000_0000_0000
        return value

    def open(self) -> None:
        self._dll.OpenUSB_2XE()
        self._opened = True
        id1, id2, id3 = c_uint(), c_uint(), c_uint()
        self._dll.GetCardId_2XE(self._dev, byref(id1), byref(id2), byref(id3))
        self._dll.Set_Axs_2XE(self._dev, Y_AXIS, 0, 0, 0, 0)
        self._dll.Set_Axs_2XE(self._dev, Y_AXIS, 1, 0, 0, 0)
        self._dll.Set_Encorder_2XE(self._dev, Y_AXIS, 3, 0, 0, 1, 0)
        self._dll.Set_Encorder_2XE(self._dev, Y_AXIS, 3, 0, 0, 1, 1)

        self._keep_monitoring = True
        self._monitor_thread = threading.Thread(target=self._monitor_loop, daemon=True)
        self._monitor_thread.start()
        logger.info("AmcFocusMotor opened (card id %d/%d/%d)", id1.value, id2.value, id3.value)

    def home(self) -> None:
        if not self._opened:
            raise RuntimeError("open() must be called first")
        init_speed = 1000
        self._dll.FH_ContinueMov_2XE(self._dev, Y_AXIS, 0, c_byte(0), init_speed, 20000)
        self.wait()
        self._dll.MovToOrg_2XE(self._dev, Y_AXIS, 1, c_byte(0), init_speed)
        logger.info("Focus axis homed")

    def move_absolute(self, target_position: int) -> None:
        if not self._opened:
            raise RuntimeError("open() must be called first")
        current, _ = self.get_state()
        forward = target_position > current
        delta = self._int_to_uint(abs(target_position - current))
        direction = 0 if forward else 1
        self._dll.DeltMov_2XE(
            self._dev, Y_AXIS, 0, direction, c_byte(0),
            1000, 20000, delta, 0, 100, 100,
        )
        logger.info("Focus move: %d -> %d", current, target_position)

    def get_state(self) -> tuple[int, int]:
        pos, run_state, io_state, sync_io = c_uint(), c_byte(), c_byte(), c_byte()
        self._dll.Read_Position_2XE(self._dev, Y_AXIS, byref(pos), byref(run_state), byref(io_state), byref(sync_io))
        position = self._uint_to_int(pos.value)

        if run_state.value == 0:
            if io_state.value & (1 << 1):
                state = MotionState.NORMAL_STOP
            elif io_state.value & (1 << 2):
                state = MotionState.NEL
            elif io_state.value & (1 << 3):
                state = MotionState.PEL
            else:
                state = MotionState.NORMAL_STOP
        elif run_state.value == 5:
            state = MotionState.HOMING
        else:
            state = MotionState.MOVING
        return position, state

    def wait(self) -> int:
        while True:
            _, state = self.get_state()
            if state != MotionState.MOVING:
                return state
            threading.Event().wait(0.01)

    def _monitor_loop(self) -> None:
        prev_position = None
        while self._keep_monitoring:
            position, _ = self.get_state()
            if position != prev_position and self.on_position_changed is not None:
                self.on_position_changed(position)
            prev_position = position
            threading.Event().wait(0.05)

    def release(self) -> None:
        self._keep_monitoring = False
        if self._monitor_thread is not None:
            self._monitor_thread.join(timeout=1)
        self._dll.CloseUSB_2XE()
        self._opened = False
        logger.info("AmcFocusMotor released")
