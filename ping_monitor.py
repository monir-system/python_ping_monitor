import threading
import subprocess
import platform
import time
from datetime import datetime
from flask import Flask, request, redirect, render_template_string

app = Flask(__name__)

status_dict = {}

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
        </div>
    {% endfor %}
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
        if new_host and new_host not in status_dict:
            status_dict[new_host] = "Checking..."
            threading.Thread(target=ping_host, args=(new_host,), daemon=True).start()
        return redirect("/")
    return render_template_string(TEMPLATE, statuses=status_dict, time=datetime.now().strftime("%Y-%m-%d %H:%M:%S"))

if __name__ == "__main__":
    app.run(debug=True)
    try:
        output = subprocess.run(["ping", param, "1", host], stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
        status = "Online ✅" if "TTL=" in output.stdout or "ttl=" in output.stdout or "bytes from" in output.stdout else "Offline ❌"
    except Exception as e:
        status = f"Error: {e}"

    log_entry = f"{datetime.now()} - {host}: {status}"
    print(log_entry)

    with open(log_file, "a", encoding="utf-8") as file:
        file.write(log_entry + "\n")

    if "Offline" in status or "Error" in status or "Online" in status:  # log all types for email alert
        log_entries.append(log_entry)


# Get user input
user_input = input("Enter IP addresses or domain names (separated by commas): ")
hosts = [host.strip() for host in user_input.split(",")]

# Log file setup
log_file = "ping_results.log"
log_entries = []

# Ping each host and collect results
for host in hosts:
    ping_host(host, log_file, log_entries)

# Send email if any host is offline
send_email(log_entries)

print(f"\nResults saved to {log_file}")

