"""Data coordinators for the Noot Taxi Busje integration."""
from __future__ import annotations

import logging
from datetime import timedelta
from typing import Any

import aiohttp

from homeassistant.core import HomeAssistant
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed

from .api import NootApiError, NootScheduleApi, NootTrackingApi
from .const import DOMAIN

_LOGGER = logging.getLogger(__name__)


class NootScheduleCoordinator(DataUpdateCoordinator[dict[str, Any]]):
    """Poll the ride schedule of the portal."""

    def __init__(
        self,
        hass: HomeAssistant,
        api: NootScheduleApi,
        interval_seconds: int,
    ) -> None:
        """Initialise the coordinator."""
        super().__init__(
            hass,
            _LOGGER,
            name=f"{DOMAIN}_schedule",
            update_interval=timedelta(seconds=interval_seconds),
        )
        self.api = api

    async def _async_update_data(self) -> dict[str, Any]:
        """Fetch the schedule."""
        try:
            return await self.api.async_fetch_schedule()
        except NootApiError as err:
            raise UpdateFailed(str(err)) from err
        except (aiohttp.ClientError, TimeoutError) as err:
            raise UpdateFailed(f"Portal request failed: {err}") from err


class NootTrackingCoordinator(DataUpdateCoordinator[dict[str, Any]]):
    """Poll the live tracking data of the portal."""

    def __init__(
        self,
        hass: HomeAssistant,
        api: NootTrackingApi,
        interval_seconds: int,
    ) -> None:
        """Initialise the coordinator."""
        super().__init__(
            hass,
            _LOGGER,
            name=f"{DOMAIN}_tracking",
            update_interval=timedelta(seconds=interval_seconds),
        )
        self.api = api

    async def _async_update_data(self) -> dict[str, Any]:
        """Fetch the live tracking data."""
        try:
            return await self.api.async_fetch_tracking()
        except NootApiError as err:
            raise UpdateFailed(str(err)) from err
        except (aiohttp.ClientError, TimeoutError) as err:
            raise UpdateFailed(f"Portal request failed: {err}") from err
