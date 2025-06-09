# 🌌 Noctilucent - Atmosferische Analyse Dashboard

Een geavanceerde webtool voor het visualiseren en analyseren van meteorologische sondemetingen (radiosondes) van het Duitse Weerstation Norderney (10113).

![Python](https://img.shields.io/badge/Python-3.7+-blue.svg)
![Plotly](https://img.shields.io/badge/Plotly-Interactive-orange.svg)
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
- **8 gespecialiseerde plots** in verticale opstelling
- **Gelijktijdige zoom** over alle grafieken
- **Interactieve tijdnavigatie** met range selectors
- **Individuele kleurschalen** per parameter

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
plotly
pickle
```

### Setup
1. **Clone de repository:**
```bash
git clone https://github.com/username/noctilucent.git
cd noctilucent
```

2. **Installeer dependencies:**
```bash
pip install pandas numpy plotly
```

3. **Zorg voor sounding data:**
Plaats je sounding data in `data/sounding.pkl` formaat

## 📊 Gebruik

### Visualisaties Genereren
```bash
python src/sounding_plot.py
```

### Website Starten
```bash
# Open index.html in je browser
open index.html
```

### Data Formaat
De sounding data verwacht een pickle-bestand met de volgende structuur:
```python
{
    'key': {
        'station_info': {
            'Station number': '10113',
            'Observation time': 'YYMMDD/HHMM',
            'CAPE': float,
            'Lifted index': float,
            'K index': float,
            # ... andere indices
        },
        'table': pandas.DataFrame({
            'PRES': [],    # Druk (hPa)
            'HGHT': [],    # Hoogte (m)
            'TEMP': [],    # Temperatuur (°C)
            'DWPT': [],    # Dauwpunt (°C)
            'RELH': [],    # Relatieve vochtigheid (%)
            'MIXR': [],    # Mengverhouding (g/kg)
            'DRCT': [],    # Windrichting (graden)
            'SKNT': [],    # Windsnelheid (knots)
            'THTA': [],    # Potentiële temperatuur (K)
            'THTE': [],    # Equivalent potentiële temperatuur (K)
            'THTV': []     # Virtuele potentiële temperatuur (K)
        })
    }
}
```

## 🎨 Customization

### Kleurschema's Aanpassen
```python
# In src/sounding_plot.py
colorscales = {
    'temperature': 'thermal',
    'wind_speed': 'Viridis', 
    'wind_direction': 'HSV',
    'humidity': 'Blues',
    'mixing_ratio': 'YlGnBu',
    'potential_temp': 'plasma'
}
```

### Plot Hoogtes Wijzigen
```python
# Aanpassen in make_subplots
row_heights=[0.16, 0.16, 0.16, 0.16, 0.16, 0.16, 0.08, 0.08]
```

## 📁 Project Structuur

```
noctilucent/
│
├── src/
│   └── sounding_plot.py        # Hoofdvisualisatie script
│
├── app/
│   ├── styles/
│   │   └── style.css          # Website styling
│   ├── visualizations/
│   │   └── sounding_plot.html # Gegenereerde plots
│   └── images/                # Website afbeeldingen
│
├── data/
│   └── sounding.pkl           # Sounding meetdata
│
├── index.html                 # Hoofdwebsite
└── README.md                  # Deze file
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
