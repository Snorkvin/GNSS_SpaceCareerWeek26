#!/usr/bin/env python

# GNSS Space Week 2026
# M.Sc. Marvin Westerholz
# Embedded Software Engineer
# Germany
# Keplerian elements: a e i OMEGA w v
#  
# F = M*a
# f=m*r°° 

# Stage 1: Setup, Imports, Constants, and Directory Structures
import json
import math
import time
import zipfile
import xml.etree.ElementTree as ET
from datetime import datetime, timedelta, timezone
from pathlib import Path
import matplotlib.pyplot as plt
import matplotlib.colors as mcolors
import requests

# --- Constants (Conventions: km, km/s, UTC-aware) ---
MU_EARTH_KM3_S2 = 398600.4418  # Earth's gravitational parameter GM
EARTH_RADIUS_KM = 6378.137      # Earth's equatorial radius (WGS-84)

# --- Directory Setup ---
BASE_DIR = Path(__file__).resolve().parent / 'content/satellite_orbits'
IN_DIR = BASE_DIR / 'input'
OUT_DIR = BASE_DIR / 'output'

IN_DIR.mkdir(parents=True, exist_ok=True)
OUT_DIR.mkdir(parents=True, exist_ok=True)

# --- Simulation Configurations ---
STEP_SECONDS = 5
DURATION_HOURS = 24
LIVE_GROUP = None  # Reserved for potential extensions

# --- Diagnostic Output ---
print("=== Stage 1 Setup Completed Successfully ===")
print(f"Input Directory  : {IN_DIR}")
print(f"Output Directory : {OUT_DIR}")
print(f"Step Duration    : {STEP_SECONDS} seconds")
print(f"Total Duration   : {DURATION_HOURS} hours")
print(f"Live Group       : {LIVE_GROUP}")