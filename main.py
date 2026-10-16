#!/usr/bin/env python3
"""Fetch new radiosondes and write the static site data files."""

import sys
import logging
from src.sounding_scraper import scrape_sounding
from src.sounding_plot import export_site

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


def main():
    """Run the scraper and export. Returns 0 on success, 1 on failure."""
    try:
        logger.info("Start met het verzamelen van sounding data...")
        scrape_sounding()

        logger.info("Start met het exporteren van de meetpagina...")
        export_site()

        logger.info("Script succesvol uitgevoerd!")
        return 0

    except Exception as e:
        logger.error(f"Er is een fout opgetreden: {str(e)}")
        return 1


if __name__ == "__main__":
    sys.exit(main())
