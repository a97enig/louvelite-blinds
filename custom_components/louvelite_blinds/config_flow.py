"""Config flow for Louvelite Blinds (Neo Smart Controller)."""
from __future__ import annotations

import logging
import re
import uuid
from typing import Any

import voluptuous as vol

from homeassistant import config_entries
from homeassistant.config_entries import ConfigEntry, OptionsFlow
from homeassistant.core import callback
from homeassistant.data_entry_flow import FlowResult
from homeassistant.helpers.aiohttp_client import async_get_clientsession
from homeassistant.helpers.selector import (
    SelectOptionDict,
    SelectSelector,
    SelectSelectorConfig,
    SelectSelectorMode,
)

from .const import (
    BLIND_TYPE_ROLLER,
    BLIND_TYPE_TDBU,
    BLIND_TYPE_VENETIAN,
    BLIND_TYPES,
    CONF_BLIND_ID,
    CONF_BLIND_TYPE,
    CONF_BLINDS,
    CONF_CHANNEL,
    CONF_CLOSE_TIME,
    CONF_HOST,
    CONF_HUB_ID,
    CONF_MOTOR_CODE,
    CONF_NAME,
    CONF_PORT,
    CONF_PREFIX,
    CONF_PROTOCOL,
    CONF_REMOTE_ID,
    CONF_REMOTE_LABEL,
    CONF_REMOTE_MODEL,
    CONF_REMOTES,
    CONF_ROOM,
    DEFAULT_CLOSE_TIME,
    DEFAULT_HTTP_PORT,
    DEFAULT_PORT,
    DEFAULT_PROTOCOL,
    DEFAULT_TCP_PORT,
    DOMAIN,
    MAX_CHANNEL,
    MIN_CHANNEL,
    PROTOCOL_HTTP,
    PROTOCOL_TCP,
)


BLIND_TYPE_SELECTOR = SelectSelector(
    SelectSelectorConfig(
        options=[
            SelectOptionDict(
                value=BLIND_TYPE_ROLLER,
                label="Standard (roller / roman / pleated / cellular / vision / visage)",
            ),
            SelectOptionDict(
                value=BLIND_TYPE_VENETIAN,
                label="Venetian (slat blinds with tilt)",
            ),
            SelectOptionDict(
                value=BLIND_TYPE_TDBU,
                label="Top-Down / Bottom-Up (two rails)",
            ),
        ],
        mode=SelectSelectorMode.DROPDOWN,
    )
)
from .hub import NeoHub, NeoHubError

_LOGGER = logging.getLogger(__name__)

PREFIX_RE = re.compile(r"^\d{1,3}\.\d{1,3}$")
HUB_ID_RE = re.compile(r"^\S{24}$")


def _normalise_prefix(prefix: str) -> str:
    """Pad each byte of an ID1.ID2 prefix to 3 digits."""
    a, b = prefix.split(".")
    return f"{int(a):03d}.{int(b):03d}"


def _hub_schema(defaults: dict[str, Any] | None = None) -> vol.Schema:
    d = defaults or {}
    return vol.Schema(
        {
            vol.Required(CONF_HOST, default=d.get(CONF_HOST, "")): str,
            vol.Required(CONF_HUB_ID, default=d.get(CONF_HUB_ID, "")): str,
            vol.Required(
                CONF_PROTOCOL, default=d.get(CONF_PROTOCOL, DEFAULT_PROTOCOL)
            ): vol.In([PROTOCOL_HTTP, PROTOCOL_TCP]),
            vol.Required(CONF_PORT, default=d.get(CONF_PORT, DEFAULT_PORT)): int,
        }
    )


class LouveliteConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    """Initial setup: hub connection details."""

    VERSION = 1

    async def async_step_user(self, user_input: dict[str, Any] | None = None) -> FlowResult:
        errors: dict[str, str] = {}
        if user_input is not None:
            cleaned, errors = _validate_hub_input(user_input)
            if not errors:
                await self.async_set_unique_id(cleaned[CONF_HUB_ID].lower())
                self._abort_if_unique_id_configured(updates=cleaned)
                # Probe before saving so wrong IP/port fails loudly here, not later.
                session = (
                    async_get_clientsession(self.hass)
                    if cleaned[CONF_PROTOCOL] == PROTOCOL_HTTP
                    else None
                )
                hub = NeoHub(
                    host=cleaned[CONF_HOST],
                    hub_id=cleaned[CONF_HUB_ID],
                    protocol=cleaned[CONF_PROTOCOL],
                    port=cleaned[CONF_PORT],
                    http_session=session,
                )
                try:
                    await hub.async_probe()
                except NeoHubError as err:
                    _LOGGER.warning("Hub probe failed: %s", err)
                    errors["base"] = "cannot_connect"
                else:
                    return self.async_create_entry(
                        title=f"Neo Hub @ {cleaned[CONF_HOST]}",
                        data=cleaned,
                        options={CONF_REMOTES: [], CONF_BLINDS: []},
                    )
        return self.async_show_form(
            step_id="user", data_schema=_hub_schema(user_input), errors=errors
        )

    @staticmethod
    @callback
    def async_get_options_flow(entry: ConfigEntry) -> OptionsFlow:
        return LouveliteOptionsFlow(entry)


def _validate_hub_input(user_input: dict[str, Any]) -> tuple[dict[str, Any], dict[str, str]]:
    errors: dict[str, str] = {}
    cleaned = dict(user_input)

    host = (cleaned.get(CONF_HOST) or "").strip()
    if not host:
        errors[CONF_HOST] = "host_required"
    cleaned[CONF_HOST] = host

    hub_id = (cleaned.get(CONF_HUB_ID) or "").strip()
    if not HUB_ID_RE.match(hub_id):
        errors[CONF_HUB_ID] = "hub_id_invalid"
    cleaned[CONF_HUB_ID] = hub_id

    protocol = cleaned.get(CONF_PROTOCOL, DEFAULT_PROTOCOL)
    if protocol not in (PROTOCOL_HTTP, PROTOCOL_TCP):
        errors[CONF_PROTOCOL] = "protocol_invalid"
    cleaned[CONF_PROTOCOL] = protocol

    port = cleaned.get(CONF_PORT)
    if not isinstance(port, int) or port <= 0 or port > 65535:
        errors[CONF_PORT] = "port_invalid"

    return cleaned, errors


class LouveliteOptionsFlow(OptionsFlow):
    """Options menu: add/remove remotes and blinds, edit hub."""

    def __init__(self, entry: ConfigEntry) -> None:
        self._entry = entry

    @property
    def _remotes(self) -> list[dict[str, Any]]:
        return list(self._entry.options.get(CONF_REMOTES, []))

    @property
    def _blinds(self) -> list[dict[str, Any]]:
        return list(self._entry.options.get(CONF_BLINDS, []))

    def _save_options(self, *, remotes=None, blinds=None) -> FlowResult:
        new = dict(self._entry.options)
        new[CONF_REMOTES] = self._remotes if remotes is None else remotes
        new[CONF_BLINDS] = self._blinds if blinds is None else blinds
        return self.async_create_entry(title="", data=new)

    # --- main menu -------------------------------------------------------

    async def async_step_init(self, user_input: dict[str, Any] | None = None) -> FlowResult:
        return self.async_show_menu(
            step_id="init",
            menu_options=[
                "add_remote",
                "remove_remote",
                "add_blind",
                "remove_blind",
                "edit_hub",
            ],
        )

    # --- hub edit --------------------------------------------------------

    async def async_step_edit_hub(self, user_input: dict[str, Any] | None = None) -> FlowResult:
        errors: dict[str, str] = {}
        if user_input is not None:
            cleaned, errors = _validate_hub_input(user_input)
            if not errors:
                self.hass.config_entries.async_update_entry(self._entry, data=cleaned)
                return self.async_create_entry(title="", data=dict(self._entry.options))
        return self.async_show_form(
            step_id="edit_hub",
            data_schema=_hub_schema(user_input or self._entry.data),
            errors=errors,
        )

    # --- remotes ---------------------------------------------------------

    async def async_step_add_remote(self, user_input: dict[str, Any] | None = None) -> FlowResult:
        errors: dict[str, str] = {}
        if user_input is not None:
            label = (user_input.get(CONF_REMOTE_LABEL) or "").strip()
            prefix = (user_input.get(CONF_PREFIX) or "").strip()
            model = (user_input.get(CONF_REMOTE_MODEL) or "").strip()
            if not label:
                errors[CONF_REMOTE_LABEL] = "label_required"
            if not PREFIX_RE.match(prefix):
                errors[CONF_PREFIX] = "prefix_invalid"
            else:
                prefix = _normalise_prefix(prefix)
                if any(r[CONF_PREFIX] == prefix for r in self._remotes):
                    errors[CONF_PREFIX] = "prefix_exists"
            if not errors:
                new_remote = {
                    CONF_REMOTE_ID: uuid.uuid4().hex,
                    CONF_REMOTE_LABEL: label,
                    CONF_PREFIX: prefix,
                    CONF_REMOTE_MODEL: model,
                }
                return self._save_options(remotes=self._remotes + [new_remote])
        return self.async_show_form(
            step_id="add_remote",
            data_schema=vol.Schema(
                {
                    vol.Required(CONF_REMOTE_LABEL): str,
                    vol.Required(CONF_PREFIX): str,
                    vol.Optional(CONF_REMOTE_MODEL, default=""): str,
                }
            ),
            errors=errors,
            description_placeholders={"example": "021.230"},
        )

    async def async_step_remove_remote(self, user_input: dict[str, Any] | None = None) -> FlowResult:
        remotes = self._remotes
        if not remotes:
            return self.async_abort(reason="no_remotes")
        choices = {r[CONF_REMOTE_ID]: f"{r[CONF_REMOTE_LABEL]} ({r[CONF_PREFIX]})" for r in remotes}
        if user_input is not None:
            rid = user_input[CONF_REMOTE_ID]
            kept_remotes = [r for r in remotes if r[CONF_REMOTE_ID] != rid]
            kept_blinds = [b for b in self._blinds if b.get(CONF_REMOTE_ID) != rid]
            return self._save_options(remotes=kept_remotes, blinds=kept_blinds)
        return self.async_show_form(
            step_id="remove_remote",
            data_schema=vol.Schema({vol.Required(CONF_REMOTE_ID): vol.In(choices)}),
        )

    # --- blinds ----------------------------------------------------------

    async def async_step_add_blind(self, user_input: dict[str, Any] | None = None) -> FlowResult:
        remotes = self._remotes
        if not remotes:
            return self.async_abort(reason="no_remotes")
        remote_choices = {
            r[CONF_REMOTE_ID]: f"{r[CONF_REMOTE_LABEL]} ({r[CONF_PREFIX]})" for r in remotes
        }
        errors: dict[str, str] = {}
        if user_input is not None:
            name = (user_input.get(CONF_NAME) or "").strip()
            room = (user_input.get(CONF_ROOM) or "").strip()
            rid = user_input.get(CONF_REMOTE_ID)
            channel = user_input.get(CONF_CHANNEL)
            blind_type = user_input.get(CONF_BLIND_TYPE)
            close_time = user_input.get(CONF_CLOSE_TIME, DEFAULT_CLOSE_TIME)
            motor_code = (user_input.get(CONF_MOTOR_CODE) or "").strip().lower()

            if not name:
                errors[CONF_NAME] = "name_required"
            if rid not in remote_choices:
                errors[CONF_REMOTE_ID] = "remote_invalid"
            if not isinstance(channel, int) or channel < MIN_CHANNEL or channel > MAX_CHANNEL:
                errors[CONF_CHANNEL] = "channel_invalid"
            if blind_type not in BLIND_TYPES:
                errors[CONF_BLIND_TYPE] = "type_invalid"
            if not errors:
                # Prevent duplicate (remote, channel) entries.
                if any(
                    b[CONF_REMOTE_ID] == rid and b[CONF_CHANNEL] == channel
                    for b in self._blinds
                ):
                    errors[CONF_CHANNEL] = "blind_exists"
            if not errors:
                new_blind = {
                    CONF_BLIND_ID: uuid.uuid4().hex,
                    CONF_NAME: name,
                    CONF_ROOM: room,
                    CONF_REMOTE_ID: rid,
                    CONF_CHANNEL: channel,
                    CONF_BLIND_TYPE: blind_type,
                    CONF_CLOSE_TIME: int(close_time),
                    CONF_MOTOR_CODE: motor_code,
                }
                return self._save_options(blinds=self._blinds + [new_blind])
        defaults = user_input or {}
        return self.async_show_form(
            step_id="add_blind",
            data_schema=vol.Schema(
                {
                    vol.Required(CONF_NAME, default=defaults.get(CONF_NAME, "")): str,
                    vol.Optional(CONF_ROOM, default=defaults.get(CONF_ROOM, "")): str,
                    vol.Required(
                        CONF_REMOTE_ID,
                        default=defaults.get(CONF_REMOTE_ID, next(iter(remote_choices))),
                    ): vol.In(remote_choices),
                    vol.Required(
                        CONF_CHANNEL, default=defaults.get(CONF_CHANNEL, 1)
                    ): vol.All(int, vol.Range(min=MIN_CHANNEL, max=MAX_CHANNEL)),
                    vol.Required(
                        CONF_BLIND_TYPE,
                        default=defaults.get(CONF_BLIND_TYPE, BLIND_TYPE_ROLLER),
                    ): BLIND_TYPE_SELECTOR,
                    vol.Required(
                        CONF_CLOSE_TIME,
                        default=defaults.get(CONF_CLOSE_TIME, DEFAULT_CLOSE_TIME),
                    ): vol.All(int, vol.Range(min=1, max=600)),
                    vol.Optional(
                        CONF_MOTOR_CODE,
                        default=defaults.get(CONF_MOTOR_CODE, ""),
                    ): str,
                }
            ),
            errors=errors,
        )

    async def async_step_remove_blind(self, user_input: dict[str, Any] | None = None) -> FlowResult:
        blinds = self._blinds
        if not blinds:
            return self.async_abort(reason="no_blinds")
        remote_labels = {r[CONF_REMOTE_ID]: r[CONF_REMOTE_LABEL] for r in self._remotes}
        choices = {
            b[CONF_BLIND_ID]: (
                f"{b[CONF_NAME]} "
                f"[{remote_labels.get(b[CONF_REMOTE_ID], '?')} ch {b[CONF_CHANNEL]:02d}]"
            )
            for b in blinds
        }
        if user_input is not None:
            bid = user_input[CONF_BLIND_ID]
            kept = [b for b in blinds if b[CONF_BLIND_ID] != bid]
            return self._save_options(blinds=kept)
        return self.async_show_form(
            step_id="remove_blind",
            data_schema=vol.Schema({vol.Required(CONF_BLIND_ID): vol.In(choices)}),
        )
