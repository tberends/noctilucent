# Import functions from sounding_scraper and sounding_plot modules in the src folder

import pickle
from datetime import datetime, timedelta

from src.sounding_scraper import scrape_sounding
from src.sounding_plot import plot_sounding

# Scrape sounding data
scrape_sounding()

# Plot sounding data
plot_sounding()
