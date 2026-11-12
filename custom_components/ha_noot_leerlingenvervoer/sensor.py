"""Sensor platform for the Noot Taxi Busje integration."""
from __future__ import annotations

from typing import Any

from homeassistant.components.sensor import SensorEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.util import dt as dt_util

from .api import minutes_until_iso
from .coordinator import NootScheduleCoordinator, NootTrackingCoordinator
from .entity import NootTaxiBaseEntity

DAY_PARTS: tuple[tuple[str, str], ...] = (
    ("MAANDAG", "ochtend"),
    ("MAANDAG", "middag"),
    ("DINSDAG", "ochtend"),
    ("DINSDAG", "middag"),
    ("WOENSDAG", "ochtend"),
    ("WOENSDAG", "middag"),
    ("DONDERDAG", "ochtend"),
    ("DONDERDAG", "middag"),
    ("VRIJDAG", "ochtend"),
    ("VRIJDAG", "middag"),
)

DAY_NAMES = {
    "MAANDAG": "Maandag",
    "DINSDAG": "Dinsdag",
    "WOENSDAG": "Woensdag",
    "DONDERDAG": "Donderdag",
    "VRIJDAG": "Vrijdag",
}


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up the sensors."""
    schedule: NootScheduleCoordinator = entry.runtime_data.schedule
    tracking: NootTrackingCoordinator = entry.runtime_data.tracking

    entities: list[SensorEntity] = [
        RitStatusNuSensor(schedule, entry),
        VolgendeOchtendritSensor(schedule, entry),
        VolgendeMiddagritSensor(schedule, entry),
        EerstvolgendeRitSensor(schedule, entry),
        RittenVandaagSensor(schedule, entry),
        ChauffeurSensor(schedule, entry),
        AfzettijdSensor(schedule, entry),
        DatumSensor(schedule, entry),
        DagSensor(schedule, entry),
        StatusSensor(schedule, entry),
        MinutenTotRitSensor(schedule, entry),
        LiveTrackingSensor(tracking, entry),
        ETASensor(tracking, entry),
    ]
    entities.extend(
        DagdeelSensor(schedule, entry, day, slot) for day, slot in DAY_PARTS
    )

    async_add_entities(entities)


def _rides(data: dict[str, Any]) -> list[dict[str, Any]]:
    """Return all rides from the coordinator data."""
    return data.get("all_rides", [])


def _upcoming_ride(data: dict[str, Any]) -> dict[str, Any]:
    """Return the ride that starts first, morning or afternoon."""
    candidates = [
        ride
        for ride in (data.get("next_morning"), data.get("next_afternoon"))
        if ride and ride.get("available") and ride.get("datetime")
    ]
    if not candidates:
        return {}
    return min(
        candidates,
        key=lambda ride: dt_util.parse_datetime(ride["datetime"]) or dt_util.now(),
    )


def _ride_attributes(ride: dict[str, Any]) -> dict[str, Any]:
    """Return the attributes shared by all ride sensors."""
    return {
        "datum": ride.get("date", ""),
        "dag": ride.get("day", ""),
        "ophaaladres": ride.get("address", ""),
        "school": ride.get("school", ""),
        "chauffeur": ride.get("driver", ""),
        "ritnummer": ride.get("route", ""),
        "status": ride.get("status", ""),
        "afzettijd": ride.get("dropoff_time", ""),
        "minuten_tot_rit": minutes_until_iso(ride.get("datetime", "")),
    }


class NootTaxiSensor(NootTaxiBaseEntity, SensorEntity):
    """Base sensor for the integration."""


class RitStatusNuSensor(NootTaxiSensor):
    """The status of the ride that is happening right now."""

    _attr_name = "Rit Status Nu"
    _attr_icon = "mdi:bus"

    def __init__(
        self, coordinator: NootScheduleCoordinator, entry: ConfigEntry
    ) -> None:
        """Initialise the sensor."""
        super().__init__(coordinator, entry, "rit_status_nu")

    def _today_rides(self) -> list[dict[str, Any]]:
        today = dt_util.now().strftime("%d-%m-%y")
        return [ride for ride in _rides(self.coordinator.data) if ride.get("date") == today]

    @property
    def native_value(self) -> str:
        """Return the status of the last ride that already started."""
        rides = self._today_rides()
        if not rides:
            return "Geen rit"

        now_time = dt_util.now().strftime("%H:%M")
        started = [
            ride
            for ride in rides
            if ride.get("time", "99:99") <= now_time and ride.get("status")
        ]
        return started[-1].get("status", "Onbekend") if started else "Geen rit"

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        """Return the previous and next ride of today."""
        rides = self._today_rides()
        now_time = dt_util.now().strftime("%H:%M")

        past = [ride for ride in rides if ride.get("time", "99:99") <= now_time]
        upcoming = [ride for ride in rides if ride.get("time", "00:00") > now_time]

        attributes: dict[str, Any] = {}
        if upcoming:
            next_ride = upcoming[0]
            attributes["volgende_rit"] = (
                f"{next_ride.get('time', '?')} - {next_ride.get('driver', '?')}"
            )
            attributes["minuten_tot_volgende"] = minutes_until_iso(
                next_ride.get("datetime", "")
            )
        else:
            attributes["volgende_rit"] = "Geen rit meer vandaag"
            attributes["minuten_tot_volgende"] = -1

        if past:
            previous = past[-1]
            attributes["vorige_rit"] = (
                f"{previous.get('time', '?')} - {previous.get('driver', '?')} "
                f"({previous.get('status', '')})"
            )
        else:
            attributes["vorige_rit"] = "Nog geen rit vandaag"

        return attributes


class _NextRideSensor(NootTaxiSensor):
    """Base sensor for the next morning or afternoon ride."""

    _attr_icon = "mdi:bus-school"
    _ride_key: str = "next_morning"

    @property
    def _ride(self) -> dict[str, Any]:
        return self.coordinator.data.get(self._ride_key) or {}

    @property
    def native_value(self) -> str:
        """Return the pickup time."""
        ride = self._ride
        if ride.get("available"):
            return ride.get("time") or "Onbekend"
        return "Geen rit"

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        """Return the ride details."""
        ride = self._ride
        if not ride.get("available"):
            return {}
        return _ride_attributes(ride)


class VolgendeOchtendritSensor(_NextRideSensor):
    """The next morning ride."""

    _attr_name = "Volgende Ochtendrit"
    _ride_key = "next_morning"

    def __init__(
        self, coordinator: NootScheduleCoordinator, entry: ConfigEntry
    ) -> None:
        """Initialise the sensor."""
        super().__init__(coordinator, entry, "volgende_ochtendrit")


class VolgendeMiddagritSensor(_NextRideSensor):
    """The next afternoon ride."""

    _attr_name = "Volgende Middagrit"
    _ride_key = "next_afternoon"

    def __init__(
        self, coordinator: NootScheduleCoordinator, entry: ConfigEntry
    ) -> None:
        """Initialise the sensor."""
        super().__init__(coordinator, entry, "volgende_middagrit")


class EerstvolgendeRitSensor(NootTaxiSensor):
    """The ride that starts first, morning or afternoon."""

    _attr_name = "Eerstvolgende Rit"
    _attr_icon = "mdi:bus-school"

    def __init__(
        self, coordinator: NootScheduleCoordinator, entry: ConfigEntry
    ) -> None:
        """Initialise the sensor."""
        super().__init__(coordinator, entry, "eerstvolgende_rit")

    @property
    def native_value(self) -> str:
        """Return the pickup time."""
        ride = _upcoming_ride(self.coordinator.data)
        if ride:
            return ride.get("time") or "Onbekend"
        return "Geen rit"

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        """Return the ride details."""
        ride = _upcoming_ride(self.coordinator.data)
        if not ride:
            return {}
        attributes = _ride_attributes(ride)
        try:
            attributes["soort"] = (
                "ochtend" if int(ride.get("time", "0:0").split(":")[0]) < 12 else "middag"
            )
        except (ValueError, IndexError):
            attributes["soort"] = ""
        return attributes


class RittenVandaagSensor(NootTaxiSensor):
    """The number of rides today."""

    _attr_name = "Ritten Vandaag"
    _attr_icon = "mdi:car-seat-child"
    _attr_native_unit_of_measurement = "ritten"

    def __init__(
        self, coordinator: NootScheduleCoordinator, entry: ConfigEntry
    ) -> None:
        """Initialise the sensor."""
        super().__init__(coordinator, entry, "ritten_vandaag")

    def _today_rides(self) -> list[dict[str, Any]]:
        today = dt_util.now().strftime("%d-%m-%y")
        return [ride for ride in _rides(self.coordinator.data) if ride.get("date") == today]

    @property
    def native_value(self) -> int:
        """Return the number of rides today."""
        return len(self._today_rides())

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        """Return a summary of today's rides."""
        rides = self._today_rides()
        if not rides:
            return {"ritten": "Geen ritten"}
        return {
            "ritten": ", ".join(
                f"{ride.get('time', '?')} - {ride.get('driver', '?')} "
                f"({ride.get('route', '')})"
                for ride in rides
            )
        }


class DagdeelSensor(NootTaxiSensor):
    """The ride of a specific day and part of the day."""

    _attr_icon = "mdi:bus-school"

    def __init__(
        self,
        coordinator: NootScheduleCoordinator,
        entry: ConfigEntry,
        day: str,
        slot: str,
    ) -> None:
        """Initialise the sensor."""
        super().__init__(coordinator, entry, f"{day.lower()}_{slot}")
        self._day = day
        self._slot = slot
        slot_name = "Ochtend" if slot == "ochtend" else "Middag"
        self._attr_name = f"{DAY_NAMES.get(day, day)} {slot_name}"

    def _day_rides(self) -> list[dict[str, Any]]:
        afternoon = self._slot == "middag"
        return [
            ride
            for ride in _rides(self.coordinator.data)
            if ride.get("day") == self._day
            and (
                ride.get("time", "99:99") >= "12:00"
                if afternoon
                else ride.get("time", "00:00") < "12:00"
            )
        ]

    @property
    def native_value(self) -> str:
        """Return the pickup time."""
        rides = self._day_rides()
        return rides[0].get("time", "Onbekend") if rides else "Geen rit"

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        """Return the ride details."""
        rides = self._day_rides()
        if not rides:
            return {}
        ride = rides[0]
        return {
            "chauffeur": ride.get("driver", ""),
            "datum": ride.get("date", ""),
            "status": ride.get("status", ""),
            "afzettijd": ride.get("dropoff_time", ""),
            "school": ride.get("school", ""),
        }


class _UpcomingRideAttributeSensor(NootTaxiSensor):
    """Expose one attribute of the upcoming ride as its own sensor."""

    _attr_icon = "mdi:bus-school"
    _attribute: str = ""

    @property
    def _ride(self) -> dict[str, Any]:
        return _upcoming_ride(self.coordinator.data)

    @property
    def native_value(self) -> str | int | None:
        """Return the attribute value."""
        ride = self._ride
        if not ride:
            return None
        return ride.get(self._attribute, "")


class ChauffeurSensor(_UpcomingRideAttributeSensor):
    """The driver of the upcoming ride."""

    _attr_name = "Chauffeur"
    _attr_icon = "mdi:account-tie"
    _attribute = "driver"

    def __init__(
        self, coordinator: NootScheduleCoordinator, entry: ConfigEntry
    ) -> None:
        """Initialise the sensor."""
        super().__init__(coordinator, entry, "chauffeur")


class AfzettijdSensor(_UpcomingRideAttributeSensor):
    """The drop-off time of the upcoming ride."""

    _attr_name = "Afzettijd"
    _attr_icon = "mdi:clock-outline"
    _attribute = "dropoff_time"

    def __init__(
        self, coordinator: NootScheduleCoordinator, entry: ConfigEntry
    ) -> None:
        """Initialise the sensor."""
        super().__init__(coordinator, entry, "afzettijd")


class DatumSensor(_UpcomingRideAttributeSensor):
    """The date of the upcoming ride."""

    _attr_name = "Datum"
    _attr_icon = "mdi:calendar"
    _attribute = "date"

    def __init__(
        self, coordinator: NootScheduleCoordinator, entry: ConfigEntry
    ) -> None:
        """Initialise the sensor."""
        super().__init__(coordinator, entry, "datum")


class DagSensor(_UpcomingRideAttributeSensor):
    """The day name of the upcoming ride."""

    _attr_name = "Dag"
    _attr_icon = "mdi:calendar-week"
    _attribute = "day"

    def __init__(
        self, coordinator: NootScheduleCoordinator, entry: ConfigEntry
    ) -> None:
        """Initialise the sensor."""
        super().__init__(coordinator, entry, "dag")


class StatusSensor(_UpcomingRideAttributeSensor):
    """The status of the upcoming ride."""

    _attr_name = "Status"
    _attr_icon = "mdi:information-outline"
    _attribute = "status"

    def __init__(
        self, coordinator: NootScheduleCoordinator, entry: ConfigEntry
    ) -> None:
        """Initialise the sensor."""
        super().__init__(coordinator, entry, "status")


class MinutenTotRitSensor(NootTaxiSensor):
    """The minutes until the upcoming ride."""

    _attr_name = "Minuten tot rit"
    _attr_icon = "mdi:timer-sand"
    _attr_native_unit_of_measurement = "min"

    def __init__(
        self, coordinator: NootScheduleCoordinator, entry: ConfigEntry
    ) -> None:
        """Initialise the sensor."""
        super().__init__(coordinator, entry, "minuten_tot_rit")

    @property
    def native_value(self) -> int:
        """Return the minutes until pickup."""
        ride = _upcoming_ride(self.coordinator.data)
        if not ride:
            return -1
        return minutes_until_iso(ride.get("datetime", ""))


class LiveTrackingSensor(NootTaxiSensor):
    """The live status of the ride being tracked."""

    _attr_name = "Live Tracking"
    _attr_icon = "mdi:map-marker-distance"

    def __init__(
        self, coordinator: NootTrackingCoordinator, entry: ConfigEntry
    ) -> None:
        """Initialise the sensor."""
        super().__init__(coordinator, entry, "live_tracking")

    @property
    def native_value(self) -> str:
        """Return the live ride status."""
        status = self.coordinator.data.get("status", "")
        return status or "Geen live data"

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        """Return the live tracking details."""
        data = self.coordinator.data
        return {
            "chauffeur": data.get("chauffeur", ""),
            "richting": data.get("richting", ""),
            "ophaaladres": data.get("pickup_address", ""),
            "afzetadres": data.get("dropoff_address", ""),
            "school": data.get("school", ""),
            "ophaaltijd_gepland": data.get("pickup_time", ""),
            "afzettijd_gepland": data.get("dropoff_time", ""),
            "instap_tijd": data.get("instap_tijd", ""),
            "uitstap_tijd": data.get("uitstap_tijd", ""),
            "gps_breedtegraad": data.get("gps_lat", ""),
            "gps_lengtegraad": data.get("gps_lon", ""),
            "gps_adres": data.get("gps_address", ""),
            "gps_tijdstip": data.get("gps_timestamp", ""),
            "ritnummer": data.get("routenr4", ""),
            "absentiestatus": data.get("absentiestatus", ""),
            "eta": data.get("eta", ""),
            "melding": data.get("melding", ""),
            "portaal_tijd": data.get("portaal_tijd", ""),
            "ophaal_breedtegraad": data.get("pickup_lat", ""),
            "ophaal_lengtegraad": data.get("pickup_lon", ""),
            "afzet_breedtegraad": data.get("dropoff_lat", ""),
            "afzet_lengtegraad": data.get("dropoff_lon", ""),
            "ophaallocatie": data.get("pickup_locatie", ""),
            "afzetlocatie": data.get("dropoff_locatie", ""),
            "school_tijden": data.get("school_tijden", ""),
            "voertuig": data.get("voertuig", ""),
        }


class ETASensor(NootTaxiSensor):
    """The ETA as reported by the portal."""

    _attr_name = "ETA"
    _attr_icon = "mdi:clock-fast"

    def __init__(
        self, coordinator: NootTrackingCoordinator, entry: ConfigEntry
    ) -> None:
        """Initialise the sensor."""
        super().__init__(coordinator, entry, "eta")

    @property
    def native_value(self) -> str:
        return self.coordinator.data.get("eta", "")
