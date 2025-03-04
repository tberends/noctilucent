#!/usr/bin/env python3
"""
Dit script verzamelt en visualiseert sounding data.

Het script maakt gebruik van twee hoofdmodules:
- sounding_scraper: Voor het ophalen van de sounding data
- sounding_plot: Voor het visualiseren van de sounding data
"""

import sys
from datetime import datetime, timedelta
import logging
from src.sounding_scraper import scrape_sounding
from src.sounding_plot import plot_sounding

# Logging configuratie
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

def main():
    """
    Hoofdfunctie die het scrapen en plotten van sounding data coördineert.
    """
    try:
        logger.info("Start met het verzamelen van sounding data...")
        scrape_sounding()
        
        logger.info("Start met het plotten van sounding data...")
        plot_sounding()
        
        logger.info("Script succesvol uitgevoerd!")
        return 0
        
    except Exception as e:
        logger.error(f"Er is een fout opgetreden: {str(e)}")
        return 1

if __name__ == "__main__":
    sys.exit(main())
