"""Tests for the top-level scrape-and-export entry point."""

from unittest.mock import patch

import main as entry


def test_main_returns_zero_when_scrape_and_export_succeed():
    with patch.object(entry, "scrape_sounding") as scrape, patch.object(
        entry, "export_site"
    ) as export:
        assert entry.main() == 0
        scrape.assert_called_once_with()
        export.assert_called_once_with()


def test_main_returns_one_when_scrape_fails():
    with patch.object(entry, "scrape_sounding", side_effect=RuntimeError("offline")):
        with patch.object(entry, "export_site") as export:
            assert entry.main() == 1
            export.assert_not_called()
