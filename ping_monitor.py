import os
import subprocess
import platform
from datetime import datetime
import smtplib
from email.message import EmailMessage

# Email Configuration (Update These)
SMTP_SERVER = "smtp.gmail.com"  # Use "smtp.gmail.com" for Gmail, "smtp.office365.com" for Outlook
SMTP_PORT = 587
EMAIL_SENDER = os.getenv("EMAIL_USER")  # Replace with your email
EMAIL_PASSWORD = os.getenv("EMAIL_PASSWORD")  # Use an App Password for security
EMAIL_RECEIVER = os.getenv("EMAIL_USER")  # Replace with recipient's email


def send_email(log_entries):
    """Sends an email with the ping results."""
    if not log_entries:
        return  # No failures, no need to send an email

    email_subject = "Ping Monitor Alert 🚨"
    email_body = "\n".join(log_entries)

    msg = EmailMessage()
    msg.set_content(email_body)
    msg["Subject"] = email_subject
    msg["From"] = EMAIL_SENDER
    msg["To"] = EMAIL_RECEIVER

    try:
        with smtplib.SMTP(SMTP_SERVER, SMTP_PORT) as server:
            server.starttls()  # Secure connection
            server.login(EMAIL_SENDER, EMAIL_PASSWORD)
            server.send_message(msg)
        print("\n📧 Email sent successfully!")
    except Exception as e:
        print(f"\n⚠️ Failed to send email: {e}")


def ping_host(host, log_file, log_entries):
    """Pings a host and logs the result."""
    param = "-n" if platform.system().lower() == "windows" else "-c"

    try:
        output = subprocess.run(["ping", param, "1", host], stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
        status = "Online ✅" if output.returncode == 0 else "Offline ❌"
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
