"""Config flow for Noot Leerlingenvervoer."""
from __future__ import annotations

from typing import Any

import voluptuous as vol

from homeassistant import config_entries
from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import FlowResult
from homeassistant.helpers.selector import selector

from .const import DOMAIN, NAME

STEP_USER_DATA_SCHEMA = vol.Schema(
    {
        vol.Required("username"): str,
        vol.Required("password"): str,
    }
)


class NootTaxiBusjeConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    """Handle a config flow for Noot Leerlingenvervoer."""

    VERSION = 1

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> FlowResult:
        """Handle the initial step."""
        errors: dict[str, str] = {}

        if user_input is not None:
            await self.async_set_unique_id(f"{DOMAIN}_{user_input['username']}")
            self._abort_if_unique_id_configured()
            return self.async_create_entry(
                title=NAME,
                data=user_input,
            )

        return self.async_show_form(
            step_id="user",
            data_schema=STEP_USER_DATA_SCHEMA,
            errors=errors,
        )