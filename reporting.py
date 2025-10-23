# reporting.py
import requests
import traceback
import os
import json
from typing import Optional

# --- Configuration ---
# NEW: This URL is now SAFE to be public. It doesn't reveal the secret.
# Replace this with the public URL Vercel gave you.
REPORTING_PROXY_URL = 'https://woonnet-error-proxy.vercel.app/api' # <-- IMPORTANT: CHANGE THIS
APP_VERSION = "3.4-secure" # Let's version the app

def send_discord_report(exception: Exception, context: str, log_file_path: Optional[str] = None):
    """
    Sends a detailed, formatted error report to Discord via a secure proxy.
    """
    if not REPORTING_PROXY_URL or "woonnet-error-proxy" in REPORTING_PROXY_URL:
        print("WARNING: Reporting proxy URL is not configured in reporting.py. Cannot send error report.")
        return

    tb_str = "".join(traceback.format_exception(type(exception), exception, exception.__traceback__))

    # Create the embed structure. The proxy will forward this to Discord.
    embed = {
        "title": f"🔴 WoonnetBot Critical Error (v{APP_VERSION})",
        "description": f"An unhandled exception occurred **{context}**.",
        "color": 15158332,  # Red color
        "fields": [
            {"name": "Error Type", "value": f"`{type(exception).__name__}`", "inline": True},
            {"name": "Error Message", "value": f"`{str(exception)}`", "inline": True},
            {"name": "Traceback", "value": f"```python\n{tb_str[-950:]}\n```"}
        ]
    }

    # The final payload that will be sent to our proxy.
    # Note: We can't send files through this simple proxy, so we send the log content instead.
    payload_to_proxy = {
        "embeds": [embed]
    }

    if log_file_path and os.path.exists(log_file_path):
        try:
            with open(log_file_path, 'r', encoding='utf-8', errors='ignore') as f:
                log_content = f.read()
            # Add the log content as another embed field.
            payload_to_proxy['embeds'][0]['fields'].append({
                "name": "Log File Tail (Last 1000 chars)",
                "value": f"```\n{log_content[-1000:]}\n```",
                "inline": False
            })
        except Exception as e:
            payload_to_proxy['embeds'][0]['fields'].append({
                "name": "Log File Error",
                "value": f"Could not read log file: {e}",
                "inline": False
            })

    try:
        # Send the report as JSON to our secure Vercel proxy.
        response = requests.post(
            REPORTING_PROXY_URL,
            json=payload_to_proxy,
            headers={'Content-Type': 'application/json'},
            timeout=15
        )
        response.raise_for_status()
        print("Successfully sent error report via secure proxy.")
    except Exception as e:
        print(f"FATAL: Could not send error report to proxy. {e}")