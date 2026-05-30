"""Cover entities for Louvelite Blinds.

One cover entity per configured blind. The set of supported_features
is determined by the blind type, so a roller never shows tilt or a
position slider in the UI.
"""
from __future__ import annotations

import logging
from typing import Any

from homeassistant.components.cover import (
    CoverEntity,
    CoverEntityFeature,
    CoverDeviceClass,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import STATE_CLOSED, STATE_OPEN
from homeassistant.core import HomeAssistant
from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .const import (
    BLIND_TYPE_ROLLER,
    BLIND_TYPE_TDBU,
    BLIND_TYPE_VENETIAN,
    CMD_DOWN,
    CMD_DOWN_RAIL2,
    CMD_MICRO_DOWN,
    CMD_MICRO_UP,
    CMD_STOP,
    CMD_UP,
    CMD_UP_RAIL2,
    CONF_BLIND_ID,
    CONF_BLIND_TYPE,
    CONF_BLINDS,
    CONF_BLIND_CODE,
    CONF_MOTOR_CODE,
    CONF_NAME,
    CONF_PREFIX,
    CONF_REMOTE_ID,
    CONF_REMOTE_LABEL,
    CONF_REMOTES,
    CONF_ROOM,
    DOMAIN,
    RAIL_PRIMARY,
    RAIL_SECONDARY,
)
from .hub import NeoHub, NeoHubError

_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Build one (or two, for TDBU) cover entity per configured blind."""
    hub: NeoHub = hass.data[DOMAIN][entry.entry_id]
    remotes = {r[CONF_REMOTE_ID]: r for r in entry.options.get(CONF_REMOTES, [])}

    entities: list[CoverEntity] = []
    for blind in entry.options.get(CONF_BLINDS, []):
        remote = remotes.get(blind.get(CONF_REMOTE_ID))
        if remote is None:
            _LOGGER.warning(
                "Skipping blind %s: its remote no longer exists", blind.get(CONF_NAME)
            )
            continue
        blind_type = blind[CONF_BLIND_TYPE]
        prefix = remote[CONF_PREFIX]
        channel = blind[CONF_BLIND_CODE]
        blind_code = NeoHub.format_blind_code(prefix, channel)

        if blind_type == BLIND_TYPE_TDBU:
            entities.append(
                _TdbuRailCover(hub, entry, blind, remote, blind_code, RAIL_PRIMARY)
            )
            entities.append(
                _TdbuRailCover(hub, entry, blind, remote, blind_code, RAIL_SECONDARY)
            )
        elif blind_type == BLIND_TYPE_VENETIAN:
            entities.append(_VenetianCover(hub, entry, blind, remote, blind_code))
        else:
            entities.append(_RollerCover(hub, entry, blind, remote, blind_code))

    if entities:
        async_add_entities(entities)


class _NeoCoverBase(CoverEntity):
    """Common plumbing shared by roller / venetian / TDBU covers."""

    _attr_has_entity_name = True
    _attr_assumed_state = True  # the hub doesn't report position back
    _attr_device_class = CoverDeviceClass.BLIND
    _attr_should_poll = False

    def __init__(
        self,
        hub: NeoHub,
        entry: ConfigEntry,
        blind: dict[str, Any],
        remote: dict[str, Any],
        blind_code: str,
    ) -> None:
        self._hub = hub
        self._entry = entry
        self._blind = blind
        self._remote = remote
        self._blind_code = blind_code
        self._motor_code = (blind.get(CONF_MOTOR_CODE) or "").strip().lower() or None
        # Assume open until commanded otherwise so the UI shows a meaningful state.
        self._state_open: bool = True

        room = (blind.get(CONF_ROOM) or "").strip()
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, f"{entry.entry_id}:{blind[CONF_BLIND_ID]}")},
            name=blind[CONF_NAME],
            manufacturer="Neo Smart Blinds",
            model=self._model_name(),
            suggested_area=room or None,
            via_device=(DOMAIN, hub.signature),
        )

    def _model_name(self) -> str:
        return "Blind"

    @property
    def is_closed(self) -> bool | None:
        return not self._state_open

    async def _send(self, command: str) -> bool:
        try:
            await self._hub.async_send(self._blind_code, command, self._motor_code)
            return True
        except NeoHubError as err:
            _LOGGER.error(
                "%s (%s): command %r failed: %s",
                self._blind[CONF_NAME],
                self._blind_code,
                command,
                err,
            )
            return False


class _RollerCover(_NeoCoverBase):
    """Roller blind: up / down / stop. No tilt, no position slider."""

    _attr_supported_features = (
        CoverEntityFeature.OPEN | CoverEntityFeature.CLOSE | CoverEntityFeature.STOP
    )

    def __init__(self, hub, entry, blind, remote, blind_code) -> None:
        super().__init__(hub, entry, blind, remote, blind_code)
        self._attr_unique_id = f"{entry.entry_id}:{blind[CONF_BLIND_ID]}"
        self._attr_name = None  # device name is the blind name; entity is the cover itself

    def _model_name(self) -> str:
        return "Roller blind"

    async def async_open_cover(self, **kwargs: Any) -> None:
        if await self._send(CMD_UP):
            self._state_open = True
            self.async_write_ha_state()

    async def async_close_cover(self, **kwargs: Any) -> None:
        if await self._send(CMD_DOWN):
            self._state_open = False
            self.async_write_ha_state()

    async def async_stop_cover(self, **kwargs: Any) -> None:
        await self._send(CMD_STOP)


class _VenetianCover(_NeoCoverBase):
    """Venetian / shutter: up / down / stop + tilt up / tilt down."""

    _attr_supported_features = (
        CoverEntityFeature.OPEN
        | CoverEntityFeature.CLOSE
        | CoverEntityFeature.STOP
        | CoverEntityFeature.OPEN_TILT
        | CoverEntityFeature.CLOSE_TILT
        | CoverEntityFeature.STOP_TILT
    )
    _attr_device_class = CoverDeviceClass.SHUTTER

    def __init__(self, hub, entry, blind, remote, blind_code) -> None:
        super().__init__(hub, entry, blind, remote, blind_code)
        self._attr_unique_id = f"{entry.entry_id}:{blind[CONF_BLIND_ID]}"
        self._attr_name = None

    def _model_name(self) -> str:
        return "Venetian blind"

    async def async_open_cover(self, **kwargs: Any) -> None:
        if await self._send(CMD_UP):
            self._state_open = True
            self.async_write_ha_state()

    async def async_close_cover(self, **kwargs: Any) -> None:
        if await self._send(CMD_DOWN):
            self._state_open = False
            self.async_write_ha_state()

    async def async_stop_cover(self, **kwargs: Any) -> None:
        await self._send(CMD_STOP)

    async def async_open_cover_tilt(self, **kwargs: Any) -> None:
        await self._send(CMD_MICRO_UP)

    async def async_close_cover_tilt(self, **kwargs: Any) -> None:
        await self._send(CMD_MICRO_DOWN)

    async def async_stop_cover_tilt(self, **kwargs: Any) -> None:
        await self._send(CMD_STOP)


class _TdbuRailCover(_NeoCoverBase):
    """One rail of a Top-Down / Bottom-Up blind. Exposed as two covers."""

    _attr_supported_features = (
        CoverEntityFeature.OPEN | CoverEntityFeature.CLOSE | CoverEntityFeature.STOP
    )

    def __init__(self, hub, entry, blind, remote, blind_code, rail: int) -> None:
        super().__init__(hub, entry, blind, remote, blind_code)
        self._rail = rail
        suffix = "bottom" if rail == RAIL_PRIMARY else "top"
        self._attr_unique_id = f"{entry.entry_id}:{blind[CONF_BLIND_ID]}:{suffix}"
        self._attr_name = "Bottom rail" if rail == RAIL_PRIMARY else "Top rail"

    def _model_name(self) -> str:
        return "Top-Down / Bottom-Up blind"

    async def async_open_cover(self, **kwargs: Any) -> None:
        cmd = CMD_UP if self._rail == RAIL_PRIMARY else CMD_UP_RAIL2
        if await self._send(cmd):
            self._state_open = True
            self.async_write_ha_state()

    async def async_close_cover(self, **kwargs: Any) -> None:
        cmd = CMD_DOWN if self._rail == RAIL_PRIMARY else CMD_DOWN_RAIL2
        if await self._send(cmd):
            self._state_open = False
            self.async_write_ha_state()

    async def async_stop_cover(self, **kwargs: Any) -> None:
        await self._send(CMD_STOP)
