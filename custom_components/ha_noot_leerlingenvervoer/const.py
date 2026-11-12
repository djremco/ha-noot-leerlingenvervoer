"""Constants for the Noot Leerlingenvervoer integration."""
from __future__ import annotations

from typing import Final

DOMAIN: Final = "ha_noot_leerlingenvervoer"
NAME: Final = "Noot Leerlingenvervoer"
MANUFACTURER: Final = "Noot Vervoer"
MODEL: Final = "Taxi Scheduler"
ATTRIBUTION: Final = "Data from portal.noot.nl"

PORTAL_URL: Final = "https://portal.noot.nl/taxsys/"
GVPAPP_URL: Final = "https://portal.noot.nl/gvpapp"
USER_AGENT: Final = "Mozilla/5.0 (compatible; HomeAssistant)"

# Config entry data
CONF_USERNAME: Final = "username"
CONF_PASSWORD: Final = "password"
CONF_KLANTNR: Final = "klantnr"
CONF_COMPANY: Final = "company"

# Config entry options
CONF_SCHEMA_INTERVAL: Final = "schema_interval"
CONF_TRACKING_INTERVAL: Final = "tracking_interval"
CONF_NEAR_HOME_KM: Final = "near_home_km"
CONF_HOME_LATITUDE: Final = "home_latitude"
CONF_HOME_LONGITUDE: Final = "home_longitude"
CONF_SCHOOL_LATITUDE: Final = "school_latitude"
CONF_SCHOOL_LONGITUDE: Final = "school_longitude"

DEFAULT_COMPANY: Final = "G-NOOT"
DEFAULT_COMPANY_GVP: Final = "g-noot"
DEFAULT_SCHEMA_INTERVAL: Final = 3600
DEFAULT_TRACKING_INTERVAL: Final = 60
DEFAULT_NEAR_HOME_KM: Final = 1.2

MIN_SCHEMA_INTERVAL: Final = 300
MIN_TRACKING_INTERVAL: Final = 30


class NootApiError(Exception):
    """Raised when the Noot portal returns an error or unexpected content."""


class NootAuthError(NootApiError):
    """Raised when the portal rejects the credentials."""
