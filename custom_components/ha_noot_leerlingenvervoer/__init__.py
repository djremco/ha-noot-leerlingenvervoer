"""The Noot Leerlingenvervoer integration."""
from __future__ import annotations

import logging
from dataclasses import dataclass

import aiohttp

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import Platform
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryNotReady
from homeassistant.helpers.aiohttp_client import async_create_clientsession

from .const import (
    CONF_COMPANY,
    CONF_KLANTNR,
    CONF_PASSWORD,
    CONF_SCHEMA_INTERVAL,
    CONF_TRACKING_INTERVAL,
    CONF_USERNAME,
    DEFAULT_COMPANY,
    DEFAULT_SCHEMA_INTERVAL,
    DEFAULT_TRACKING_INTERVAL,
    DOMAIN,
    MIN_SCHEMA_INTERVAL,
    MIN_TRACKING_INTERVAL,
)
from .coordinator import NootScheduleCoordinator, NootTrackingCoordinator
from .api import NootScheduleApi, NootTrackingApi

_LOGGER = logging.getLogger(__name__)

PLATFORMS: list[Platform] = [
    Platform.SENSOR,
    Platform.BINARY_SENSOR,
    Platform.DEVICE_TRACKER,
]


@dataclass
class NootTaxiRuntimeData:
    """Runtime data of a config entry."""

    schedule: NootScheduleCoordinator
    tracking: NootTrackingCoordinator
    schedule_session: aiohttp.ClientSession
    tracking_session: aiohttp.ClientSession


def _interval(value: object, default: int, minimum: int = 1) -> int:
    """Return a usable update interval, clamped to at least minimum."""
    try:
        interval = int(value)  # type: ignore[arg-type]
    except (TypeError, ValueError):
        return default
    return max(interval, minimum) if interval > 0 else default


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Set up the integration from a config entry."""
    username = entry.data[CONF_USERNAME]
    password = entry.data[CONF_PASSWORD]
    klantnr = entry.data.get(CONF_KLANTNR, "").strip()
    company = entry.data.get(CONF_COMPANY) or DEFAULT_COMPANY

    if not klantnr:
        # Auto-detect klantnr from the portal during setup
        _LOGGER.info("No klantnr configured, detecting from portal...")
        session = aiohttp.ClientSession()
        try:
            tracking_api = NootTrackingApi(session, username, password)
            klantnr = await tracking_api.async_login()
            _LOGGER.info("Auto-detected klantnr: %s", klantnr)
        except Exception:
            await session.close()
            raise ConfigEntryNotReady(
                "Could not detect customer number (klantnr)"
            ) from None
        else:
            await session.close()

    schedule_session = async_create_clientsession(hass)
    tracking_session = async_create_clientsession(hass)

    schedule = NootScheduleCoordinator(
        hass,
        NootScheduleApi(schedule_session, username, password, klantnr, company),
        _interval(
            entry.options.get(CONF_SCHEMA_INTERVAL),
            DEFAULT_SCHEMA_INTERVAL,
            MIN_SCHEMA_INTERVAL,
        ),
    )
    tracking = NootTrackingCoordinator(
        hass,
        NootTrackingApi(tracking_session, username, password),
        _interval(
            entry.options.get(CONF_TRACKING_INTERVAL),
            DEFAULT_TRACKING_INTERVAL,
            MIN_TRACKING_INTERVAL,
        ),
    )

    try:
        await schedule.async_config_entry_first_refresh()
        await tracking.async_config_entry_first_refresh()
    except Exception:
        await schedule_session.close()
        await tracking_session.close()
        raise

    entry.runtime_data = NootTaxiRuntimeData(
        schedule=schedule,
        tracking=tracking,
        schedule_session=schedule_session,
        tracking_session=tracking_session,
    )

    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)
    entry.async_on_unload(entry.add_update_listener(async_reload_entry))
    return True


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Unload a config entry."""
    unloaded = await hass.config_entries.async_unload_platforms(entry, PLATFORMS)
    if unloaded:
        runtime = entry.runtime_data
        await runtime.schedule_session.close()
        await runtime.tracking_session.close()
    return unloaded


async def async_reload_entry(hass: HomeAssistant, entry: ConfigEntry) -> None:
    """Reload the entry after its options changed."""
    await hass.config_entries.async_reload(entry.entry_id)
