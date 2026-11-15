from __future__ import annotations

import math
import socket
import struct
import threading
import time

import pytest

from jarvis.runner import clock as clock_module
from jarvis.runner.clock import NTP_EPOCH_OFFSET, ClockMonitor, ntp_measure, sntp_offset


class Mono:
    def __init__(self) -> None:
        self.now = 0.0

    def __call__(self) -> float:
        return self.now


async def test_unknown_until_measured_then_cached_then_expires() -> None:
    mono = Mono()

    async def measure() -> float:
        return 0.2

    monitor = ClockMonitor(measure, monotonic=mono)
    assert monitor.drift() == math.inf  # never checked: halt
    await monitor.refresh()
    assert monitor.drift() == 0.2
    mono.now = 3601
    assert monitor.drift() == math.inf  # too old to trust


async def test_failed_check_keeps_the_last_value() -> None:
    mono = Mono()
    results: list[float | Exception] = [0.1, OSError("no network")]

    async def measure() -> float:
        result = results.pop(0)
        if isinstance(result, Exception):
            raise result
        return result

    monitor = ClockMonitor(measure, monotonic=mono)
    await monitor.refresh()
    await monitor.refresh()
    assert monitor.drift() == 0.1


def fake_ntp_server(offset: float) -> tuple[socket.socket, int]:
    server = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    server.bind(("127.0.0.1", 0))

    def answer() -> None:
        _, address = server.recvfrom(48)
        now = time.time() + offset + NTP_EPOCH_OFFSET
        seconds, fraction = int(now), int((now % 1) * 2**32)
        server.sendto(b"\0" * 40 + struct.pack("!II", seconds, fraction), address)

    threading.Thread(target=answer, daemon=True).start()
    return server, server.getsockname()[1]


def test_sntp_measures_the_offset() -> None:
    server, port = fake_ntp_server(offset=2.5)
    try:
        assert sntp_offset("127.0.0.1", port=port) == pytest.approx(2.5, abs=0.2)
    finally:
        server.close()


async def test_ntp_measure_runs_off_the_event_loop(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(clock_module, "sntp_offset", lambda server: 0.05)
    assert await ntp_measure("example")() == 0.05
