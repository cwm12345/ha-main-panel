# Written by Claude, guided by Chris.
"""Config flow for the Main Panel integration.

No host/credentials to collect -- there's only one main panel, and its
data already lives in HA's own state machine (the native Shelly Pro 3EM
integration). The flow just confirms every source entity actually exists
before creating the entry, same "don't silently create a broken setup"
principle as a device integration that validates its connection.
"""

from __future__ import annotations

from typing import Any

import voluptuous as vol

from homeassistant import config_entries
from homeassistant.data_entry_flow import FlowResult

from .const import ALL_SOURCES, DOMAIN, UNIQUE_ID

EMPTY_SCHEMA = vol.Schema({})


class MainPanelConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    """Single config entry -- confirms the underlying Shelly entities exist."""

    VERSION = 1

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> FlowResult:
        await self.async_set_unique_id(UNIQUE_ID)
        self._abort_if_unique_id_configured()

        errors: dict[str, str] = {}
        if user_input is not None:
            missing = [src for src in ALL_SOURCES if self.hass.states.get(src) is None]
            if missing:
                errors["base"] = "cannot_connect"
            else:
                return self.async_create_entry(title="Main Panel", data={})

        return self.async_show_form(
            step_id="user", data_schema=EMPTY_SCHEMA, errors=errors
        )
