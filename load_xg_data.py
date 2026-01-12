"""
Quick xG Data Loader
Run this script to load xG data for all leagues
"""

import sys
sys.path.insert(0, '/mnt/user-data/outputs')

from data_engine import DataEngine
from api_football import APIFootball

# API Keys
FOOTBALL_DATA_KEY = "ef8c2eb9be6b43fe8353c99f51904c0f"
API_FOOTBALL_KEY = "1a1c70f5c48bfdce946b71680e47e92e"

print("🚀 BTTS Pro Analyzer - xG Data Loader")
print("=" * 50)
print()

# Initialize
engine = DataEngine(
    api_key=FOOTBALL_DATA_KEY,
    api_football_key=API_FOOTBALL_KEY
)

# Leagues to load (12 total)
leagues = [
    'BL1',  # Bundesliga
    'PL',   # Premier League
    'PD',   # La Liga
    'SA',   # Serie A
    'FL1',  # Ligue 1
    'DED',  # Eredivisie
    'ELC',  # Championship
    'PPL',  # Primeira Liga
    'BSA',  # Brasileirão
    'BEL',  # Belgian Pro League
    'SWE',  # Allsvenskan
    'NOR',  # Eliteserien
]

print(f"📊 Loading xG data for {len(leagues)} leagues...")
print()

# Load xG for each league
for idx, league in enumerate(leagues):
    print(f"\n[{idx+1}/{len(leagues)}] {league}")
    print("-" * 40)
    
    try:
        # First ensure league data is loaded
        if league in ['BEL', 'SWE', 'NOR']:
            print(f"  Loading {league} matches first...")
            engine.refresh_league_data(league, season="2024")
        
        # Then load xG
        engine.load_xg_for_league(league, season=2024, limit=50)
        
    except Exception as e:
        print(f"  ❌ Error: {e}")
        continue

print("\n" + "=" * 50)
print("✅ xG Data Loading Complete!")
print()

# Show summary
import sqlite3
conn = sqlite3.connect('btts_data.db')
cursor = conn.cursor()

# Count matches with xG
cursor.execute('SELECT COUNT(*) FROM matches WHERE xg_home IS NOT NULL')
xg_count = cursor.fetchone()[0]

cursor.execute('SELECT COUNT(*) FROM matches WHERE status="FINISHED"')
total_count = cursor.fetchone()[0]

conn.close()

print(f"📊 Summary:")
print(f"  Total matches: {total_count}")
print(f"  Matches with xG: {xg_count} ({xg_count/total_count*100:.1f}%)")
print()
print("🎉 Ready for ML training with xG!")
