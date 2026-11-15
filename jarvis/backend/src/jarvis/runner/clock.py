"""Clock check against an NTP server (spec §11: drift over 1 s stops trading).

The measurement runs in the background; the risk engine reads the cached value. If the
clock cannot be checked for an hour, the drift is reported as unknown (infinite), which
halts trading: an unverified clock is treated like a wrong one.
"""

from __future__ import annotations

import asyncio
import logging
import math
import socket
import struct
import time
from collections.abc import Awaitable, Callable

logger = logging.getLogger(__name__)
NTP_EPOCH_OFFSET = 2208988800  # seconds between 1900-01-01 and 1970-01-01
MAX_AGE_SECONDS = 3600.0


def sntp_offset(server: str, timeout: float = 3.0, port: int = 123) -> float:
    """One SNTP request (RFC 4330): how far the local clock is from the server's, in s."""
    request = b"\x1b" + 47 * b"\0"  # version 3, client mode
    with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as sock:
        sock.settimeout(timeout)
        sent = time.time()
        sock.sendto(request, (server, port))
        data, _ = sock.recvfrom(48)
        received = time.time()
    seconds, fraction = struct.unpack("!II", data[40:48])  # server transmit time
    server_time: float = seconds - NTP_EPOCH_OFFSET + fraction / 2**32
    return server_time - (sent + received) / 2


class ClockMonitor:
    def __init__(
        self,
        measure: Callable[[], Awaitable[float]],
        monotonic: Callable[[], float] = time.monotonic,
    ) -> None:
        self._measure = measure
        self._monotonic = monotonic
        self._drift: float | None = None
        self._measured_at: float | None = None

    async def refresh(self) -> None:
        try:
            self._drift = await self._measure()
            self._measured_at = self._monotonic()
        except Exception:
            logger.warning("clock check failed; keeping the last measurement for now")

    def drift(self) -> float:
        if self._drift is None or self._measured_at is None:
            return math.inf
        if self._monotonic() - self._measured_at > MAX_AGE_SECONDS:
            return math.inf
        return self._drift


def ntp_measure(server: str = "pool.ntp.org") -> Callable[[], Awaitable[float]]:
    async def measure() -> float:
        return await asyncio.to_thread(sntp_offset, server)

    return measure
