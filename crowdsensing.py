#!/usr/bin/env python3
"""
Simplified Occupancy Monitor - WiFi & Bluetooth Device Detection
Removes Django dependencies and uses direct SQLite storage
"""

import os
import sys
import time
import argparse
import threading
import traceback
import pyshark
import sqlite3
from datetime import datetime
from random import randint

# Configuration
BIN_SIZE = 300  # 5 minutes in seconds
RSSI_THRESHOLD = -70  # Signal strength threshold
DEBUG_MODE = False

# Global variables
last_bin = int(time.time())
mac_set = set()
mac_signal_dict = dict()
channel = 1
already_stopping = False
monitor_iface = None
sensor_id = None


def setup_database():
    """Create SQLite database and tables"""
    conn = sqlite3.connect('occupancy_data.db')
    cursor = conn.cursor()
    
    # Create occupancy table
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS occupancy (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            sensor_id INTEGER,
            timestamp TEXT,
            occupancy INTEGER
        )
    ''')
    
    # Create device table
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS devices (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            sensor_id INTEGER,
            timestamp TEXT,
            mac TEXT,
            rssi REAL,
            channel INTEGER
        )
    ''')
    
    conn.commit()
    conn.close()
    print("[I] Database initialized: occupancy_data.db")


def get_sensor_id():
    """Get or create unique sensor ID"""
    try:
        with open('sensor_id.txt', 'r') as f:
            sensor_id = int(f.read())
            print(f"[I] Loaded sensor ID: {sensor_id}")
    except FileNotFoundError:
        sensor_id = randint(0, 2147483647)
        with open('sensor_id.txt', 'w') as f:
            f.write(str(sensor_id))
        print(f"[I] Generated new sensor ID: {sensor_id}")
    
    return sensor_id


def debug(msg):
    """Print debug messages if enabled"""
    if DEBUG_MODE:
        print(f"[DEBUG] {msg}")


def save_occupancy_data(sensor_id, occupancy_count, devices_data):
    """Save occupancy and device data to database"""
    conn = sqlite3.connect('occupancy_data.db')
    cursor = conn.cursor()
    
    timestamp = datetime.utcnow().isoformat()
    
    # Save occupancy count
    cursor.execute(
        'INSERT INTO occupancy (sensor_id, timestamp, occupancy) VALUES (?, ?, ?)',
        (sensor_id, timestamp, occupancy_count)
    )
    
    # Save individual device data
    for mac, (rssi, channel) in devices_data.items():
        if mac is None:
            continue
        cursor.execute(
            'INSERT INTO devices (sensor_id, timestamp, mac, rssi, channel) VALUES (?, ?, ?, ?, ?)',
            (sensor_id, timestamp, mac, rssi, channel)
        )
    
    conn.commit()
    conn.close()
    
    print(f"[I] Saved data: {occupancy_count} devices detected")


def channel_hopper():
    """
    Continuously cycle through WiFi channels
    Helps capture devices on different channels
    """
    global channel, already_stopping, monitor_iface
    
    # 2.4 GHz channels
    channels = [1, 2, 3, 4, 5, 6, 7, 8, 9, 10, 11, 12, 13]
    
    # If you have 5GHz support, uncomment below:
    # channels = [1, 2, 3, 4, 5, 6, 7, 8, 9, 10, 11, 12, 13, 
    #            36, 40, 44, 48, 52, 56, 60, 64, 
    #            100, 104, 108, 112, 116, 120, 124, 128, 132, 136, 140, 
    #            149, 153, 157, 161, 165]
    
    while not already_stopping:
        for channel in channels:
            if already_stopping:
                break
            
            os.system(f"iwconfig {monitor_iface} channel {channel} > /dev/null 2>&1")
            debug(f"[CHOPPER] Channel changed to: {channel}")
            time.sleep(BIN_SIZE / len(channels))
    
    debug("[CHOPPER] Stopping")


def packet_handler(pkt):
    """
    Process each captured WiFi packet
    Extract MAC addresses and signal strength
    """
    global mac_signal_dict, sensor_id, last_bin, mac_set, channel
    
    try:
        # Get RSSI (signal strength)
        rssi_val = float(pkt.radiotap.dbm_antsignal)
        
        # Extract MAC addresses from different packet fields
        to_address = None
        rcv_address = None
        dst_address = None
        src_address = None
        
        try:
            to_address = pkt.wlan.ta
        except AttributeError:
            pass
        
        try:
            rcv_address = pkt.wlan.ra
        except AttributeError:
            pass
        
        try:
            dst_address = pkt.wlan.dst
        except AttributeError:
            pass
        
        try:
            src_address = pkt.wlan.src
        except AttributeError:
            pass
        
        current_time = time.time()
        
        # Check if it's time to save data (every BIN_SIZE seconds)
        if last_bin + BIN_SIZE < current_time:
            last_bin = last_bin + BIN_SIZE
            
            # Save to database
            save_occupancy_data(sensor_id, len(mac_set), mac_signal_dict)
            
            # Reset for next time bin
            mac_set = set()
            mac_signal_dict = dict()
        
        # Only count devices with strong enough signal
        if rssi_val > RSSI_THRESHOLD:
            # Add all detected MAC addresses
            for addr in [to_address, rcv_address, dst_address, src_address]:
                if addr:
                    mac_set.add(addr)
                    mac_signal_dict[addr] = [rssi_val, channel]
    
    except Exception as e:
        debug(f"Error processing packet: {e}")


def stop():
    """Stop the monitoring gracefully"""
    global already_stopping
    
    if not already_stopping:
        already_stopping = True
        print("\n[I] Stopping...")
        print("[I] Monitor stopped.")
        sys.exit(0)


def main():
    global monitor_iface, sensor_id, DEBUG_MODE
    
    # Parse command line arguments
    parser = argparse.ArgumentParser(
        description="WiFi Occupancy Monitor - Detect devices via WiFi signals"
    )
    parser.add_argument(
        "interface",
        help="Monitor mode interface (e.g., wlan0mon)"
    )
    parser.add_argument(
        "--debug",
        action="store_true",
        help="Enable debug output"
    )
    parser.add_argument(
        "--bin-size",
        type=int,
        default=300,
        help="Time bin size in seconds (default: 300)"
    )
    parser.add_argument(
        "--rssi-threshold",
        type=int,
        default=-70,
        help="RSSI threshold for device detection (default: -70)"
    )
    
    if len(sys.argv) == 1:
        parser.print_help()
        sys.exit(1)
    
    args = parser.parse_args()
    
    monitor_iface = args.interface
    DEBUG_MODE = args.debug
    
    global BIN_SIZE, RSSI_THRESHOLD
    BIN_SIZE = args.bin_size
    RSSI_THRESHOLD = args.rssi_threshold
    
    print("\n" + "="*60)
    print("WiFi Occupancy Monitor")
    print("="*60)
    print(f"Interface: {monitor_iface}")
    print(f"Bin Size: {BIN_SIZE} seconds")
    print(f"RSSI Threshold: {RSSI_THRESHOLD} dBm")
    print(f"Debug Mode: {DEBUG_MODE}")
    print("="*60 + "\n")
    
    # Initialize
    sensor_id = get_sensor_id()
    setup_database()
    
    # Start channel hopping in background thread
    print("[I] Starting channel hopper...")
    chopper = threading.Thread(target=channel_hopper, daemon=True)
    chopper.start()
    
    # Main capture loop
    print("[I] Starting packet capture...")
    print("[I] Press CTRL+C to stop\n")
    
    while True:
        try:
            capture = pyshark.LiveCapture(interface=monitor_iface)
            capture.apply_on_packets(packet_handler)
        
        except KeyboardInterrupt:
            stop()
        
        except Exception as e:
            print(f"[!] An error occurred: {e}")
            print(traceback.format_exc())
            print("[!] Restarting in 5 sec... Press CTRL+C to stop.")
            try:
                time.sleep(5)
            except KeyboardInterrupt:
                stop()


if __name__ == "__main__":
    main()