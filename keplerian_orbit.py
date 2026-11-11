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


def parse_gp_epoch(text):
    """
    Parses a UTC ISO format timestamp from CelesTrak (without offset/with trailing Z)
    to a Python UTC-aware datetime.
    """
    clean_text = text.rstrip('Z')
    # Use timezone-aware UTC datetime
    return datetime.fromisoformat(clean_text).replace(tzinfo=timezone.utc)

def parse_gp_elements(rec):
    """
    Converts a raw GP record (dict) into classical orbital elements in model units (km, rad, rad/s).
    """
    name = rec['OBJECT_NAME']
    norad_id = int(rec['NORAD_CAT_ID'])
    epoch = parse_gp_epoch(rec['EPOCH'])
    
    # Mean motion: rev/day -> rad/s
    n_rev_day = float(rec['MEAN_MOTION'])
    n_rad_s = n_rev_day * (2.0 * math.pi) / 86400.0
    
    # Semi-major axis from Kepler's Third Law: a = (mu / n^2) ^ (1/3)
    a_km = (MU_EARTH_KM3_S2 / (n_rad_s ** 2)) ** (1.3 / 3.0)  # Correct Keplerian 1/3 exponent
    a_km = (MU_EARTH_KM3_S2 / (n_rad_s ** 2)) ** (1.0 / 3.0)
    
    e = float(rec['ECCENTRICITY'])
    
    # Degrees to Radians
    i_rad = math.radians(float(rec['INCLINATION']))
    raan_rad = math.radians(float(rec['RA_OF_ASC_NODE']))
    argp_rad = math.radians(float(rec['ARG_OF_PERICENTER']))
    M0_rad = math.radians(float(rec['MEAN_ANOMALY']))
    
    return {
        'name': name,
        'norad_id': norad_id,
        'label': f"{name} [{norad_id}]",
        'epoch': epoch,
        'n_rad_s': n_rad_s,
        'a_km': a_km,
        'e': e,
        'i_rad': i_rad,
        'raan_rad': raan_rad,
        'argp_rad': argp_rad,
        'M0_rad': M0_rad
    }

def elements_table(elements_list):
    """
    Returns a list of formatted lines representing a summary table of converted elements.
    """
    headers = f"{'Satellite Name':<18} | {'NORAD':<6} | {'Epoch (UTC)':<19} | {'a (km)':<9} | {'e':<8} | {'i (deg)':<7} | {'Ω (deg)':<7} | {'ω (deg)':<7} | {'M0 (deg)':<7}"
    separator = "-" * len(headers)
    lines = [headers, separator]
    
    for el in elements_list:
        epoch_str = el['epoch'].strftime('%Y-%m-%d %H:%M:%S')
        line = (f"{el['name'][:18]:<18} | "
                f"{el['norad_id']:<6} | "
                f"{epoch_str:<19} | "
                f"{el['a_km']:<9.2f} | "
                f"{el['e']:<8.6f} | "
                f"{math.degrees(el['i_rad']):<7.2f} | "
                f"{math.degrees(el['raan_rad']):<7.2f} | "
                f"{math.degrees(el['argp_rad']):<7.2f} | "
                f"{math.degrees(el['M0_rad']):<7.2f}")
        lines.append(line)
    return lines

# Check if input 'sats' exists from Stage 2
if 'sats' not in globals():
    raise NameError("Missing list of satellites 'sats'. Make sure Stage 2 executed successfully.")

# --- Convert Elements ---
elements = [parse_gp_elements(s) for s in sats]

# --- Display Elements Table ---
table_lines = elements_table(elements)
for line in table_lines:
    print(line)


# Stage 4: Establish a Unified UTC Time Grid & Check Record Age

# Ensure preceding stages executed and populated elements
if 'elements' not in globals() or not elements:
    raise NameError("Missing 'elements' list from Stage 3. Make sure to run Stage 2 and 3 first.")

# 1. Identify the newest epoch in our elements list
newest_epoch = max(el['epoch'] for el in elements)

# 2. Floor this newest epoch to UTC midnight to establish a clean starting baseline
sim_start = newest_epoch.replace(hour=0, minute=0, second=0, microsecond=0)
sim_end = sim_start + timedelta(hours=DURATION_HOURS)

# 3. Create the time grid (including both start and end endpoints)
total_seconds = int((sim_end - sim_start).total_seconds())
n_points = (total_seconds // STEP_SECONDS) + 1
times = [sim_start + timedelta(seconds=i * STEP_SECONDS) for i in range(n_points)]

# --- Diagnostics output ---
print("=== Stage 4: Unified Time Grid ===")
print(f"Newest Epoch in Data   : {newest_epoch.strftime('%Y-%m-%d %H:%M:%S %Z')}")
print(f"Simulation Start (UTC) : {sim_start.strftime('%Y-%m-%d %H:%M:%S %Z')}")
print(f"Simulation End (UTC)   : {sim_end.strftime('%Y-%m-%d %H:%M:%S %Z')}")
print(f"Step Interval          : {STEP_SECONDS} seconds")
print(f"Total Time Points      : {n_points:,}\n")

print("--- Satellite Epoch Offset (Age) Analysis ---")
for el in elements:
    # Calculate offset in fractional days
    offset_delta = sim_start - el['epoch']
    offset_days = offset_delta.total_seconds() / 86400.0
    
    # Check if the record is older than 7 days (stale)
    stale_flag = "[STALE RECORD]" if offset_days > 7.0 else "[FRESH]"
    
    print(f"- {el['label']:<25} | Age relative to sim start: {offset_days:6.2f} days | Status: {stale_flag}")


# Stage 5: Analytical Two-Body Keplerian Orbit Propagator

# Verification of prior dependencies
if 'elements' not in globals() or 'times' not in globals():
    raise NameError("Missing 'elements' list or simulation 'times' grid. Run prior stages first.")

def solve_kepler(M, e):
    """
    Solves Kepler's Equation M = E - e * sin(E) using Newton-Raphson iteration.
    """
    # 1. Select starting estimate based on eccentricity
    E = math.pi if e > 0.8 else M
    tol = 1e-12
    max_iter = 50
    
    for _ in range(max_iter):
        f = E - e * math.sin(E) - M
        f_prime = 1.0 - e * math.cos(E)
        delta = f / f_prime
        E_next = E - delta
        if abs(delta) < tol:
            return E_next
        E = E_next
        
    raise ValueError(f"Kepler solver failed to converge. M={M}, e={e}")

def gmst_rad(t):
    """
    Calculates Greenwich Mean Sidereal Time (GMST) in radians for a given UTC datetime.
    Uses IAU-1982 formulation (Meeus formula 12.4).
    """
    # J2000 epoch is January 1, 2000, at 12:00 UTC
    j2000 = datetime(2000, 1, 1, 12, 0, 0, tzinfo=timezone.utc)
    d = (t - j2000).total_seconds() / 86400.0
    T = d / 36525.0
    
    # Angle in degrees
    theta_deg = 280.46061837 + 360.98564736629 * d + 0.000387933 * (T ** 2) - (T ** 3) / 38710000.0
    return math.radians(theta_deg % 360.0)

# --- Verification Assertions ---
# 1. GMST at J2000 is approximately 280.46 degrees
j2000_check_time = datetime(2000, 1, 1, 12, 0, 0, tzinfo=timezone.utc)
assert abs(math.degrees(gmst_rad(j2000_check_time)) - 280.46061837) < 1e-5, "GMST at J2000 calculation discrepancy."

# 2. Kepler residual error check
for test_M, test_e in [(0.5, 0.1), (1.5, 0.7), (3.0, 0.05)]:
    test_E = solve_kepler(test_M, test_e)
    residual = abs(test_E - test_e * math.sin(test_E) - test_M)
    assert residual < 1e-10, f"Newton-Raphson failed precision threshold: residual={residual}"

def propagate(el, time_grid):
    """
    Propagates a satellite's orbit across a sequence of datetimes under two-body physics.
    """
    track = []
    a = el['a_km']
    e = el['e']
    i = el['i_rad']
    raan = el['raan_rad']
    argp = el['argp_rad']
    M0 = el['M0_rad']
    epoch = el['epoch']
    n = el['n_rad_s']
    
    for t in time_grid:
        # Step 1: Mean Anomaly computation
        dt_sec = (t - epoch).total_seconds()
        M = (M0 + n * dt_sec) % (2.0 * math.pi)
        
        # Step 2: Solve Kepler's equation for Eccentric Anomaly
        E = solve_kepler(M, e)
        
        # Step 3: Compute radial distance, true anomaly, and argument of latitude
        r = a * (1.0 - e * math.cos(E))
        nu = math.atan2(math.sqrt(1.0 - e ** 2) * math.sin(E), math.cos(E) - e)
        u = argp + nu
        
        # Step 4: Map coordinates to geocentric equatorial inertial frame (ECI)
        cos_u, sin_u = math.cos(u), math.sin(u)
        cos_raan, sin_raan = math.cos(raan), math.sin(raan)
        cos_i, sin_i = math.cos(i), math.sin(i)
        
        x = r * (cos_raan * cos_u - sin_raan * sin_u * cos_i)
        y = r * (sin_raan * cos_u + cos_raan * sin_u * cos_i)
        z = r * sin_u * sin_i
        
        # Step 5: Rotate into Earth-centered Earth-fixed (ECEF) frame using GMST
        theta = gmst_rad(t)
        cos_t, sin_t = math.cos(theta), math.sin(theta)
        xp = cos_t * x + sin_t * y
        yp = -sin_t * x + cos_t * y
        
        # Step 6: Convert ECEF coordinates to geodetic latitude, longitude, and altitude
        lat_rad = math.atan2(z, math.hypot(xp, yp))
        lon_rad = math.atan2(yp, xp)
        
        lat_deg = math.degrees(lat_rad)
        lon_deg = math.degrees(lon_rad)
        alt_km = r - EARTH_RADIUS_KM
        
        # Step 7: Instantaneous vis-viva speed
        speed_km_s = math.sqrt(MU_EARTH_KM3_S2 * (2.0 / r - 1.0 / a))
        
        track.append({
            'time': t,
            'lat_deg': lat_deg,
            'lon_deg': lon_deg,
            'alt_km': alt_km,
            'speed_km_s': speed_km_s
        })
        
    return track

# --- Perform Propagation ---
tracks = [propagate(el, times) for el in elements]

# 3. Assert longitudinal behavior for geostationary satellite SES-5 if present
for idx, el in enumerate(elements):
    if el['norad_id'] == 38652:  # SES-5
        ses5_track = tracks[idx]
        for point in ses5_track:
            lon = point['lon_deg']
            # Normalize longitude to [-180, 180]
            lon_norm = (lon + 180) % 360 - 180
            assert 4.0 <= lon_norm <= 6.0, f"SES-5 drifted outside [4, 6]° East. Found: {lon_norm}°"

# --- Display Propagation Diagnostics ---
print("=== Propagation Completed Successfully ===")
for idx, el in enumerate(elements):
    track = tracks[idx]
    print(f"\nSatellite: {el['label']}")
    for label, pt_idx in [("First", 0), ("Middle", len(track) // 2), ("Last", -1)]:
        p = track[pt_idx]
        print(f"  * {label:<6} Point | {p['time'].strftime('%H:%M:%S')} | Lat: {p['lat_deg']:7.2f}° | Lon: {p['lon_deg']:7.2f}° | Alt: {p['alt_km']:8.2f} km | Speed: {p['speed_km_s']:5.2f} km/s")


# Stage 6: Orbital Summary and Spacecraft Classification

# Ensure preceding stages executed and populated required elements and tracks
if 'elements' not in globals() or 'tracks' not in globals():
    raise NameError("Missing 'elements' or 'tracks' from previous stages. Ensure Stages 3 and 5 ran successfully.")

def orbit_summary(el, pts):
    """
    Computes key Keplerian and dynamic properties of an orbit, incorporating
    empirical velocity limits calculated during propagation.
    """
    a = el['a_km']
    e = el['e']
    n = el['n_rad_s']
    
    # Analytical Calculations
    period_h = (2.0 * math.pi) / n / 3600.0
    perigee_km = a * (1.0 - e) - EARTH_RADIUS_KM
    apogee_km = a * (1.0 + e) - EARTH_RADIUS_KM
    i_deg = math.degrees(el['i_rad'])
    
    # Dynamic Calculations
    speeds = [pt['speed_km_s'] for pt in pts]
    min_speed = min(speeds)
    max_speed = max(speeds)
    
    return {
        'name': el['name'],
        'norad_id': el['norad_id'],
        'period_h': period_h,
        'perigee_km': perigee_km,
        'apogee_km': apogee_km,
        'e': e,
        'i_deg': i_deg,
        'min_speed': min_speed,
        'max_speed': max_speed
    }

def summary_table(summaries_list):
    """
    Generates formatted lines of a diagnostic summary table.
    """
    headers = (f"{'Satellite Name':<18} | {'NORAD':<6} | "
               f"{'Period (h)':<10} | {'Perigee (km)':<12} | {'Apogee (km)':<11} | "
               f"{'e':<8} | {'i (deg)':<7} | {'Min V (km/s)':<12} | {'Max V (km/s)':<12}")
    separator = "-" * len(headers)
    lines = [headers, separator]
    
    for s in summaries_list:
        line = (f"{s['name'][:18]:<18} | "
                f"{s['norad_id']:<6} | "
                f"{s['period_h']:<10.2f} | "
                f"{s['perigee_km']:<12.1f} | "
                f"{s['apogee_km']:<11.1f} | "
                f"{s['e']:<8.6f} | "
                f"{s['i_deg']:<7.2f} | "
                f"{s['min_speed']:<12.3f} | "
                f"{s['max_speed']:<12.3f}")
        lines.append(line)
    return lines

# --- Process Summaries ---
summaries = [orbit_summary(el, pts) for el, pts in zip(elements, tracks)]

# --- Display Table ---
summary_lines = summary_table(summaries)
print("=== Stage 6: Satellite Orbit Summaries ===")
for line in summary_lines:
    print(line)

# --- Verification Assertion ---
for s in summaries:
    if s['norad_id'] == 59598:  # Galileo 29
        assert 14.0 <= s['period_h'] <= 14.2, f"Galileo 29 period of {s['period_h']:.2f} h fell outside expected [14.0, 14.2] range."
        print(f"\n[PASSED] Verified Galileo 29 orbital period: {s['period_h']:.2f} hours.")

# Stage 7: Visualizing Ground Tracks and Velocity Profiles

# Ensure preceding stages executed and populated tracks and elements
if 'tracks' not in globals() or 'elements' not in globals():
    raise NameError("Missing 'tracks' or 'elements' variables from preceding stages. Make sure Stages 3 and 5 ran successfully.")

def load_coastline(path):
    """
    Parses world_map.txt. Each line contains 'latitude longitude' (latitude first).
    Blank lines separate distinct coastline segments.
    """
    segments = []
    current_segment = []
    
    with open(path, 'r') as f:
        for line in f:
            line = line.strip()
            if not line:
                if current_segment:
                    segments.append(current_segment)
                    current_segment = []
            else:
                parts = line.split()
                if len(parts) >= 2:
                    lat = float(parts[0])
                    lon = float(parts[1])
                    current_segment.append((lon, lat)) # Save as (lon, lat) tuple
                    
    if current_segment:
        segments.append(current_segment)
        
    return segments

# Define color palette for consistent plotting (one color per satellite)
COLORS = ['tab:blue', 'tab:orange', 'tab:green', 'tab:red']

# --- Plot Figure 1: Ground Tracks over World Map ---
print("Generating Ground Tracks Plot...")
plt.figure(figsize=(14, 8))

# 1. Plot coastline segments
coastline_path = IN_DIR / 'world_map.txt'
if coastline_path.is_file():
    segments = load_coastline(coastline_path)
    for seg in segments:
        lons, lats = zip(*seg)
        plt.plot(lons, lats, color='gray', linewidth=0.8, alpha=0.7)
else:
    print("Warning: world_map.txt not found. Plotting without coastlines.")

# 2. Plot satellite ground tracks
for idx, track in enumerate(tracks):
    el = elements[idx]
    lons = [pt['lon_deg'] for pt in track]
    lats = [pt['lat_deg'] for pt in track]
    
    # Normalize longitudes to [-180, 180] to avoid lines jumping across boundaries
    norm_lons = [(lon + 180) % 360 - 180 for lon in lons]
    
    # Use scatter with small dots to avoid lines stretching across the plot boundary
    plt.scatter(norm_lons, lats, s=2, color=COLORS[idx % len(COLORS)], label=el['label'])

plt.title('Satellite Ground Tracks (24-Hour Simulation)')
plt.xlabel('Longitude (deg)')
plt.ylabel('Latitude (deg)')
plt.xlim(-180, 180)
plt.ylim(-90, 90)
plt.grid(True, linestyle='--', alpha=0.5)
plt.legend(loc='lower left', markerscale=6)
plt.tight_layout()

# Save ground tracks figure
ground_track_fig_path = OUT_DIR / 'ground_tracks.png'
plt.savefig(ground_track_fig_path, dpi=200)
plt.show()

# --- Plot Figure 2: Velocity Timeseries Stacked Subplots ---
print("\nGenerating Velocity Profiles...")
fig, axs = plt.subplots(len(elements), 1, figsize=(12, 3 * len(elements)), sharex=True)
if len(elements) == 1:
    axs = [axs]

for idx, track in enumerate(tracks):
    el = elements[idx]
    ax = axs[idx]
    
    times_plot = [pt['time'] for pt in track]
    speeds = [pt['speed_km_s'] for pt in track]
    
    ax.plot(times_plot, speeds, color=COLORS[idx % len(COLORS)], linewidth=2, label=el['name'])
    
    ax.set_ylabel('Speed (km/s)')
    ax.grid(True, linestyle='--', alpha=0.5)
    ax.ticklabel_format(axis='y', useOffset=False) # Suppress offset notation on y-axis
    ax.legend(loc='upper right')
    ax.set_title(f"Velocity Profile: {el['label']}", fontsize=10)

plt.xlabel('UTC Time')
plt.tight_layout()

# Save velocity timeseries figure
velocity_fig_path = OUT_DIR / 'velocity_timeseries.png'
plt.savefig(velocity_fig_path, dpi=200)
plt.show()