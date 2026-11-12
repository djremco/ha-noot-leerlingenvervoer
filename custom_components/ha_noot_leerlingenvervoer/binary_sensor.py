"""Binary sensors for the Noot Taxi Busje integration."""
from __future__ import annotations

from datetime import timedelta
from typing import Any

from homeassistant.components.binary_sensor import (
    BinarySensorDeviceClass,
    BinarySensorEntity,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.util import dt as dt_util

from .const import CONF_NEAR_HOME_KM, DEFAULT_NEAR_HOME_KM
from .coordinator import NootTrackingCoordinator
from .entity import NootTaxiBaseEntity
from .util import as_float, distance_km, get_home_coordinates


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up the binary sensors."""
    tracking: NootTrackingCoordinator = entry.runtime_data.tracking
    async_add_entities(
        [
            InBusMiddagritSensor(tracking, entry),
            OchtendritBinnenkortSensor(tracking, entry),
            BijnaThuisSensor(tracking, entry),
            AanwezigGemeldSensor(tracking, entry),
        ]
    )


class NootTaxiBinarySensor(NootTaxiBaseEntity, BinarySensorEntity):
    """Base binary sensor for the integration."""

    def __init__(
        self, coordinator: NootTrackingCoordinator, entry: ConfigEntry, key: str
    ) -> None:
        """Initialise the binary sensor."""
        super().__init__(coordinator, entry, key)

    @property
    def _data(self) -> dict[str, Any]:
        return self.coordinator.data


class InBusMiddagritSensor(NootTaxiBinarySensor):
    """True while the afternoon ride is in progress."""

    _attr_name = "In Bus Middagrit"
    _attr_icon = "mdi:bus"

    def __init__(
        self, coordinator: NootTrackingCoordinator, entry: ConfigEntry
    ) -> None:
        """Initialise the binary sensor."""
        super().__init__(coordinator, entry, "in_bus_middagrit")

    @property
    def is_on(self) -> bool:
        """Return True when the child is in the afternoon bus."""
        data = self._data
        return (
            data.get("routedatum") == dt_util.now().strftime("%d-%m-%y")
            and data.get("richting") == "Terug"
            and data.get("status_code") == "110"
        )


class OchtendritBinnenkortSensor(NootTaxiBinarySensor):
    """True shortly before and around the morning pickup."""

    _attr_name = "Ochtendrit Binnenkort"
    _attr_icon = "mdi:bus-clock"

    def __init__(
        self, coordinator: NootTrackingCoordinator, entry: ConfigEntry
    ) -> None:
        """Initialise the binary sensor."""
        super().__init__(coordinator, entry, "ochtendrit_binnenkort")

    @property
    def is_on(self) -> bool:
        """Return True within the morning pickup window."""
        data = self._data
        if (
            data.get("routedatum") != dt_util.now().strftime("%d-%m-%y")
            or data.get("richting") != "Heen"
        ):
            return False

        pickup_time = data.get("pickup_time")
        if not pickup_time:
            return False

        now = dt_util.now()
        start = dt_util.today_at(pickup_time) - timedelta(minutes=10)
        boarded = data.get("instap_tijd") or pickup_time
        end = dt_util.today_at(boarded) + timedelta(minutes=5)
        return start < now < end


class BijnaThuisSensor(NootTaxiBinarySensor):
    """True when the afternoon bus is close to home."""

    _attr_name = "Bijna Thuis"
    _attr_icon = "mdi:bus-clock"
    _attr_device_class = BinarySensorDeviceClass.PRESENCE

    def __init__(
        self, coordinator: NootTrackingCoordinator, entry: ConfigEntry
    ) -> None:
        """Initialise the binary sensor."""
        super().__init__(coordinator, entry, "bijna_thuis")

    @property
    def _distance(self) -> float | None:
        data = self._data
        if data.get("status_code") != "110" or data.get("richting") != "Terug":
            return None

        latitude = as_float(data.get("gps_lat"))
        longitude = as_float(data.get("gps_lon"))
        home_latitude, home_longitude = get_home_coordinates(self.hass, self._entry)
        return distance_km(latitude, longitude, home_latitude, home_longitude)

    @property
    def is_on(self) -> bool:
        """Return True when the bus is within the configured distance."""
        distance = self._distance
        if distance is None:
            return False
        threshold = as_float(
            self._entry.options.get(CONF_NEAR_HOME_KM, DEFAULT_NEAR_HOME_KM)
        )
        return distance <= (threshold if threshold is not None else DEFAULT_NEAR_HOME_KM)

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        """Return the measured distance."""
        distance = self._distance
        return {"afstand_km": round(distance, 2) if distance is not None else None}


class AanwezigGemeldSensor(NootTaxiBinarySensor):
    """True when the child is marked as present."""

    _attr_name = "Aanwezig Gemeld"
    _attr_icon = "mdi:account-check"
    _attr_device_class = BinarySensorDeviceClass.OCCUPANCY

    def __init__(
        self, coordinator: NootTrackingCoordinator, entry: ConfigEntry
    ) -> None:
        """Initialise the binary sensor."""
        super().__init__(coordinator, entry, "aanwezig_gemeld")

    @property
    def is_on(self) -> bool:
        """Return True when the portal reports the child as present."""
        return self._data.get("absentiestatus", "") == "Aanwezig"
