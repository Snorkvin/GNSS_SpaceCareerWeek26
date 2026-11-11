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


# Stage 2: Load GP JSON and Extract Assets

def extract_inputs():
    """
    Checks for required inputs in IN_DIR. If missing, monitors /content
    for an uploaded zip file, validates, and extracts the required files.
    """
    required_files = ['orbital_elements.json', 'data_manifest.json', 'world_map.txt']
    all_exist = all((IN_DIR / f).is_file() for f in required_files)
    
    if all_exist:
        print("All required input files already exist in input directory.")
        return

    print("--- Action Required ---")
    print("Please drag and drop 'orbit_workshop_inputs.zip' into the /content folder using the Colab Files panel.")
    print("Waiting for upload...")
    
    zip_path = None
    start_time = time.time()
    timeout = 15 * 60  # 15 minutes
    
    while True:
        if time.time() - start_time > timeout:
            raise TimeoutError("Upload timeout exceeded. Please upload the zip file and rerun this cell.")
            
        # Search for any zip file matching the pattern in /content
        for p in Path('/content').glob('orbit_workshop_inputs*.zip'):
            if zipfile.is_zipfile(p):
                zip_path = p
                break
        
        if zip_path:
            break
        time.sleep(2)
        
    print(f"Found valid ZIP archive: {zip_path.name}. Extracting files...")
    with zipfile.ZipFile(zip_path, 'r') as ref:
        # Extract only the three required files to IN_DIR
        for member in ref.namelist():
            name = Path(member).name
            if name in required_files:
                target_path = IN_DIR / name
                with open(target_path, 'wb') as out_f:
                    out_f.write(ref.read(member))
                print(f" Extracted: {name} -> {target_path}")

def read_gp_json(path):
    """
    Loads a CelesTrak OMM JSON file and validates that each record contains the necessary elements.
    """
    required_keys = {
        'OBJECT_NAME', 'NORAD_CAT_ID', 'EPOCH', 'MEAN_MOTION',
        'ECCENTRICITY', 'INCLINATION', 'RA_OF_ASC_NODE',
        'ARG_OF_PERICENTER', 'MEAN_ANOMALY'
    }
    
    with open(path, 'r') as f:
        records = json.load(f)
        
    # Validate elements
    for i, record in enumerate(records):
        missing = required_keys - record.keys()
        if missing:
            raise ValueError(f"Record at index {i} is missing required fields: {missing}")
            
    return records

# --- Execution ---
extract_inputs()

# Load files
sats = read_gp_json(IN_DIR / 'orbital_elements.json')
with open(IN_DIR / 'data_manifest.json', 'r') as f:
    data_manifest = json.load(f)

# Display metadata
source_note = f"Data sourced from CelesTrak, retrieved at UTC: {data_manifest.get('retrieved_utc', 'N/A')}"
print(f"\n{source_note}")
print(f"Loaded {len(sats)} satellite record(s):\n")
for sat in sats:
    print(f"- Name: {sat['OBJECT_NAME']:<20} | NORAD ID: {sat['NORAD_CAT_ID']:<6} | Epoch: {sat['EPOCH']}")

    