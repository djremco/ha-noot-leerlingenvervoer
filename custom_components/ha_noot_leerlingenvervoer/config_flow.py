"""Config flow for Noot Leerlingenvervoer."""
from __future__ import annotations

from typing import Any

import voluptuous as vol

from homeassistant import config_entries
from homeassistant.config_entries import ConfigEntry, OptionsFlow
from homeassistant.core import callback
from homeassistant.data_entry_flow import FlowResult

from .const import (
    CONF_KLANTNR,
    CONF_NEAR_HOME_KM,
    CONF_SCHEMA_INTERVAL,
    CONF_TRACKING_INTERVAL,
    DEFAULT_NEAR_HOME_KM,
    DEFAULT_SCHEMA_INTERVAL,
    DEFAULT_TRACKING_INTERVAL,
    DOMAIN,
    MIN_SCHEMA_INTERVAL,
    MIN_TRACKING_INTERVAL,
    NAME,
)

STEP_USER_DATA_SCHEMA = vol.Schema(
    {
        vol.Required("username"): str,
        vol.Required("password"): str,
    }
)

ADVANCED_SCHEMA = vol.Schema(
    {
        vol.Optional(
            CONF_SCHEMA_INTERVAL,
            default=DEFAULT_SCHEMA_INTERVAL,
        ): vol.All(vol.Coerce(int), vol.Range(min=MIN_SCHEMA_INTERVAL, max=86400)),
        vol.Optional(
            CONF_TRACKING_INTERVAL,
            default=DEFAULT_TRACKING_INTERVAL,
        ): vol.All(vol.Coerce(int), vol.Range(min=MIN_TRACKING_INTERVAL, max=3600)),
        vol.Optional(
            CONF_NEAR_HOME_KM,
            default=DEFAULT_NEAR_HOME_KM,
        ): vol.All(vol.Coerce(float), vol.Range(min=0.1, max=50)),
    }
)


class NootTaxiBusjeConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    """Handle a config flow for Noot Leerlingenvervoer."""

    VERSION = 1

    def __init__(self) -> None:
        self._credentials: dict[str, Any] = {}

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> FlowResult:
        """Handle the initial step."""
        errors: dict[str, str] = {}

        if user_input is not None:
            await self.async_set_unique_id(f"{DOMAIN}_{user_input['username']}")
            self._abort_if_unique_id_configured()
            self._credentials = {
                "username": user_input["username"],
                "password": user_input["password"],
                CONF_KLANTNR: user_input.get(CONF_KLANTNR, ""),
            }
            return await self.async_step_advanced()

        return self.async_show_form(
            step_id="user",
            data_schema=STEP_USER_DATA_SCHEMA,
            errors=errors,
        )

    async def async_step_advanced(
        self, user_input: dict[str, Any] | None = None
    ) -> FlowResult:
        """Handle the tuning step."""
        if user_input is not None:
            return self.async_create_entry(
                title=NAME,
                data=self._credentials,
                options=user_input,
            )
        return self.async_show_form(
            step_id="advanced",
            data_schema=ADVANCED_SCHEMA,
        )

    @staticmethod
    @callback
    def async_get_options_flow(config_entry: ConfigEntry) -> OptionsFlow:
        return NootTaxiBusjeOptionsFlow()


class NootTaxiBusjeOptionsFlow(OptionsFlow):
    """Allow options to be changed later."""

    async def async_step_init(
        self, user_input: dict[str, Any] | None = None
    ) -> FlowResult:
        if user_input is not None:
            return self.async_create_entry(title="", data=user_input)
        return self.async_show_form(
            step_id="init",
            data_schema=self._schema_with_defaults(),
        )

    def _schema_with_defaults(self) -> vol.Schema:
        entry = self.config_entry
        return vol.Schema(
            {
                vol.Optional(
                    CONF_SCHEMA_INTERVAL,
                    default=entry.options.get(CONF_SCHEMA_INTERVAL, DEFAULT_SCHEMA_INTERVAL),
                ): vol.All(vol.Coerce(int), vol.Range(min=MIN_SCHEMA_INTERVAL, max=86400)),
                vol.Optional(
                    CONF_TRACKING_INTERVAL,
                    default=entry.options.get(CONF_TRACKING_INTERVAL, DEFAULT_TRACKING_INTERVAL),
                ): vol.All(vol.Coerce(int), vol.Range(min=MIN_TRACKING_INTERVAL, max=3600)),
                vol.Optional(
                    CONF_NEAR_HOME_KM,
                    default=entry.options.get(CONF_NEAR_HOME_KM, DEFAULT_NEAR_HOME_KM),
                ): vol.All(vol.Coerce(float), vol.Range(min=0.1, max=50)),
            }
        )