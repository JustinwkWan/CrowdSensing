# CrowdSensing

A WiFi-based occupancy detection system that estimates crowd presence by capturing packets in monitor mode and analyzing MAC addresses and signal strength.

## What It Does

CrowdSensing passively monitors WiFi traffic to count nearby devices, giving a real-time estimate of how many people are in an area. It captures packets using a monitor-mode network interface, filters by signal strength (RSSI), and stores occupancy data in a local SQLite database.

- Extracts MAC addresses from WiFi packets
- Filters weak signals below a configurable RSSI threshold
- Hops across WiFi channels (1-13) to maximize detection
- Groups device counts into configurable time bins
- Stores results in SQLite for later analysis

## Tech Stack

- **Language:** Python 3
- **Packet Capture:** pyshark
- **Database:** SQLite3
- **System Requirements:** Linux/macOS, monitor-mode capable WiFi adapter, root privileges

## Usage

```bash
# Basic usage
sudo python3 crowdsensing.py <interface>

# Example with a monitor-mode interface
sudo python3 crowdsensing.py wlan0mon

# With options
sudo python3 crowdsensing.py wlan0mon --debug --bin-size 600 --rssi-threshold -65
```

### Options

| Flag | Default | Description |
|------|---------|-------------|
| `interface` | (required) | Monitor-mode WiFi interface |
| `--debug` | off | Enable debug output |
| `--bin-size` | 300 | Time bin size in seconds |
| `--rssi-threshold` | -70 | Minimum signal strength (dBm) |

## Output

- `occupancy_data.db` — SQLite database with `occupancy` and `devices` tables
- `sensor_id.txt` — Unique identifier for this sensor instance

## Project Structure

```
CrowdSensing/
└── crowdsensing.py    # Main application (packet capture, channel hopping, DB storage)
```
