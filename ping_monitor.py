import re
import threading
import os
import subprocess
import platform
import time
import sqlite3
import wmi
import psutil
import socket
from datetime import datetime
from flask import Flask, request, redirect, render_template_string

DB_NAME = "hosts.db"
print("📁 Using database file at:", os.path.abspath(DB_NAME))

def get_system_info():
    boot_time = datetime.fromtimestamp(psutil.boot_time())
    uptime = datetime.now() - boot_time
    return {
        "Hostname": socket.gethostname(),
        "OS": platform.platform(),
        "CPU Usage": f"{psutil.cpu_percent(interval=0.5)}%",
        "RAM Usage": f"{psutil.virtual_memory().percent}%",
        "Uptime": str(uptime).split('.')[0],  # strip microseconds
    }


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
   <!-- <meta http-equiv="refresh" content="30"> -->
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

<div style="position: absolute; top: 10px; right: 10px; background-color: #222; padding: 1em; border-radius: 10px; text-align: left;">
    <h3>🖥️ System Info</h3>
    <ul style="list-style: none; padding-left: 0;">
    {% for key, value in system_info.items() %}
        <li><strong>{{ key }}:</strong> {{ value }}</li>
    {% endfor %}
    </ul>
</div>
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

<!-- Add a button to manually refresh Bluetooth devices -->
<h2 style="text-align: left;">🔵 Connected Bluetooth Devices [WINDOWS ONLY]</h2>

<!-- Manual refresh button with timer placeholder -->
<button id="refreshBtBtn" onclick="refreshBtDevices()" style="padding: 0.5em; background-color: #444; color: #fff; border-radius: 5px; border: none; cursor: pointer;">
    Refresh Bluetooth Devices
</button>
<span id="bt-update-msg" style="margin-left: 1em; color: #4CAF50; display: none;">✅ Updated</span>
<span id="bt-timer" style="margin-left: 1em; color: #ccc;"></span>

<!-- Bluetooth devices dropdown -->
<select id="bt-select" onchange="showBtInfo()" style="padding: 0.5em; background-color: #222; color: #eee; border-radius: 5px; border: none;">
    <option value="">-- Select a device --</option>
    {% for name, mac in bt_devices %}
        <option value="{{ loop.index0 }}">{{ name }}</option>
    {% endfor %}
</select>

<!-- Bluetooth device info box -->
<div id="bt-info" style="margin-top: 1em; background-color: #222; padding: 1em; border-radius: 10px; min-width: 200px; display: none;"></div>

<div style="position: absolute; top: 10px; right: 10px; background-color: #222; padding: 1em; border-radius: 10px; text-align: left;">
    <h3>🖥️ System Info 
        <button onclick="refreshSystemInfo()" style="float: right; background: #444; color: #fff; border: none; padding: 0.3em 0.6em; border-radius: 5px; cursor: pointer;">⟳</button>
    </h3>
    <ul id="system-info-list" style="list-style: none; padding-left: 0;">
        {% for key, value in system_info.items() %}
            <li><strong>{{ key }}:</strong> {{ value }}</li>
        {% endfor %}
    </ul>
</div>

<script>
    let btData = [];  // Start with an empty array for Bluetooth devices
     let btCountdown;

    // Function to display Bluetooth device info when selected
    function showBtInfo() {
        const select = document.getElementById("bt-select");
        const infoBox = document.getElementById("bt-info");
        const index = select.value;

        if (index === "") {
            infoBox.style.display = "none";
            infoBox.innerHTML = "";
            return;
        }

        const [name, mac] = btData[index];
        infoBox.innerHTML = `<strong>${name}</strong><br><code>${mac}</code>`;
        infoBox.style.display = "block";
    }

    function refreshBtDevices() {
    // Start 23s countdown timer
    let remaining = 23;
    const timerEl = document.getElementById("bt-timer");
    timerEl.textContent = `⏳ ${remaining}s`;

    const countdown = setInterval(() => {
        remaining--;
        if (remaining > 0) {
            timerEl.textContent = `⏳ ${remaining}s`;
        } else {
            timerEl.textContent = "";
            clearInterval(countdown);
        }
    }, 1000);

    // Fetch Bluetooth devices
    fetch("/refresh_bt", { method: "POST" })
        .then(response => response.json())
        .then(data => {
            btData = data.bt_devices;
            const btSelect = document.getElementById("bt-select");
            btSelect.innerHTML = '<option value="">-- Select a device --</option>';
            btData.forEach((device, index) => {
                const option = document.createElement("option");
                option.value = index;
                option.textContent = device[0];
                btSelect.appendChild(option);
            });

            // Show "Updated" message
            const msgEl = document.getElementById("bt-update-msg");
            msgEl.style.display = "inline";
            setTimeout(() => {
                msgEl.style.display = "none";
            }, 3000); // hide after 3s
        })
        .catch(error => {
            console.error("Error refreshing Bluetooth devices:", error);
            timerEl.textContent = ""; // clear timer if fetch fails
            clearInterval(countdown);
        });
}
</script>
<script>
    function refreshSystemInfo() {
        fetch("/refresh_system_info", { method: "POST" })
            .then(res => res.json())
            .then(data => {
                const infoList = document.getElementById("system-info-list");
                infoList.innerHTML = "";  // Clear current list
                for (const [key, value] of Object.entries(data.system_info)) {
                    const li = document.createElement("li");
                    li.innerHTML = `<strong>${key}:</strong> ${value}`;
                    infoList.appendChild(li);
                }
            })
            .catch(err => console.error("Failed to refresh system info:", err));
    }
</script>
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
        return redirect("/")
    
    bt_devices = []
    system_info = get_system_info()
    
    return render_template_string(
        TEMPLATE,
        statuses=status_dict,
        time=datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        bt_devices=bt_devices,  # Empty list initially
        system_info=system_info
    )

@app.route("/delete/<hostname>", methods=["POST"])
def delete_host(hostname):
    with sqlite3.connect(DB_NAME) as conn:
        c = conn.cursor()
        c.execute("DELETE FROM hosts WHERE hostname = ?", (hostname,))
        conn.commit()

    # Also remove it from the status dictionary so it disappears
    status_dict.pop(hostname, None)

    return redirect("/")

@app.route("/refresh_bt", methods=["POST"])
def refresh_bt_devices():
    """Handle manual refresh of Bluetooth devices."""
    bt_devices = get_connected_bluetooth_devices()  # Get the updated list of Bluetooth devices
    return {"bt_devices": bt_devices}  # Send the list back as JSON

@app.route("/refresh_system_info", methods=["POST"])
def refresh_system_info():
    """Return updated system information as JSON."""
    info = get_system_info()
    return {"system_info": info}

if __name__ == "__main__":
    init_db()
    print("Current hosts in DB:", get_all_hosts())
    start_monitoring_all_hosts()
    app.run(debug=True)
