import re
import threading
import os
import re
import subprocess
import platform
import time
import sqlite3
import wmi
from datetime import datetime
from flask import Flask, request, redirect, render_template_string

DB_NAME = "hosts.db"
print("📁 Using database file at:", os.path.abspath(DB_NAME))

def init_db():
    with sqlite3.connect(DB_NAME) as conn:
        c = conn.cursor()
        c.execute("""
            CREATE TABLE IF NOT EXISTS hosts (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                hostname TEXT UNIQUE NOT NULL,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)
        conn.commit()

def get_connected_bluetooth_devices():
    try:
        c = wmi.WMI()
        bt_devices = []
        for device in c.Win32_PnPEntity():
            if device.PNPClass == "Bluetooth" and device.Status == "OK":
                name = device.Name
                mac = None
                if device.DeviceID:
                    print(f"Device Name: {name}, Device ID: {device.DeviceID}")  # Optional debug
                    mac_match = re.search(r'([0-9A-F]{12})', device.DeviceID, re.IGNORECASE)
                    if mac_match:
                        raw_mac = mac_match.group(1)
                        mac = ":".join(raw_mac[i:i+2] for i in range(0, 12, 2))
                bt_devices.append((name, mac or "Unknown MAC"))
        return bt_devices if bt_devices else [("None", "No devices connected")]
    except Exception as e:
        return [("Error", str(e))]


def add_host_to_db(hostname):
    with sqlite3.connect(DB_NAME) as conn:
        c = conn.cursor()
        try:
            c.execute("INSERT INTO hosts (hostname) VALUES (?)", (hostname,))
            conn.commit()
        except sqlite3.IntegrityError:
            pass  # Host already exists

def get_all_hosts():
    with sqlite3.connect(DB_NAME) as conn:
        c = conn.cursor()
        c.execute("SELECT hostname FROM hosts")
        return [row[0] for row in c.fetchall()]

app = Flask(__name__)

status_dict = {}

def start_monitoring_all_hosts():
    for host in get_all_hosts():
        start_monitoring_for_host(host)

def start_monitoring_for_host(host):
    if host not in status_dict:
        status_dict[host] = "Checking..."
        threading.Thread(target=ping_host, args=(host,), daemon=True).start()

TEMPLATE = """
<!DOCTYPE html>
<html>
<head>
    <title>Ping Monitor Dashboard</title>
    <meta http-equiv="refresh" content="30">
    <style>
        body { font-family: Arial, sans-serif; background-color: #111; color: #eee; text-align: center; padding: 2em; }
        .host { margin: 1em; padding: 1em; border-radius: 10px; display: inline-block; width: 200px; background-color: #222; }
        .online { color: #0f0; }
        .offline { color: #f33; }
        form { margin-bottom: 2em; }
        input[type=text] { padding: 0.5em; width: 300px; border-radius: 5px; border: none; }
        input[type=submit] { padding: 0.5em 1em; background-color: #444; color: #fff; border: none; border-radius: 5px; cursor: pointer; }
        input[type=submit]:hover { background-color: #666; }
    </style>
</head>
<body>
    <h1>🌐 Ping Monitor Dashboard</h1>
    <form method="POST">
        <input type="text" name="host" placeholder="Enter hostname or IP" required>
        <input type="submit" value="Add Host">
    </form>
    {% for host, status in statuses.items() %}
    <div class="host">
        <h2>{{ host }}</h2>
        <p class="{{ 'online' if status == 'Online ✅' else 'offline' }}">{{ status }}</p>
        <form method="POST" action="/delete/{{ host }}" onsubmit="return confirm('Are you sure you want to remove {{ host }}?');">
            <input type="submit" value="Remove 🗑️">
        </form>
    </div>
{% endfor %}

<h2>🔵 Connected Bluetooth Devices</h2>
<ul>
{% for name, mac in bt_devices %}
    <li>{{ name }} — <code>{{ mac }}</code></li>
{% else %}
    <li>No devices connected.</li>
{% endfor %}
</ul>

    <p>Last updated: {{ time }}</p>
</body>
</html>
"""

def ping_host(host):
    """Ping loop for a single host."""
    param = "-n" if platform.system().lower() == "windows" else "-c"
    while True:
        try:
            output = subprocess.run(["ping", param, "1", host], stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
            if "TTL=" in output.stdout or "ttl=" in output.stdout or "bytes from" in output.stdout:
                status_dict[host] = "Online ✅"
            else:
                status_dict[host] = "Offline ❌"
        except Exception:
            status_dict[host] = "Error ❌"
        time.sleep(5)

@app.route("/", methods=["GET", "POST"])
def dashboard():
    if request.method == "POST":
        new_host = request.form["host"].strip()
        if new_host:
            add_host_to_db(new_host)
            start_monitoring_for_host(new_host)
        return redirect("/")  # You need this to reload page after adding
    bt_devices = get_connected_bluetooth_devices()
    return render_template_string(TEMPLATE, statuses=status_dict, time=datetime.now().strftime("%Y-%m-%d %H:%M:%S"), bt_devices=bt_devices)

@app.route("/delete/<hostname>", methods=["POST"])
def delete_host(hostname):
    with sqlite3.connect(DB_NAME) as conn:
        c = conn.cursor()
        c.execute("DELETE FROM hosts WHERE hostname = ?", (hostname,))
        conn.commit()

    # Also remove it from the status dictionary so it disappears
    status_dict.pop(hostname, None)

    return redirect("/")

if __name__ == "__main__":
    init_db()
    print("Current hosts in DB:", get_all_hosts())
    start_monitoring_all_hosts()
    app.run(debug=True)
