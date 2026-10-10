# 🌌 Noctilucent - Atmosferische Analyse Dashboard

Een geavanceerde webtool voor het visualiseren en analyseren van meteorologische sondemetingen (radiosondes) van het Duitse Weerstation Norderney (10113).

![Python](https://img.shields.io/badge/Python-3.7+-blue.svg)
![License](https://img.shields.io/badge/License-MIT-green.svg)

## 📋 Overzicht

Noctilucent biedt een uitgebreide atmosferische analyse door middel van interactieve visualisaties van:
- **Temperatuurprofielen** met WMO-gedefinieerde tropopauze detectie
- **Windpatronen** (snelheid en richting) voor jet stream analyse
- **Vochtigheidsmetingen** (relatieve vochtigheid en mengverhouding)
- **Atmosferische stabiliteit** (potentiële temperatuur, CAPE, K-index)
- **Convectie-indicatoren** voor onweersbui voorspelling

## ✨ Features

### 🎯 **Uitgebreide Visualisaties**
- **Zes kaarten** met een gedeelde tijdlijn
- **Periodekeuze** van 14 dagen tot het hele archief
- **Verticaal profiel** van de gekozen oplating
- **Eigen kleurschaal** per grootheid

### 🌡️ **Meteorologische Parameters**
1. **Temperatuurprofiel** - Met automatische tropopauze detectie (WMO-definitie)
2. **Windsnelheid** - Jet stream en windschering identificatie
3. **Windrichting** - Atmosferische circulatiepatronen
4. **Relatieve Vochtigheid** - Wolkvorming en neerslag voorspelling
5. **Mengverhouding** - Conservatieve vochtigheidsmaat
6. **Potentiële Temperatuur** - Atmosferische stabiliteitsanalyse
7. **K-Index** - Onweersbui potentieel indicator
8. **CAPE & Lifted Index** - Convectie-energie en stabiliteit

### 🔬 **Wetenschappelijke Toepassingen**
- **Weersvoorspelling** - Fronten en inversielagen
- **Onweersbui-analyse** - CAPE, windschering, stabiliteitsindices
- **Luchtvaart** - Turbulentie en windschering detectie
- **Klimaatstudie** - Langetermijntrends in atmosferische structuur
- **Atmosferische chemie** - Transport van pollutanten

## 🚀 Installatie

### Vereisten
```bash
Python 3.7+
pandas
numpy
pyarrow
```

### Setup
1. **Clone de repository:**
```bash
git clone https://github.com/tberends/noctilucent.git
cd noctilucent
```

2. **Installeer dependencies:**
```bash
pip install pandas numpy pyarrow
```

3. **Archief**
De metingen staan in `data/profiles.parquet` en `data/station.parquet`.

## 📊 Gebruik

### Paginabestanden genereren
```bash
python src/sounding_plot.py
```
Dit schrijft `app/data/meta.json`, `app/data/recent.bin` en `app/data/archive.bin`. De pagina tekent die bestanden zelf.

### Website
`index.html` is de GitHub Pages-ingang. Paden zijn relatief, zodat de site zowel op de root als onder `/noctilucent/` werkt.

## 📁 Project Structuur

```
noctilucent/
│
├── src/
│   └── sounding_plot.py        # Export naar de statische pagina
│
├── app/
│   ├── data/                  # meta.json, recent.bin, archive.bin
│   ├── styles/
│   │   └── style.css
│   ├── scripts/
│   └── images/
│
├── data/
│   ├── profiles.parquet
│   └── station.parquet
│
├── index.html
└── README.md
```

## 🔧 Algoritmes

### Tropopauze Detectie
Implementeert de **WMO-definitie**:
- Laagste niveau waar temperatuurgradiënt > -2°C/km
- Gemiddelde gradiënt in volgende 2km blijft > -2°C/km
- Minimum zoekaltitude: 5000m

### Stabiliteitsindices
- **K-Index**: `(T850 - T500) + Td850 - (T700 - Td700)`
- **CAPE**: Convectieve beschikbare potentiële energie
- **Lifted Index**: Stabiliteit van atmosferische kolom

## 🌐 Browser Ondersteuning

- ✅ Chrome 80+
- ✅ Firefox 75+
- ✅ Safari 13+
- ✅ Edge 80+

## 📈 Data Bronnen

- **Station**: Norderney (10113) - Duitse Weerdienst (DWD)
- **Frequentie**: 2x per dag (00 UTC, 12 UTC)
- **Altitude**: Oppervlakte tot ~30km
- **Parameters**: Volledige atmosferische profielen
