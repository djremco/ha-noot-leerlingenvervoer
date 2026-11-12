"""Small helpers for the Noot Taxi Busje integration."""
from __future__ import annotations

import math

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant

from .const import (
    CONF_HOME_LATITUDE,
    CONF_HOME_LONGITUDE,
    CONF_SCHOOL_LATITUDE,
    CONF_SCHOOL_LONGITUDE,
)

EARTH_RADIUS_KM = 6371.0088


def as_float(value: object) -> float | None:
    """Convert a config value to a float, or return None."""
    if value in (None, ""):
        return None
    try:
        return float(value)  # type: ignore[arg-type]
    except (TypeError, ValueError):
        return None


def get_home_coordinates(
    hass: HomeAssistant, entry: ConfigEntry
) -> tuple[float | None, float | None]:
    """Return the configured home coordinates, falling back to ``zone.home``."""
    latitude = as_float(entry.options.get(CONF_HOME_LATITUDE))
    longitude = as_float(entry.options.get(CONF_HOME_LONGITUDE))
    if latitude is not None and longitude is not None:
        return latitude, longitude

    zone = hass.states.get("zone.home")
    if zone is not None:
        return zone.attributes.get("latitude"), zone.attributes.get("longitude")

    return None, None


def get_school_coordinates(
    entry: ConfigEntry,
) -> tuple[float | None, float | None]:
    """Return the configured school coordinates, if any."""
    return (
        as_float(entry.options.get(CONF_SCHOOL_LATITUDE)),
        as_float(entry.options.get(CONF_SCHOOL_LONGITUDE)),
    )


def distance_km(
    latitude_a: float | None,
    longitude_a: float | None,
    latitude_b: float | None,
    longitude_b: float | None,
) -> float | None:
    """Return the great-circle distance between two points in kilometres."""
    if None in (latitude_a, longitude_a, latitude_b, longitude_b):
        return None

    lat_a = math.radians(latitude_a)  # type: ignore[arg-type]
    lat_b = math.radians(latitude_b)  # type: ignore[arg-type]
    delta_lat = lat_b - lat_a
    delta_lon = math.radians(longitude_b - longitude_a)  # type: ignore[operator]

    hav = (
        math.sin(delta_lat / 2) ** 2
        + math.cos(lat_a) * math.cos(lat_b) * math.sin(delta_lon / 2) ** 2
    )
    return 2 * EARTH_RADIUS_KM * math.asin(math.sqrt(hav))
