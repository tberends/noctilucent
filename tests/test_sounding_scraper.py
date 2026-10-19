"""Tests for Wyoming FM35 fetch helpers and HTML parsers."""

from datetime import datetime
from unittest.mock import patch

import pandas as pd
import pytest
import requests
import responses

import src.sounding_scraper as sounding_scraper
from src.sounding_scraper import (
    FetchError,
    fetch_sounding,
    http_get,
    inventory_times,
    parse_indices,
    parse_profile,
    sounding_url,
)
from src.sounding_store import MS_TO_KNOTS, PROFILE_VALUE_COLUMNS


@pytest.fixture(autouse=True)
def reset_ssl_verify():
    sounding_scraper._ssl_verify = True
    yield
    sounding_scraper._ssl_verify = True


def test_sounding_url_encodes_datetime_and_product():
    when = datetime(2024, 6, 15, 12, 0, 0)
    url = sounding_url(when, "10113", "TEXT:LIST")
    assert "id=10113" in url
    assert "src=FM35" in url
    assert "type=TEXT:LIST" in url
    assert "datetime=2024-06-15%2012%3A00%3A00" in url


def test_parse_profile_reads_fixed_width_and_converts_sped_to_knots(fm35_html):
    frame = parse_profile(fm35_html)
    assert frame is not None
    assert list(frame.columns) == PROFILE_VALUE_COLUMNS
    assert frame.iloc[0]["PRES"] == pytest.approx(999.0)
    assert frame.iloc[0]["HGHT"] == pytest.approx(11.0)
    assert frame.iloc[0]["TEMP"] == pytest.approx(14.6)
    # First row SPED is 7.0 m/s in the fixture.
    assert frame.iloc[0]["SKNT"] == pytest.approx(7.0 * MS_TO_KNOTS)
    assert frame["SKNT"].notna().sum() >= 20


def test_parse_profile_returns_none_without_pre_block():
    assert parse_profile("<html><body>no sounding</body></html>") is None


def test_parse_profile_returns_none_without_pres_header():
    html = "<html><pre>\nnot a table\n</pre></html>"
    assert parse_profile(html) is None


def test_parse_indices_maps_known_codes(fm35_html):
    fields = parse_indices(fm35_html)
    assert fields["Station latitude"] == pytest.approx(53.71)
    assert fields["K index"] == pytest.approx(30.3)
    assert fields["Most Unstable CAPE"] == pytest.approx(90.2)
    assert fields["Virtual Lifted Index"] == pytest.approx(-1.6)
    assert "Unknown" not in fields


def test_parse_indices_skips_unknown_and_empty_values():
    html = """
    <TR><TD>KINX</TD><TD>K Index</TD><TD>12.5</TD></TR>
    <TR><TD>ZZZZ</TD><TD>Unknown</TD><TD>9</TD></TR>
    <TR><TD>SHOW</TD><TD>Showalter</TD><TD></TD></TR>
    """
    fields = parse_indices(html)
    assert fields == {"K index": 12.5}


@responses.activate
def test_http_get_returns_none_on_missing_sounding():
    url = "https://weather.uwyo.edu/wsgi/sounding?missing=1"
    responses.add(responses.GET, url, status=404)
    assert http_get(url, attempts=1) is None


@responses.activate
def test_http_get_returns_body_on_success():
    url = "https://weather.uwyo.edu/wsgi/sounding?ok=1"
    responses.add(responses.GET, url, body="payload", status=200)
    assert http_get(url, attempts=1) == "payload"
    assert responses.calls[0].request.headers["User-Agent"] == "noctilucent"


@responses.activate
def test_http_get_retries_server_errors_then_raises():
    url = "https://weather.uwyo.edu/wsgi/sounding?busy=1"
    responses.add(responses.GET, url, status=503)
    responses.add(responses.GET, url, status=503)
    with patch("src.sounding_scraper.time.sleep"):
        with pytest.raises(FetchError):
            http_get(url, attempts=2)


def test_http_get_falls_back_when_ssl_verify_fails():
    url = "https://weather.uwyo.edu/wsgi/sounding?ssl=1"
    ok = requests.Response()
    ok.status_code = 200
    ok._content = b"payload"

    def fake_get(request_url, timeout=45, headers=None, verify=True):
        assert request_url == url
        if verify:
            raise requests.exceptions.SSLError("certificate verify failed")
        return ok

    with patch("src.sounding_scraper.requests.get", side_effect=fake_get):
        with pytest.warns(RuntimeWarning, match="SSL verification failed"):
            assert http_get(url, attempts=2) == "payload"
    assert sounding_scraper._ssl_verify is False


@responses.activate
def test_inventory_times_keeps_text_list_links_for_requested_year(inventory_html):
    url = sounding_url(datetime(2024, 1, 1, 0, 0), "10113", "INVENTORY")
    responses.add(responses.GET, url, body=inventory_html, status=200)
    found = inventory_times(2024, "10113")
    assert found == [
        datetime(2024, 6, 15, 0, 0),
        datetime(2024, 6, 15, 12, 0),
        datetime(2024, 6, 16, 0, 0),
    ]


@responses.activate
def test_fetch_sounding_builds_profile_and_station_row(fm35_html):
    when = datetime(2024, 6, 15, 12, 0)
    url = sounding_url(when, "10113", "TEXT:LIST")
    responses.add(responses.GET, url, body=fm35_html, status=200)
    profile, station_row = fetch_sounding(when)
    assert "time" in profile.columns
    assert profile["time"].iloc[0] == pd.Timestamp(when)
    assert station_row["Station number"] == "10113"
    assert station_row["Observation time"] == "240615/1200"
    assert station_row["K index"] == pytest.approx(30.3)


@responses.activate
def test_fetch_sounding_returns_none_when_server_has_no_slot():
    when = datetime(2024, 6, 15, 6, 0)
    url = sounding_url(when, "10113", "TEXT:LIST")
    responses.add(responses.GET, url, status=400)
    assert fetch_sounding(when) is None
