"""Hub client for the Neo Smart Controller.

Speaks the Neo Open Local protocol over either HTTP (port 8838) or TCP
(port 8839).  A single NeoHub owns one controller; commands are sent
serially with a small backoff so the hub isn't flooded.
"""
from __future__ import annotations

import asyncio
import logging
from datetime import datetime
from typing import Optional

import aiohttp

from .const import (
    COMMAND_BACKOFF,
    IO_TIMEOUT,
    PROTOCOL_HTTP,
    PROTOCOL_TCP,
)

_LOGGER = logging.getLogger(__name__)


class NeoHubError(Exception):
    """Raised when a command to the hub fails."""


class NeoHub:
    """Async client for a Neo Smart Controller.

    Commands are 2-letter codes ('up', 'dn', 'sp', 'mu', 'md', 'u2', 'd2').
    The wire payload is `<prefix>-<channel>-<command>[!<motor_code>]`,
    where prefix is `ID1.ID2` and channel is `01`-`15`.
    """

    def __init__(
        self,
        host: str,
        hub_id: str,
        protocol: str,
        port: int,
        motor_code: Optional[str],
        http_session: Optional[aiohttp.ClientSession],
    ) -> None:
        self._host = host
        self._hub_id = hub_id
        self._protocol = protocol.lower()
        self._port = int(port)
        self._motor_code = motor_code
        self._session = http_session
        self._send_lock = asyncio.Lock()
        self._last_send = 0.0

    @property
    def host(self) -> str:
        return self._host

    @property
    def hub_id(self) -> str:
        return self._hub_id

    @property
    def signature(self) -> str:
        """Stable identifier used for HA device registry."""
        return f"{self._hub_id}@{self._host}"

    @staticmethod
    def format_blind_code(prefix: str, channel: int) -> str:
        """Build the wire address for a blind: '021.230-04'."""
        return f"{prefix}-{channel:02d}"

    async def async_send(self, blind_code: str, command: str) -> None:
        """Send a single command to a blind (or group)."""
        suffix = f"!{self._motor_code}" if self._motor_code else ""
        payload = f"{blind_code}-{command}{suffix}"
        async with self._send_lock:
            # Space commands out so the hub keeps up.
            elapsed = asyncio.get_event_loop().time() - self._last_send
            if elapsed < COMMAND_BACKOFF:
                await asyncio.sleep(COMMAND_BACKOFF - elapsed)
            try:
                if self._protocol == PROTOCOL_HTTP:
                    await self._send_http(payload)
                elif self._protocol == PROTOCOL_TCP:
                    await self._send_tcp(payload)
                else:
                    raise NeoHubError(f"Unknown protocol: {self._protocol}")
            finally:
                self._last_send = asyncio.get_event_loop().time()

    async def _send_http(self, payload: str) -> None:
        if self._session is None:
            raise NeoHubError("HTTP session not initialised")
        url = f"http://{self._host}:{self._port}/neo/v1/transmit"
        # Hash is required by the hub; microsecond is unique-enough in practice.
        params = {
            "id": self._hub_id,
            "command": payload,
            "hash": str(datetime.now().microsecond).zfill(7),
        }
        _LOGGER.debug("HTTP -> %s %s", url, params)
        try:
            async with self._session.get(
                url, params=params, timeout=aiohttp.ClientTimeout(total=IO_TIMEOUT)
            ) as resp:
                body = await resp.text()
                _LOGGER.debug("HTTP <- %s: %s", resp.status, body)
                if resp.status >= 400:
                    raise NeoHubError(f"Hub HTTP {resp.status}: {body}")
        except aiohttp.ClientError as err:
            raise NeoHubError(f"HTTP error talking to hub: {err}") from err
        except asyncio.TimeoutError as err:
            raise NeoHubError("Timed out talking to hub over HTTP") from err

    async def _send_tcp(self, payload: str) -> None:
        line = f"{payload}\r\n".encode()
        _LOGGER.debug("TCP -> %s:%s %s", self._host, self._port, payload)
        try:
            reader, writer = await asyncio.wait_for(
                asyncio.open_connection(self._host, self._port), timeout=IO_TIMEOUT
            )
        except (OSError, asyncio.TimeoutError) as err:
            raise NeoHubError(f"Cannot connect to hub at {self._host}:{self._port}: {err}") from err

        try:
            writer.write(line)
            await asyncio.wait_for(writer.drain(), timeout=IO_TIMEOUT)
            # The hub responds with an ack; drain it but don't require a shape.
            try:
                resp = await asyncio.wait_for(reader.read(256), timeout=2.0)
                _LOGGER.debug("TCP <- %s", resp)
            except asyncio.TimeoutError:
                pass
        finally:
            writer.close()
            try:
                await writer.wait_closed()
            except Exception:  # noqa: BLE001 — best-effort cleanup
                pass

    async def async_probe(self) -> None:
        """Verify a hub is reachable. Raises NeoHubError on failure.

        We don't have a documented no-op, so we just confirm the right
        port is listening (TCP) or that the HTTP endpoint responds at
        all to a malformed request — which the hub will reject without
        moving any blinds.
        """
        if self._protocol == PROTOCOL_HTTP:
            if self._session is None:
                raise NeoHubError("HTTP session not initialised")
            url = f"http://{self._host}:{self._port}/neo/v1/transmit"
            try:
                async with self._session.get(
                    url,
                    params={"id": self._hub_id, "command": "probe", "hash": "0000000"},
                    timeout=aiohttp.ClientTimeout(total=IO_TIMEOUT),
                ) as resp:
                    # Any response (even an error) means a Neo hub is listening.
                    await resp.text()
            except aiohttp.ClientError as err:
                raise NeoHubError(f"Cannot reach hub at {self._host}:{self._port}: {err}") from err
            except asyncio.TimeoutError as err:
                raise NeoHubError(f"Timed out reaching {self._host}:{self._port}") from err
        else:
            try:
                _, writer = await asyncio.wait_for(
                    asyncio.open_connection(self._host, self._port), timeout=IO_TIMEOUT
                )
                writer.close()
                try:
                    await writer.wait_closed()
                except Exception:  # noqa: BLE001
                    pass
            except (OSError, asyncio.TimeoutError) as err:
                raise NeoHubError(f"Cannot reach hub at {self._host}:{self._port}: {err}") from err
