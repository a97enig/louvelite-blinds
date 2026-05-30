"""Louvelite Blinds (Neo Smart Controller) integration."""
from __future__ import annotations

import logging

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import Platform
from homeassistant.core import HomeAssistant
from homeassistant.helpers.aiohttp_client import async_get_clientsession
from homeassistant.helpers.device_registry import DeviceEntry

from .const import (
    CONF_BLIND_ID,
    CONF_BLINDS,
    CONF_HOST,
    CONF_HUB_ID,
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


async def async_remove_config_entry_device(
    hass: HomeAssistant, entry: ConfigEntry, device: DeviceEntry
) -> bool:
    """Allow deleting a blind from its device page.

    Each blind's device identifier is `<entry_id>:<blind_id>`. We strip
    the blind out of the entry's options; the update listener picks it
    up and reloads, which removes any covers (both rails for TDBU) the
    device was hosting.
    """
    prefix = f"{entry.entry_id}:"
    blind_id = next(
        (
            ident[len(prefix):]
            for domain, ident in device.identifiers
            if domain == DOMAIN and ident.startswith(prefix)
        ),
        None,
    )
    if not blind_id:
        return False

    blinds = list(entry.options.get(CONF_BLINDS, []))
    kept = [b for b in blinds if b.get(CONF_BLIND_ID) != blind_id]
    if len(kept) == len(blinds):
        # Device isn't backed by anything we know about — treat as removable.
        return True

    new_options = dict(entry.options)
    new_options[CONF_BLINDS] = kept
    hass.config_entries.async_update_entry(entry, options=new_options)
    return True
