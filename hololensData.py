import requests
import json
from datetime import datetime
from flask import Flask, Response
import urllib3

# Ignore warnings for self-signed certificates (if HTTPS used later)
urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

app = Flask(__name__)


# HOLOLENS WINDOWS DEVICE PORTAL CONFIG
HOLOLENS_IP = "192.168.137.1"      # Replace with your HoloLens IP
PORT = "50080"                    # Your WDP port
USERNAME = "herjing"        # Replace
PASSWORD = "12345678"        # Replace

WDP_URL = f"https://{HOLOLENS_IP}:{PORT}/api/power/battery"


# GET REAL BATTERY DATA FROM HOLOLENS
def get_hololens_battery():
    try:
        response = requests.get(
            WDP_URL,
            auth=(USERNAME, PASSWORD),
            timeout=5,
            verify=False
        )

        print("STATUS:", response.status_code)
        print("RAW RESPONSE:", response.text[:1000])

        if response.status_code != 200:
            return 0, 0, 0

        source = response.json()

        max_cap = source.get("MaximumCapacity", 1)
        remain_cap = source.get("RemainingCapacity", 0)

        soc = round((remain_cap / max_cap) * 100, 2)
        charging = source.get("Charging", 0)
        ac = source.get("AcOnline", 0)

        return soc, charging, ac

    except Exception as e:
        print("WDP ERROR:", e)
        return 0, 0, 0


# LOCAL JSON API FOR YOUR SYSTEM
@app.route('/dataHoloLens', methods=['GET'])
def data_hololens():

    soc, charging, ac = get_hololens_battery()

    payload = {
        "device_type": "hololens",
        "device_id": "HL2_01",
        "timestamp": datetime.utcnow().isoformat() + "Z",

        "data": {
            "StateOfCharge": soc,
            "Charging": charging,
            "AcOnline": ac
        }
    }

    return Response(
        json.dumps(payload, indent=4),
        mimetype='application/json'
    )


# RUN SERVER
if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5001, threaded=True)