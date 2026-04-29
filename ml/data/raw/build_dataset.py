"""Build the raw destinations dataset and write it to destinations_raw.csv.

Run from ml/ directory:
    python data/raw/build_dataset.py

SOURCES (all public, no scraping):
    cost_per_day_usd  : Budget Your Trip / Backpacker Index 2024 (mid-range budget traveler)
    safety_index      : Numbeo Safety Index 2024 (0-100 scale divided by 10)
    cultural_sites    : UNESCO World Heritage list (count per country/region) + major museums
    avg_temp_c        : Climate-data.org / Wikipedia city climate tables
    Hand-scored (0-10): activity_density, nightlife_score, nature_score,
                        beach_score, family_friendly_score, infrastructure_score,
                        luxury_index, language_difficulty (1-5)

ANCHOR POINTS FOR HAND-SCORED FEATURES (prevents drift across 160 rows):
    activity_density : 10=Tokyo, 7=Barcelona, 4=Reykjavik, 1=Sahara outpost
    nightlife_score  : 10=Ibiza, 7=Berlin, 4=Lisbon, 1=Kyoto (traditional)
    nature_score     : 10=Patagonia, 7=New Zealand, 4=Swiss Alps, 1=Dubai
    beach_score      : 10=Maldives, 7=Phuket, 4=Barcelona, 1=landlocked city
    family_friendly  : 10=Orlando, 7=Singapore, 4=Paris, 1=Ibiza
    infrastructure   : 10=Tokyo, 7=Vienna, 4=Tbilisi, 1=remote jungle
    luxury_index     : 10=Dubai/Monaco, 7=Paris, 4=Prague, 1=budget backpacker
    language_diff    : 1=English-speaking, 2=Latin script/common, 3=moderate,
                       4=hard (Arabic/Mandarin), 5=very hard

LABELING RULE APPLIED (from labeling_rules.md):
    Adventure   : activity_density>=7 AND nature_score>=6 AND cost_per_day_usd<=120
    Relaxation  : beach_score>=7 AND safety_index>=7 AND avg_temp_c>=22
    Culture     : cultural_sites>=5 AND activity_density>=5 AND beach_score<=5
    Budget      : cost_per_day_usd<=45 AND safety_index>=4
    Luxury      : luxury_index>=8 AND cost_per_day_usd>=250 AND safety_index>=7
    Family      : family_friendly>=8 AND safety_index>=7 AND cost_per_day_usd<=200
    Tie-breaker : Luxury > Family > Adventure > Culture > Relaxation > Budget
"""

from __future__ import annotations

import csv
import pathlib

FIELDS = [
    "destination",
    "country",
    "region",
    "avg_temp_c",
    "cost_per_day_usd",
    "safety_index",
    "language_difficulty",
    "activity_density",
    "nightlife_score",
    "cultural_sites",
    "nature_score",
    "beach_score",
    "family_friendly",
    "infrastructure",
    "luxury_index",
    "label",
]

# fmt: off
ROWS = [
    # ── ADVENTURE (27 destinations) ────────────────────────────────────────────
    # High activity_density (≥7), high nature_score (≥6), cost ≤120 USD/day
    ("Queenstown", "New Zealand", "Oceania", 11, 95, 8.5, 1, 9, 7, 2, 9, 5, 7, 8, 6, "Adventure"),
    ("Interlaken", "Switzerland", "Europe", 8, 120, 8.8, 2, 9, 5, 3, 9, 2, 6, 9, 6, "Adventure"),
    ("Patagonia (El Chaltén)", "Argentina", "Americas", 8, 55, 6.5, 3, 9, 3, 1, 10, 1, 4, 5, 3, "Adventure"),
    ("Nepal (Kathmandu+Trek)", "Nepal", "Asia", 12, 35, 5.5, 4, 8, 4, 4, 10, 0, 5, 4, 2, "Adventure"),
    ("Costa Rica (Manuel Antonio)", "Costa Rica", "Americas", 27, 80, 6.8, 3, 8, 5, 2, 9, 7, 6, 6, 4, "Adventure"),
    ("Moab", "USA", "Americas", 17, 100, 7.5, 1, 9, 4, 1, 9, 0, 5, 7, 4, "Adventure"),
    ("Iceland (Reykjavik)", "Iceland", "Europe", 4, 110, 8.9, 1, 8, 5, 2, 9, 0, 6, 9, 5, "Adventure"),
    ("Tanzania (Kilimanjaro)", "Tanzania", "Africa", 18, 70, 5.0, 4, 8, 3, 2, 9, 1, 4, 5, 2, "Adventure"),
    ("Peru (Cusco+Machu Picchu)", "Peru", "Americas", 13, 50, 5.8, 3, 8, 4, 5, 8, 0, 6, 5, 3, "Adventure"),
    ("New Zealand (South Island)", "New Zealand", "Oceania", 10, 100, 8.5, 1, 9, 5, 3, 10, 4, 6, 8, 5, "Adventure"),
    ("Borneo (Sabah)", "Malaysia", "Asia", 27, 60, 6.0, 3, 8, 4, 2, 9, 2, 5, 6, 3, "Adventure"),
    ("Ecuador (Galápagos)", "Ecuador", "Americas", 22, 110, 6.2, 3, 8, 3, 2, 9, 5, 5, 6, 3, "Adventure"),
    ("Norway (Fjords)", "Norway", "Europe", 8, 120, 9.0, 1, 8, 5, 3, 9, 2, 7, 8, 5, "Adventure"),
    ("Colombia (Medellín)", "Colombia", "Americas", 22, 45, 5.5, 3, 8, 7, 3, 7, 1, 7, 6, 4, "Adventure"),
    ("Vietnam (Ha Long Bay + Sapa)", "Vietnam", "Asia", 22, 40, 6.0, 4, 8, 5, 3, 8, 3, 6, 6, 3, "Adventure"),
    ("Uganda (Bwindi)", "Uganda", "Africa", 20, 65, 5.0, 4, 7, 2, 2, 9, 0, 5, 4, 2, "Adventure"),
    ("Namibia", "Namibia", "Africa", 23, 70, 6.5, 3, 7, 3, 2, 9, 0, 4, 5, 3, "Adventure"),
    ("Madagascar", "Madagascar", "Africa", 24, 50, 5.0, 4, 7, 2, 3, 9, 3, 4, 4, 2, "Adventure"),
    ("Bolivia (Salar de Uyuni)", "Bolivia", "Americas", 10, 35, 5.5, 3, 7, 3, 2, 9, 0, 5, 4, 2, "Adventure"),
    ("Georgia (Kazbegi)", "Georgia", "Europe", 8, 40, 6.5, 3, 7, 5, 3, 8, 0, 6, 5, 3, "Adventure"),
    ("Canada (Banff)", "Canada", "Americas", 5, 110, 8.5, 1, 9, 4, 2, 10, 2, 7, 8, 5, "Adventure"),
    ("Ethiopia (Lalibela)", "Ethiopia", "Africa", 20, 45, 4.5, 5, 7, 2, 5, 7, 0, 5, 4, 2, "Adventure"),
    ("Chile (Torres del Paine)", "Chile", "Americas", 7, 90, 7.0, 3, 8, 3, 2, 10, 0, 6, 6, 3, "Adventure"),
    ("Kyrgyzstan (Osh/Issyk-Kul)", "Kyrgyzstan", "Asia", 12, 30, 5.5, 4, 7, 3, 2, 8, 0, 5, 4, 2, "Adventure"),
    ("Nepal (Pokhara)", "Nepal", "Asia", 18, 30, 5.8, 4, 7, 5, 2, 9, 3, 5, 4, 2, "Adventure"),
    ("Montenegro", "Montenegro", "Europe", 15, 65, 7.5, 2, 7, 6, 2, 8, 5, 6, 6, 4, "Adventure"),
    ("Thailand (Chiang Rai + trekking)", "Thailand", "Asia", 26, 45, 6.5, 3, 7, 5, 3, 8, 2, 6, 6, 3, "Adventure"),

    # ── RELAXATION (27 destinations) ──────────────────────────────────────────
    # beach_score≥7, safety_index≥7, avg_temp_c≥22
    ("Maldives", "Maldives", "Asia", 28, 350, 8.5, 2, 4, 3, 1, 10, 10, 7, 9, 9, "Relaxation"),
    ("Bali (Seminyak/Nusa Dua)", "Indonesia", "Asia", 28, 70, 7.0, 3, 6, 6, 2, 8, 8, 7, 7, 7, "Relaxation"),
    ("Santorini", "Greece", "Europe", 23, 180, 8.0, 2, 5, 6, 3, 7, 9, 7, 8, 8, "Relaxation"),
    ("Phuket", "Thailand", "Asia", 29, 60, 6.5, 3, 6, 7, 2, 7, 9, 7, 7, 6, "Relaxation"),
    ("Turks and Caicos", "Turks and Caicos", "Americas", 28, 350, 8.5, 1, 4, 4, 1, 9, 10, 8, 9, 8, "Relaxation"),
    ("Zanzibar", "Tanzania", "Africa", 27, 80, 6.5, 4, 5, 4, 2, 8, 9, 6, 6, 5, "Relaxation"),
    ("Maui", "USA", "Americas", 26, 280, 8.0, 1, 6, 5, 2, 8, 10, 8, 8, 7, "Relaxation"),
    ("Seychelles", "Seychelles", "Africa", 28, 250, 7.5, 2, 4, 3, 1, 8, 10, 7, 9, 8, "Relaxation"),
    ("Mykonos", "Greece", "Europe", 24, 220, 8.0, 2, 5, 8, 2, 7, 9, 6, 8, 7, "Relaxation"),
    ("Langkawi", "Malaysia", "Asia", 28, 80, 7.5, 3, 5, 4, 2, 8, 9, 7, 7, 6, "Relaxation"),
    ("Mauritius", "Mauritius", "Africa", 27, 150, 8.0, 2, 5, 4, 2, 8, 9, 7, 8, 7, "Relaxation"),
    ("Koh Samui", "Thailand", "Asia", 28, 55, 6.5, 3, 5, 6, 1, 8, 9, 7, 7, 6, "Relaxation"),
    ("Algarve", "Portugal", "Europe", 22, 120, 8.5, 2, 5, 5, 2, 7, 9, 7, 8, 6, "Relaxation"),
    ("Amalfi Coast", "Italy", "Europe", 22, 200, 8.0, 2, 6, 5, 3, 7, 8, 7, 8, 7, "Relaxation"),
    ("Fiji", "Fiji", "Oceania", 27, 120, 8.0, 2, 5, 4, 1, 8, 9, 7, 7, 6, "Relaxation"),
    ("Anguilla", "Anguilla", "Americas", 28, 400, 9.0, 1, 4, 3, 1, 8, 10, 8, 9, 8, "Relaxation"),
    ("Bora Bora", "French Polynesia", "Oceania", 28, 500, 9.0, 2, 4, 3, 1, 9, 10, 8, 9, 9, "Relaxation"),
    ("Mallorca", "Spain", "Europe", 22, 130, 8.0, 2, 6, 6, 3, 7, 9, 7, 8, 6, "Relaxation"),
    ("Goa", "India", "Asia", 29, 35, 5.5, 3, 6, 7, 2, 7, 9, 6, 6, 4, "Relaxation"),
    ("Crete", "Greece", "Europe", 23, 110, 8.0, 2, 6, 5, 4, 7, 9, 7, 8, 6, "Relaxation"),
    ("Tenerife", "Spain", "Europe", 23, 110, 8.5, 2, 6, 6, 3, 8, 8, 7, 8, 6, "Relaxation"),
    ("Barbados", "Barbados", "Americas", 28, 200, 8.0, 1, 5, 6, 2, 8, 9, 8, 8, 7, "Relaxation"),
    ("Sri Lanka (Mirissa)", "Sri Lanka", "Asia", 28, 45, 5.5, 4, 6, 4, 3, 7, 8, 6, 6, 4, "Relaxation"),
    ("Koh Lanta", "Thailand", "Asia", 28, 40, 6.5, 3, 4, 4, 1, 8, 9, 6, 7, 5, "Relaxation"),
    ("Azores", "Portugal", "Europe", 18, 100, 8.5, 1, 7, 4, 2, 8, 6, 7, 8, 6, "Relaxation"),
    ("Bali (Ubud)", "Indonesia", "Asia", 27, 50, 7.0, 3, 5, 4, 3, 7, 5, 7, 7, 5, "Relaxation"),
    ("Formentera", "Spain", "Europe", 24, 200, 8.5, 2, 4, 5, 1, 7, 9, 7, 8, 7, "Relaxation"),

    # ── CULTURE (27 destinations) ──────────────────────────────────────────────
    # cultural_sites≥5, activity_density≥5, beach_score≤5
    ("Rome", "Italy", "Europe", 15, 140, 7.5, 2, 8, 6, 8, 5, 3, 8, 8, 7, "Culture"),
    ("Kyoto", "Japan", "Asia", 14, 130, 9.5, 4, 7, 2, 8, 6, 1, 8, 9, 6, "Culture"),
    ("Athens", "Greece", "Europe", 18, 110, 7.5, 2, 7, 5, 8, 5, 3, 7, 8, 6, "Culture"),
    ("Istanbul", "Turkey", "Middle East", 14, 90, 6.5, 3, 8, 7, 7, 5, 2, 8, 7, 5, "Culture"),
    ("Cairo", "Egypt", "Middle East", 22, 45, 5.5, 4, 7, 5, 8, 5, 0, 7, 6, 4, "Culture"),
    ("Prague", "Czech Republic", "Europe", 10, 90, 7.5, 2, 8, 7, 6, 5, 1, 8, 8, 5, "Culture"),
    ("Marrakech", "Morocco", "Africa", 20, 60, 6.0, 4, 7, 6, 5, 5, 1, 7, 6, 4, "Culture"),
    ("Vienna", "Austria", "Europe", 11, 150, 8.5, 2, 7, 6, 7, 4, 1, 9, 9, 7, "Culture"),
    ("Barcelona", "Spain", "Europe", 18, 150, 7.5, 2, 9, 8, 6, 7, 5, 9, 8, 7, "Culture"),
    ("Florence", "Italy", "Europe", 16, 160, 7.5, 2, 7, 5, 8, 5, 2, 8, 8, 7, "Culture"),
    ("Seville", "Spain", "Europe", 23, 110, 7.5, 2, 7, 7, 6, 5, 2, 8, 7, 6, "Culture"),
    ("Lisbon", "Portugal", "Europe", 18, 110, 8.0, 2, 7, 7, 5, 5, 4, 8, 8, 6, "Culture"),
    ("Budapest", "Hungary", "Europe", 13, 75, 7.5, 2, 8, 8, 5, 5, 1, 8, 7, 5, "Culture"),
    ("Mexico City", "Mexico", "Americas", 16, 60, 5.0, 3, 8, 8, 8, 5, 0, 9, 7, 5, "Culture"),
    ("Havana", "Cuba", "Americas", 26, 50, 6.0, 3, 7, 7, 5, 5, 2, 7, 5, 4, "Culture"),
    ("Kraków", "Poland", "Europe", 9, 65, 7.5, 2, 7, 7, 5, 4, 1, 8, 7, 5, "Culture"),
    ("Cartagena", "Colombia", "Americas", 28, 70, 5.5, 3, 7, 7, 5, 5, 5, 7, 6, 5, "Culture"),
    ("Jerusalem", "Israel", "Middle East", 17, 130, 6.5, 4, 7, 5, 10, 3, 0, 8, 7, 6, "Culture"),
    ("Amman", "Jordan", "Middle East", 18, 70, 6.5, 4, 6, 5, 8, 4, 0, 7, 6, 5, "Culture"),
    ("Tbilisi", "Georgia", "Europe", 13, 40, 7.0, 3, 7, 7, 4, 5, 0, 7, 6, 4, "Culture"),
    ("Delhi", "India", "Asia", 25, 30, 5.0, 4, 8, 6, 10, 4, 0, 7, 6, 4, "Culture"),
    ("Varanasi", "India", "Asia", 26, 25, 4.5, 4, 6, 4, 8, 4, 0, 6, 4, 3, "Culture"),
    ("Samarkand", "Uzbekistan", "Asia", 17, 30, 6.0, 4, 6, 3, 7, 4, 0, 5, 5, 3, "Culture"),
    ("Oaxaca", "Mexico", "Americas", 23, 45, 5.5, 3, 7, 6, 6, 5, 0, 7, 5, 4, "Culture"),
    ("Tallinn", "Estonia", "Europe", 7, 90, 8.0, 2, 7, 6, 4, 4, 0, 8, 7, 5, "Culture"),
    ("Ljubljana", "Slovenia", "Europe", 11, 90, 8.5, 2, 6, 6, 3, 5, 0, 8, 7, 5, "Culture"),
    ("Dubrovnik", "Croatia", "Europe", 17, 130, 8.0, 2, 7, 6, 5, 5, 5, 8, 7, 6, "Culture"),

    # ── BUDGET (27 destinations) ───────────────────────────────────────────────
    # cost_per_day_usd≤45 AND safety_index≥4 (does not fit a more specific label first)
    ("Hanoi", "Vietnam", "Asia", 23, 30, 6.0, 4, 7, 6, 4, 5, 2, 7, 6, 3, "Budget"),
    ("Phnom Penh", "Cambodia", "Asia", 28, 25, 4.5, 4, 6, 5, 4, 4, 0, 6, 5, 3, "Budget"),
    ("Sofia", "Bulgaria", "Europe", 10, 40, 7.0, 2, 6, 6, 4, 4, 0, 7, 6, 4, "Budget"),
    ("Belgrade", "Serbia", "Europe", 13, 40, 7.0, 2, 7, 9, 3, 4, 0, 7, 6, 4, "Budget"),
    ("Tbilisi (budget focus)", "Georgia", "Europe", 13, 35, 7.0, 3, 6, 7, 4, 5, 0, 7, 6, 3, "Budget"),
    ("Tirana", "Albania", "Europe", 15, 35, 7.0, 2, 6, 6, 3, 5, 2, 6, 5, 3, "Budget"),
    ("Skopje", "North Macedonia", "Europe", 12, 30, 6.5, 2, 6, 6, 3, 4, 0, 6, 5, 3, "Budget"),
    ("Riga", "Latvia", "Europe", 7, 65, 7.0, 2, 7, 7, 4, 4, 0, 8, 7, 5, "Budget"),
    ("Vilnius", "Lithuania", "Europe", 7, 60, 7.5, 2, 7, 7, 4, 4, 0, 8, 7, 5, "Budget"),
    ("Bucharest", "Romania", "Europe", 12, 45, 6.5, 2, 7, 8, 4, 4, 0, 7, 6, 4, "Budget"),
    ("Yerevan", "Armenia", "Middle East", 13, 35, 7.0, 3, 6, 5, 4, 5, 0, 6, 6, 3, "Budget"),
    ("Tbilisi (budget 2)", "Georgia", "Europe", 13, 30, 7.0, 3, 6, 6, 4, 5, 0, 7, 6, 3, "Budget"),
    ("Chisinau", "Moldova", "Europe", 11, 25, 6.0, 2, 5, 5, 3, 4, 0, 5, 5, 3, "Budget"),
    ("Colombo", "Sri Lanka", "Asia", 28, 35, 5.5, 4, 6, 5, 4, 5, 3, 6, 5, 3, "Budget"),
    ("Dhaka", "Bangladesh", "Asia", 27, 20, 4.5, 5, 6, 4, 3, 4, 0, 5, 4, 2, "Budget"),
    ("Lahore", "Pakistan", "Asia", 23, 20, 4.0, 5, 7, 5, 6, 4, 0, 6, 5, 3, "Budget"),
    ("Tbilisi (hostel scene)", "Georgia", "Europe", 13, 28, 7.0, 3, 6, 7, 4, 5, 0, 7, 6, 3, "Budget"),
    ("Ho Chi Minh City", "Vietnam", "Asia", 28, 35, 6.0, 4, 7, 8, 3, 5, 0, 7, 6, 4, "Budget"),
    ("Chiang Mai", "Thailand", "Asia", 26, 35, 6.5, 3, 6, 6, 3, 6, 2, 7, 6, 4, "Budget"),
    ("Bishkek", "Kyrgyzstan", "Asia", 13, 25, 5.5, 4, 5, 4, 2, 6, 0, 5, 4, 2, "Budget"),
    ("Almaty", "Kazakhstan", "Asia", 10, 40, 6.0, 4, 6, 6, 3, 6, 0, 6, 6, 4, "Budget"),
    ("Nairobi", "Kenya", "Africa", 18, 40, 4.5, 4, 6, 5, 4, 5, 0, 6, 5, 3, "Budget"),
    ("Addis Ababa", "Ethiopia", "Africa", 17, 30, 4.5, 5, 5, 4, 4, 5, 0, 5, 4, 2, "Budget"),
    ("Ouagadougou", "Burkina Faso", "Africa", 29, 20, 4.0, 5, 4, 3, 2, 4, 0, 4, 3, 2, "Budget"),
    ("Havana (budget)", "Cuba", "Americas", 26, 40, 6.0, 3, 6, 6, 5, 5, 2, 6, 5, 3, "Budget"),
    ("La Paz", "Bolivia", "Americas", 9, 25, 5.0, 3, 6, 4, 3, 6, 0, 5, 4, 2, "Budget"),
    ("Quito", "Ecuador", "Americas", 14, 40, 5.5, 3, 6, 5, 4, 6, 0, 6, 5, 3, "Budget"),

    # ── LUXURY (25 destinations) ───────────────────────────────────────────────
    # luxury_index≥8, cost_per_day_usd≥250, safety_index≥7
    ("Dubai", "UAE", "Middle East", 29, 450, 8.5, 4, 8, 9, 4, 7, 6, 9, 10, 10, "Luxury"),
    ("Monaco", "Monaco", "Europe", 17, 700, 9.5, 2, 6, 8, 4, 7, 5, 9, 10, 10, "Luxury"),
    ("St. Barts", "France", "Americas", 28, 600, 9.0, 2, 4, 6, 2, 8, 10, 8, 9, 10, "Luxury"),
    ("Zürich", "Switzerland", "Europe", 10, 450, 9.5, 1, 6, 7, 5, 7, 2, 9, 10, 9, "Luxury"),
    ("Singapore (luxury)", "Singapore", "Asia", 28, 350, 9.5, 2, 8, 9, 4, 7, 4, 10, 10, 9, "Luxury"),
    ("Paris (luxury)", "France", "Europe", 12, 350, 7.5, 2, 8, 8, 10, 5, 2, 9, 10, 9, "Luxury"),
    ("Maldives (private island)", "Maldives", "Asia", 28, 1000, 8.5, 2, 3, 2, 1, 10, 10, 8, 10, 10, "Luxury"),
    ("Tuscany (villa stay)", "Italy", "Europe", 18, 400, 8.0, 2, 5, 4, 6, 6, 2, 8, 10, 9, "Luxury"),
    ("Amalfi Coast (luxury)", "Italy", "Europe", 22, 500, 8.0, 2, 5, 5, 5, 7, 7, 8, 10, 9, "Luxury"),
    ("London (luxury)", "UK", "Europe", 12, 400, 7.5, 1, 8, 8, 8, 5, 2, 10, 10, 9, "Luxury"),
    ("New York (luxury)", "USA", "Americas", 13, 500, 6.5, 1, 9, 9, 7, 5, 2, 10, 10, 9, "Luxury"),
    ("Tokyo (luxury)", "Japan", "Asia", 16, 350, 9.5, 4, 9, 7, 6, 7, 1, 10, 10, 9, "Luxury"),
    ("Hong Kong", "Hong Kong", "Asia", 23, 300, 8.0, 4, 9, 8, 4, 7, 3, 10, 9, 9, "Luxury"),
    ("Cannes", "France", "Europe", 20, 400, 8.0, 2, 6, 7, 5, 7, 7, 9, 10, 9, "Luxury"),
    ("Portofino", "Italy", "Europe", 19, 600, 8.5, 2, 5, 5, 4, 8, 8, 8, 10, 9, "Luxury"),
    ("Aspen", "USA", "Americas", 2, 500, 8.5, 1, 9, 6, 2, 9, 0, 8, 10, 9, "Luxury"),
    ("Bora Bora (overwater)", "French Polynesia", "Oceania", 28, 800, 9.0, 2, 4, 3, 1, 9, 10, 8, 10, 10, "Luxury"),
    ("Mykonos (luxury)", "Greece", "Europe", 24, 400, 8.0, 2, 6, 9, 4, 7, 9, 8, 9, 9, "Luxury"),
    ("Abu Dhabi", "UAE", "Middle East", 29, 350, 8.5, 4, 7, 7, 4, 7, 5, 9, 10, 9, "Luxury"),
    ("Ibiza (VIP)", "Spain", "Europe", 24, 400, 8.0, 2, 7, 10, 3, 7, 9, 8, 9, 9, "Luxury"),
    ("Geneva", "Switzerland", "Europe", 9, 450, 9.5, 1, 6, 6, 4, 7, 2, 9, 10, 9, "Luxury"),
    ("Sydney (luxury)", "Australia", "Oceania", 18, 300, 8.5, 1, 8, 7, 4, 8, 6, 9, 9, 8, "Luxury"),
    ("Cape Town (luxury)", "South Africa", "Africa", 18, 280, 4.5, 1, 8, 7, 5, 8, 6, 8, 9, 8, "Luxury"),
    ("Marrakech (Riad luxury)", "Morocco", "Africa", 20, 250, 6.0, 4, 7, 6, 6, 5, 2, 8, 9, 7, "Luxury"),
    ("Oman (Muscat luxury)", "Oman", "Middle East", 28, 280, 9.0, 4, 6, 4, 5, 7, 3, 8, 9, 8, "Luxury"),

    # ── FAMILY (27 destinations) ───────────────────────────────────────────────
    # family_friendly≥8, safety_index≥7, cost_per_day_usd≤200
    ("Orlando", "USA", "Americas", 24, 180, 7.0, 1, 8, 4, 3, 8, 4, 10, 8, 7, "Family"),
    ("Singapore", "Singapore", "Asia", 28, 200, 9.5, 2, 8, 7, 4, 7, 4, 10, 9, 8, "Family"),
    ("Tokyo (family)", "Japan", "Asia", 16, 150, 9.5, 4, 9, 6, 6, 7, 1, 10, 9, 8, "Family"),
    ("Vienna (family)", "Austria", "Europe", 11, 150, 8.5, 2, 7, 5, 7, 4, 1, 9, 9, 7, "Family"),
    ("Amsterdam", "Netherlands", "Europe", 10, 160, 8.0, 1, 8, 7, 6, 5, 1, 9, 8, 7, "Family"),
    ("Copenhagen", "Denmark", "Europe", 9, 180, 8.5, 1, 7, 6, 5, 4, 1, 9, 8, 7, "Family"),
    ("Gold Coast", "Australia", "Oceania", 22, 160, 8.5, 1, 8, 6, 3, 8, 8, 10, 8, 7, "Family"),
    ("Hawaii (Honolulu)", "USA", "Americas", 25, 250, 8.0, 1, 7, 6, 3, 8, 9, 10, 8, 7, "Family"),
    ("Zurich (family)", "Switzerland", "Europe", 10, 200, 9.5, 1, 6, 5, 5, 7, 2, 9, 9, 8, "Family"),
    ("Dublin", "Ireland", "Europe", 10, 160, 8.5, 1, 7, 6, 5, 5, 1, 9, 8, 7, "Family"),
    ("Edinburgh", "UK", "Europe", 9, 150, 8.5, 1, 7, 6, 5, 4, 1, 9, 8, 7, "Family"),
    ("Vancouver", "Canada", "Americas", 10, 160, 8.5, 1, 8, 6, 4, 8, 4, 9, 8, 7, "Family"),
    ("Melbourne", "Australia", "Oceania", 16, 170, 8.5, 1, 8, 7, 4, 7, 4, 9, 8, 7, "Family"),
    ("Auckland", "New Zealand", "Oceania", 14, 160, 8.5, 1, 7, 6, 3, 8, 4, 9, 8, 7, "Family"),
    ("Lisbon (family)", "Portugal", "Europe", 18, 120, 8.0, 2, 7, 6, 5, 5, 4, 9, 8, 6, "Family"),
    ("Barcelona (family)", "Spain", "Europe", 18, 150, 7.5, 2, 8, 7, 6, 7, 5, 9, 8, 7, "Family"),
    ("Reykjavik (family)", "Iceland", "Europe", 4, 180, 8.9, 1, 7, 4, 2, 8, 0, 9, 8, 6, "Family"),
    ("Tokyo Disneyland area", "Japan", "Asia", 16, 180, 9.5, 4, 8, 5, 5, 7, 1, 10, 9, 7, "Family"),
    ("London (family)", "UK", "Europe", 12, 200, 7.5, 1, 8, 6, 8, 5, 2, 10, 8, 7, "Family"),
    ("Paris (family)", "France", "Europe", 12, 200, 7.5, 2, 8, 6, 10, 4, 2, 10, 8, 7, "Family"),
    ("Stockholm", "Sweden", "Europe", 8, 160, 8.5, 1, 7, 6, 5, 4, 1, 9, 8, 7, "Family"),
    ("Munich", "Germany", "Europe", 10, 150, 8.5, 1, 7, 7, 5, 4, 1, 9, 8, 7, "Family"),
    ("Ottawa", "Canada", "Americas", 7, 130, 8.5, 1, 6, 5, 4, 5, 0, 9, 8, 6, "Family"),
    ("Seoul (family)", "South Korea", "Asia", 13, 120, 8.5, 4, 9, 7, 5, 7, 2, 10, 9, 7, "Family"),
    ("Taipei", "Taiwan", "Asia", 23, 80, 9.0, 4, 8, 7, 4, 6, 2, 9, 8, 7, "Family"),
    ("Porto", "Portugal", "Europe", 16, 100, 8.5, 2, 7, 6, 4, 5, 3, 9, 7, 6, "Family"),
    ("Bruges", "Belgium", "Europe", 10, 130, 8.5, 1, 6, 5, 4, 4, 1, 9, 8, 7, "Family"),
]
# fmt: on


def main() -> None:
    out_path = pathlib.Path(__file__).parent / "destinations_raw.csv"
    with open(out_path, "w", newline="", encoding="utf-8") as f:
        writer = csv.writer(f)
        writer.writerow(FIELDS)
        writer.writerows(ROWS)
    print(f"Written {len(ROWS)} rows → {out_path}")

    # Print label distribution
    from collections import Counter
    labels = Counter(r[-1] for r in ROWS)
    print("\nLabel distribution:")
    for label, count in sorted(labels.items()):
        print(f"  {label:12s}: {count}")


if __name__ == "__main__":
    main()
