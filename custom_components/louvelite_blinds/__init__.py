"""Louvelite Blinds (Neo Smart Controller) integration."""
from __future__ import annotations

import logging

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import Platform
from homeassistant.core import HomeAssistant
from homeassistant.helpers.aiohttp_client import async_get_clientsession

from .const import (
    CONF_HOST,
    CONF_HUB_ID,
    CONF_MOTOR_CODE,
    CONF_PORT,
    CONF_PROTOCOL,
    DEFAULT_PORT,
    DEFAULT_PROTOCOL,
    DOMAIN,
    PROTOCOL_HTTP,
)
from .hub import NeoHub

_LOGGER = logging.getLogger(__name__)

PLATFORMS: list[Platform] = [Platform.COVER]


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Set up Louvelite Blinds from a config entry."""
    data = entry.data
    hub = NeoHub(
        host=data[CONF_HOST],
        hub_id=data[CONF_HUB_ID],
        protocol=data.get(CONF_PROTOCOL, DEFAULT_PROTOCOL),
        port=data.get(CONF_PORT, DEFAULT_PORT),
        motor_code=data.get(CONF_MOTOR_CODE) or None,
        http_session=async_get_clientsession(hass)
        if data.get(CONF_PROTOCOL, DEFAULT_PROTOCOL) == PROTOCOL_HTTP
        else None,
    )

    hass.data.setdefault(DOMAIN, {})[entry.entry_id] = hub

    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)
    entry.async_on_unload(entry.add_update_listener(_async_update_listener))
    return True


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Unload a config entry."""
    unload_ok = await hass.config_entries.async_unload_platforms(entry, PLATFORMS)
    if unload_ok:
        hass.data[DOMAIN].pop(entry.entry_id, None)
    return unload_ok


async def _async_update_listener(hass: HomeAssistant, entry: ConfigEntry) -> None:
    """Reload entities when options change (remote/blind added or removed)."""
    await hass.config_entries.async_reload(entry.entry_id)
