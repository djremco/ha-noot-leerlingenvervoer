"""Device tracker for the Noot Taxi Busje integration."""
from __future__ import annotations

from typing import Any

from homeassistant.components.device_tracker import SourceType, TrackerEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.util import dt as dt_util

from .coordinator import NootTrackingCoordinator
from .entity import NootTaxiBaseEntity
from .util import as_float, get_home_coordinates, get_school_coordinates


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up the device tracker."""
    tracking: NootTrackingCoordinator = entry.runtime_data.tracking
    async_add_entities([TaxiLocatieTracker(tracking, entry)])


class TaxiLocatieTracker(NootTaxiBaseEntity, TrackerEntity):
    """The position of the taxi.

    The portal does not always report GPS coordinates. When they are missing the
    tracker falls back to the school while a ride is running, and to home
    otherwise.
    """

    _attr_name = "Locatie"
    _attr_icon = "mdi:bus-school"

    def __init__(
        self, coordinator: NootTrackingCoordinator, entry: ConfigEntry
    ) -> None:
        """Initialise the tracker."""
        super().__init__(coordinator, entry, "locatie")

    @property
    def _data(self) -> dict[str, Any]:
        return self.coordinator.data

    @property
    def source_type(self) -> SourceType:
        """Return the source type."""
        return SourceType.GPS

    def _fallback(self) -> tuple[float | None, float | None]:
        """Return the position to use when the portal has no GPS coordinates.

        Priority:
        1. Drop-off (pickup/delivery) coordinates from the portal.
        2. Configured school coordinates.
        3. Home coordinates (from config or zone.home).
        """
        data = self._data
        today = dt_util.now().strftime("%d-%m-%y")

        if data.get("routedatum") == today:
            # Try the portal's own location first
            dropoff_lat = as_float(data.get("dropoff_lat"))
            dropoff_lon = as_float(data.get("dropoff_lon"))
            if dropoff_lat is not None and dropoff_lon is not None:
                return dropoff_lat, dropoff_lon

            pickup_lat = as_float(data.get("pickup_lat"))
            pickup_lon = as_float(data.get("pickup_lon"))
            if pickup_lat is not None and pickup_lon is not None:
                return pickup_lat, pickup_lon

            # Fall back to configured school coordinates
            direction = data.get("richting")
            completed = data.get("status") == "Voltooid"

            if direction == "Heen" and completed:
                return get_school_coordinates(self._entry)
            if direction == "Terug" and not completed:
                return get_school_coordinates(self._entry)

        home_latitude, home_longitude = get_home_coordinates(self.hass, self._entry)
        return home_latitude, home_longitude

    @property
    def latitude(self) -> float | None:
        """Return the latitude."""
        latitude = as_float(self._data.get("gps_lat"))
        if latitude is not None:
            return latitude
        return self._fallback()[0]

    @property
    def longitude(self) -> float | None:
        """Return the longitude."""
        longitude = as_float(self._data.get("gps_lon"))
        if longitude is not None:
            return longitude
        return self._fallback()[1]

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        """Return the GPS address and ride information."""
        data = self._data
        return {
            "gps_adres": data.get("gps_address", ""),
            "gps_tijdstip": data.get("gps_timestamp", ""),
            "richting": data.get("richting", ""),
            "ritnummer": data.get("routenr4", ""),
            "chauffeur": data.get("chauffeur", ""),
            "ophaaladres": data.get("pickup_address", ""),
            "afzetadres": data.get("dropoff_address", ""),
        }
