"""Client for the Noot taxi portal.

Two separate portal endpoints are used:

* ``taxsys``  - the ride schedule (one page with a table of rides).
* ``gvpapp``  - the live tracking data of a single ride.

Both are scraped; the portal does not expose a documented API.
"""
from __future__ import annotations

import hashlib
import json
import logging
import re
from datetime import datetime
from typing import Any
from urllib.parse import quote

import aiohttp

from homeassistant.util import dt as dt_util

from .const import (
    DEFAULT_COMPANY,
    DEFAULT_COMPANY_GVP,
    GVPAPP_URL,
    PORTAL_URL,
    USER_AGENT,
    NootApiError,
    NootAuthError,
)

_LOGGER = logging.getLogger(__name__)

REQUEST_TIMEOUT = aiohttp.ClientTimeout(total=45)


def hash_password(password: str) -> str:
    """Return the password hash the portal expects."""
    return hashlib.sha512(("BSA" + password).encode("utf-8")).hexdigest()


def _as_local(value: datetime) -> datetime:
    """Attach the Home Assistant time zone to a naive datetime."""
    if value.tzinfo is None:
        return value.replace(tzinfo=dt_util.DEFAULT_TIME_ZONE)
    return value.astimezone(dt_util.DEFAULT_TIME_ZONE)


def parse_portal_date(date_str: str) -> datetime | None:
    """Parse a ``dd-mm-yy`` date from the portal."""
    try:
        day, month, year = (int(part) for part in date_str.split("-"))
        return datetime(2000 + year, month, day)
    except (AttributeError, TypeError, ValueError):
        return None


def parse_ride_time(ride_time: str) -> tuple[int, int] | None:
    """Parse a ``HH:MM`` pickup time into an hour and minute."""
    try:
        hour, minute = (int(part) for part in ride_time.split(":"))
    except (AttributeError, ValueError):
        return None
    if not 0 <= hour <= 23 or not 0 <= minute <= 59:
        return None
    return hour, minute


# ---------------------------------------------------------------------------
# Schedule parsing
# ---------------------------------------------------------------------------

_ROW_PATTERN = re.compile(r"<tr[^>]*>(.*?)</tr>", re.DOTALL)
_DATE_PATTERN = re.compile(r"([A-Z]+)<br>\s*(\d{2}-\d{2}-\d{2})")
_PICKUP_PATTERN = re.compile(
    r'(\d{2}:\d{2})<input[^>]*name="vakantie_vanaf_tijd"'
)
_DROPOFF_PATTERN = re.compile(
    r'(\d{2}:\d{2})\s*<input[^>]*name="vakantie_tot_tijd"'
)
_ADDRESS_PATTERN = re.compile(
    r"([A-Z0-9 ]+\d*[A-Z]?)<br>\s*(\d{4}[A-Z]{2})\s+([A-Z ]+)"
)
_SCHOOL_PATTERN = re.compile(r"\[([^\]]+)\]<br>([^<]+)")
_ROUTE_PATTERN = re.compile(r'<td id="middle">(\d{5})</td>')
_STATUS_PATTERN = re.compile(r"ritstatus[^>]*>[^<]*</div>\s*([A-Za-z]+)")
_DRIVER_PATTERN = re.compile(r'<td id="middle"[^>]*>([A-Z]{2,})</td>')


def parse_rides(html: str) -> list[dict[str, Any]]:
    """Parse the ride table out of the schedule page."""
    table_match = re.search(r'<table[^>]*id="tblvvs"[^>]*>(.*?)</table>', html, re.DOTALL)
    if not table_match:
        return []

    rides: list[dict[str, Any]] = []
    for row in _ROW_PATTERN.findall(table_match.group(1)):
        date_match = _DATE_PATTERN.search(row)
        if not date_match:
            continue

        ride: dict[str, Any] = {
            "day_name": date_match.group(1),
            "date": date_match.group(2),
        }

        pickup_match = _PICKUP_PATTERN.search(row)
        if not pickup_match:
            continue
        ride["pickup_time"] = pickup_match.group(1)

        address_match = _ADDRESS_PATTERN.search(row)
        if address_match:
            ride["pickup_address"] = (
                f"{address_match.group(1).strip()}, "
                f"{address_match.group(2)} {address_match.group(3).strip()}"
            )

        dropoff_match = _DROPOFF_PATTERN.search(row)
        if dropoff_match:
            ride["dropoff_time"] = dropoff_match.group(1)

        school_match = _SCHOOL_PATTERN.search(row)
        if school_match:
            ride["school_name"] = school_match.group(1)
            ride["school_address"] = school_match.group(2).strip()

        route_match = _ROUTE_PATTERN.search(row)
        if route_match:
            ride["route"] = route_match.group(1)

        status_match = _STATUS_PATTERN.search(row)
        ride["status"] = status_match.group(1) if status_match else ""

        driver_match = _DRIVER_PATTERN.search(row)
        if driver_match:
            ride["driver"] = driver_match.group(1)

        rides.append(ride)

    return rides


def get_next_ride(rides: list[dict[str, Any]], *, morning: bool) -> dict[str, Any] | None:
    """Return the first ride of today or later for the given part of the day."""
    now = dt_util.now()
    result: dict[str, Any] | None = None
    result_dt: datetime | None = None

    for ride in rides:
        ride_date = parse_portal_date(ride.get("date", ""))
        parsed_time = parse_ride_time(ride.get("pickup_time", ""))
        if ride_date is None or parsed_time is None:
            continue

        hour, minute = parsed_time
        if morning != (hour < 12):
            continue

        ride_dt = _as_local(ride_date.replace(hour=hour, minute=minute))
        if ride_dt <= now:
            continue
        if result_dt is None or ride_dt < result_dt:
            result = {**ride, "_datetime": ride_dt}
            result_dt = ride_dt

    return result


def format_ride(ride: dict[str, Any] | None) -> dict[str, Any]:
    """Return a ride in the shape the sensors expect."""
    if not ride:
        return {
            "available": False,
            "time": "",
            "address": "",
            "school": "",
            "school_address": "",
            "driver": "",
            "route": "",
            "date": "",
            "day": "",
            "dropoff_time": "",
            "status": "",
            "datetime": "",
        }

    ride_dt = ride.get("_datetime")
    return {
        "available": True,
        "time": ride.get("pickup_time", ""),
        "address": ride.get("pickup_address", ""),
        "school": ride.get("school_name", ""),
        "school_address": ride.get("school_address", ""),
        "driver": ride.get("driver", ""),
        "route": ride.get("route", ""),
        "date": ride.get("date", ""),
        "day": ride.get("day_name", ""),
        "dropoff_time": ride.get("dropoff_time", ""),
        "status": ride.get("status", ""),
        "datetime": _as_local(ride_dt).isoformat() if ride_dt else "",
    }


def minutes_until_iso(value: str) -> int:
    """Return the minutes until an ISO timestamp, or -1 when it is unknown."""
    target = dt_util.parse_datetime(value)
    if target is None:
        return -1
    return int((_as_local(target) - dt_util.now()).total_seconds() // 60)


# ---------------------------------------------------------------------------
# Tracking parsing
# ---------------------------------------------------------------------------

_SHOW_RIDE_PATTERN = re.compile(
    r"ShowDeelnemersRit\('([^']+)','([^']+)','([^']+)','([^']+)','[^']*','[^']*'\)"
)


def parse_ride_calls(html: str) -> list[dict[str, str]]:
    """Parse the ride references out of the tracking page."""
    return [
        {
            "dnnr": match[0],
            "routedatum": match[1],
            "routenr": match[2],
            "company": match[3],
        }
        for match in _SHOW_RIDE_PATTERN.findall(html)
    ]


def find_next_ride(ritten: list[dict[str, str]]) -> dict[str, str] | None:
    """Pick the ride that is relevant right now.

    Morning routes end in ``0`` and afternoon routes end in ``1``.
    """
    now = dt_util.now()
    today = now.strftime("%y%m%d")

    today_rides = [rit for rit in ritten if rit["routedatum"] == today]
    future_rides = sorted(
        (rit for rit in ritten if rit["routedatum"] > today),
        key=lambda rit: rit["routedatum"],
    )

    morning = [rit for rit in today_rides if rit["routenr"].endswith("0")]
    afternoon = [rit for rit in today_rides if rit["routenr"].endswith("1")]

    if now.hour < 12:
        return (morning or afternoon or future_rides or today_rides or [None])[0]
    if now.hour < 16:
        return (afternoon or morning or future_rides or today_rides or [None])[0]
    return (future_rides or afternoon or today_rides or [None])[0]


# ---------------------------------------------------------------------------
# API clients
# ---------------------------------------------------------------------------


class NootScheduleApi:
    """Fetch the ride schedule from the ``taxsys`` portal."""

    def __init__(
        self,
        session: aiohttp.ClientSession,
        username: str,
        password: str,
        klantnr: str,
        company: str = DEFAULT_COMPANY,
    ) -> None:
        """Initialise the schedule client."""
        self._session = session
        self._username = username
        self._password = password
        self._klantnr = klantnr
        self._company = company

    async def async_login(self) -> None:
        """Start a portal session."""
        session_id = hashlib.md5(
            str(datetime.now().timestamp()).encode("utf-8")
        ).hexdigest()[:26]
        self._session.cookie_jar.update_cookies({"PHPSESSID": session_id})

        data = {
            "submit": "true",
            "username": self._username,
            "password": self._password,
            "passwordENC": hash_password(self._password),
            "meta_sw": "1920",
            "meta_sh": "1080",
        }
        try:
            async with self._session.post(
                f"{PORTAL_URL}?company={self._company}",
                data=data,
                headers={"User-Agent": USER_AGENT},
                timeout=REQUEST_TIMEOUT,
            ) as response:
                await response.read()
                if response.status >= 400:
                    raise NootApiError(f"Login failed with HTTP {response.status}")
        except aiohttp.ClientError as err:
            raise NootApiError(f"Login request failed: {err}") from err
        except TimeoutError as err:
            raise NootApiError("Login request timed out") from err

    async def _async_fetch_html(self) -> str:
        """Fetch the schedule page."""
        url = (
            f"{PORTAL_URL}?page=deelnemerMutatie"
            f"&klantNr={quote(self._klantnr)}&company={self._company}"
        )
        try:
            async with self._session.get(
                url,
                headers={"User-Agent": USER_AGENT},
                timeout=REQUEST_TIMEOUT,
            ) as response:
                if response.status >= 400:
                    raise NootApiError(f"Schedule request failed with HTTP {response.status}")
                return (await response.read()).decode("utf-8", errors="replace")
        except aiohttp.ClientError as err:
            raise NootApiError(f"Schedule request failed: {err}") from err
        except TimeoutError as err:
            raise NootApiError("Schedule request timed out") from err

    async def async_fetch_schedule(self) -> dict[str, Any]:
        """Return the parsed schedule, including the next morning/afternoon ride."""
        await self.async_login()
        html = await self._async_fetch_html()

        if "tblvvs" not in html:
            # The session was probably rejected; try once more with a fresh login.
            await self.async_login()
            html = await self._async_fetch_html()
        if "tblvvs" not in html:
            raise NootApiError("Ride table not found; login may have failed")

        rides = parse_rides(html)
        next_morning = get_next_ride(rides, morning=True)
        next_afternoon = get_next_ride(rides, morning=False)

        return {
            "timestamp": dt_util.now().isoformat(),
            "klant_nr": self._klantnr,
            "total_rides": len(rides),
            "next_morning": format_ride(next_morning),
            "next_afternoon": format_ride(next_afternoon),
            "next_morning_minutes_until": minutes_until_iso(
                format_ride(next_morning)["datetime"]
            ),
            "next_afternoon_minutes_until": minutes_until_iso(
                format_ride(next_afternoon)["datetime"]
            ),
            "all_rides": [format_ride(ride) for ride in rides],
        }


class NootTrackingApi:
    """Fetch live tracking data from the ``gvpapp`` portal."""

    def __init__(
        self,
        session: aiohttp.ClientSession,
        username: str,
        password: str,
        company: str = DEFAULT_COMPANY_GVP,
    ) -> None:
        """Initialise the tracking client."""
        self._session = session
        self._username = username
        self._password = password
        self._company = company
        self._dnnr: str | None = None

    async def _async_request(self, method: str, url: str, data: dict[str, Any] | None = None) -> str:
        """Perform a request and return the decoded body."""
        try:
            async with self._session.request(
                method,
                url,
                data=data,
                headers={"User-Agent": USER_AGENT},
                timeout=REQUEST_TIMEOUT,
            ) as response:
                if response.status >= 400:
                    raise NootApiError(f"Request failed with HTTP {response.status}")
                return (await response.read()).decode("utf-8", errors="replace")
        except aiohttp.ClientError as err:
            raise NootApiError(f"Request failed: {err}") from err
        except TimeoutError as err:
            raise NootApiError("Request timed out") from err

    async def async_login(self) -> str:
        """Log in and return the customer number (dnnr)."""
        await self._async_request("GET", f"{GVPAPP_URL}/?company={self._company}")
        raw = await self._async_request(
            "POST",
            f"{GVPAPP_URL}/data/getxml.php?company={self._company}",
            {
                "type": "1",
                "fldusername": self._username,
                "fldpasswd": hash_password(self._password),
                "fldrememberme": "on",
                "token": "",
            },
        )

        try:
            payload = json.loads(raw)
        except json.JSONDecodeError as err:
            raise NootApiError("Login response was not valid JSON") from err

        login = payload.get("loginrequest", {})
        if login.get("status") != "200":
            raise NootAuthError("Login rejected by the portal")

        for group in login.get("dlist", []):
            for item in group.get("dl", []):
                if item.get("dnnr"):
                    self._dnnr = item["dnnr"]
                    return self._dnnr

        raise NootApiError("No customer number in the login response")

    async def _async_get_rides(self) -> list[dict[str, str]]:
        """Return the ride references for today."""
        if self._dnnr is None:
            await self.async_login()

        await self._async_request(
            "POST",
            f"{GVPAPP_URL}/data/getxml.php?",
            {
                "type": "",
                "action": "setpeildatum",
                "peildatum": dt_util.now().strftime("%d-%m-%Y"),
            },
        )
        html = await self._async_request(
            "POST",
            f"{GVPAPP_URL}/data/getxml.php?company={self._company}",
            {
                "type": "2",
                "pagenum": "3",
                "company": self._company,
                "deeltype": "1",
                "dnnr": self._dnnr,
            },
        )
        return parse_ride_calls(html)

    async def _async_get_ride_details(self, rit: dict[str, str]) -> dict[str, Any]:
        """Return the live tracking details of a single ride."""
        raw = await self._async_request(
            "POST",
            f"{GVPAPP_URL}/data/getxml.php?company={self._company}",
            {
                "type": "0",
                "action": "getdeelnemersrit",
                "company": rit["company"],
                "dnnr": rit["dnnr"],
                "routenr": rit["routenr"],
                "routedatum": rit["routedatum"],
            },
        )
        try:
            payload = json.loads(raw)
        except json.JSONDecodeError as err:
            raise NootApiError("Tracking response was not valid JSON") from err
        return payload.get("gvpritrequest", {})

    async def async_fetch_tracking(self) -> dict[str, Any]:
        """Return the live tracking data of the ride that is relevant now."""
        await self.async_login()

        ritten = await self._async_get_rides()
        if not ritten:
            raise NootApiError("No rides found for today")

        rit = find_next_ride(ritten)
        if rit is None:
            raise NootApiError("No upcoming ride found")

        tracking = await self._async_get_ride_details(rit)
        if tracking.get("status") != "200":
            raise NootApiError(
                f"Tracking failed: {tracking.get('melding') or 'unknown error'}"
            )

        return {
            "timestamp": dt_util.now().isoformat(),
            "dnnr": tracking.get("dnnr", ""),
            "naam": tracking.get("naam", ""),
            "routenr": tracking.get("routenr", ""),
            "routenr4": tracking.get("routenr4", ""),
            "routedatum": tracking.get("routedatum1", ""),
            "richting": tracking.get("richting", ""),
            "pickup_time": tracking.get("ot", ""),
            "dropoff_time": tracking.get("at", ""),
            "pickup_address": tracking.get("adr1dis", ""),
            "dropoff_address": tracking.get("adr2dis", ""),
            "school": tracking.get("aom2", ""),
            "chauffeur": tracking.get("chf_displaynaam", ""),
            "status": tracking.get("data_status", ""),
            "status_code": tracking.get("data_status1", ""),
            "instap_tijd": tracking.get("data_instap", ""),
            "uitstap_tijd": tracking.get("data_uitstap", ""),
            "gps_lat": tracking.get("wgngps_lat", ""),
            "gps_lon": tracking.get("wgngps_lon", ""),
            "gps_address": tracking.get("wgngps_adr", ""),
            "gps_timestamp": tracking.get("wgngps_tim", ""),
            "absentiestatus": tracking.get("absentiestatus2", ""),
            # Nieuwe velden — optie B
            "eta": tracking.get("eta1", ""),
            "melding": tracking.get("melding", ""),
            "portaal_tijd": tracking.get("nu", ""),
            "pickup_lat": tracking.get("lat1", ""),
            "pickup_lon": tracking.get("lon1", ""),
            "dropoff_lat": tracking.get("lat2", ""),
            "dropoff_lon": tracking.get("lon2", ""),
            "pickup_locatie": " ".join(
                tracking.get(k, "") for k in ("str1", "pk1", "wpl1") if tracking.get(k, "")
            ),
            "dropoff_locatie": " ".join(
                tracking.get(k, "") for k in ("str2", "pk2", "wpl2") if tracking.get(k, "")
            ),
            "school_tijden": tracking.get("om2", ""),
            "voertuig": tracking.get("wgn_displaynaam", ""),
        }
