# Noctilucent

Statische site met radiosondes van DWD-station Norderney (10113). De pagina toont temperatuur, wind, vocht, potentiële temperatuur, K-index, CAPE en lifted index tegen hoogte en tijd.

Bron: University of Wyoming Atmospheric Soundings, product FM35. Meestal twee oplatingen per dag (00:00 en 12:00 UTC), soms ook 06:00 of 18:00. De sonde bereikt doorgaans ongeveer 30 km.

## Vereisten

- Python 3.13 (zoals in de GitHub Actions-workflow)
- `pandas`, `numpy`, `pyarrow`, `requests`

```bash
git clone https://github.com/tberends/noctilucent.git
cd noctilucent
pip install pandas numpy pyarrow requests
```

Het archief staat in `data/profiles.parquet` (niveaus) en `data/station.parquet` (stationsindices).

## Gebruik

Nieuwe oplatingen ophalen en de pagina vernieuwen:

```bash
python main.py
```

Alleen de exportbestanden voor de site schrijven:

```bash
python src/sounding_plot.py
```

Dat levert `app/data/meta.json`, `app/data/recent.bin` en `app/data/archive.bin`. De browser tekent die bestanden in `index.html`.

Historische gaten vullen (optioneel):

```bash
python src/sounding_scraper.py --historical
```

Tijdstempels controleren of corrupte oplatingen verwijderen:

```bash
python src/clean_data.py
python src/clean_data.py --clean --backup
```

## Automatische update

`.github/workflows/python-cron.yml` draait dagelijks om 17:00 UTC (GitHub start de run vaak later) en kan handmatig worden gestart. De job roept `main.py` aan, commit gewijzigde Parquet- en `app/data`-bestanden en pusht naar `main`.

`scrape_sounding` begint bij de laatste opgeslagen oplating en haalt alle latere FM35-tijdstippen uit de Wyoming-inventaris. Als een eerdere run faalde (bijvoorbeeld HTTP 503), vult de volgende geslaagde run die achterstand in één keer aan.

## Projectstructuur

```
noctilucent/
├── main.py                 # scrape + export
├── index.html              # GitHub Pages-ingang
├── src/
│   ├── sounding_scraper.py # Wyoming FM35 ophalen
│   ├── sounding_store.py   # Parquet lezen en schrijven
│   ├── sounding_plot.py    # export naar app/data
│   └── clean_data.py       # tijdstempelcontrole
├── data/
│   ├── profiles.parquet
│   └── station.parquet
├── app/
│   ├── data/               # meta.json, recent.bin, archive.bin
│   ├── scripts/
│   ├── styles/
│   └── images/
└── .github/workflows/
    └── python-cron.yml
```

Paden in `index.html` zijn relatief, zodat de site zowel op de root als onder `/noctilucent/` werkt.

## Tropopauze

`find_tropopause` volgt de WMO-definitie: het laagste niveau boven 5.000 m waar de temperatuurgradiënt groter is dan −2 °C/km, en waar het gemiddelde over de volgende 2 km ook boven −2 °C/km blijft.

## Data

| Onderdeel | Waarde |
|---|---|
| Station | Norderney, DWD 10113 |
| Frequentie | 00:00 en 12:00 UTC (soms 06:00 of 18:00) |
| Profiel | oppervlak tot ongeveer 30 km |
| Indices | onder meer K-index, CAPE/MUCAPE, lifted index |

De oudere oppervlakte-CAPE en lifted index lopen tot 26 juni 2026. Daarna volgen MUCAPE en de virtuele lifted index uit de FM35-interface.
