import requests
import time
import random
import json

# --- Configuration ---
# !!! IMPORTANT: Choose your backend URL
# For local testing (recommended for development):
BACKEND_DATA_URL = 'http://127.0.0.1:5000/api/data'
# For Render deployment, use: 'https://my-coldchain-backend.onrender.com/api/data'
SEND_INTERVAL_SECONDS = 3 # Send data every 3 seconds for testing
# --- ---

# --- Simulation Parameters ---
# Cold chain optimal range: 5-15°C (realistic for vaccines/pharmaceuticals)
current_temp = 8.0 # Starting temp (optimal cold chain temperature)
current_lat = 27.7172 # Kathmandu coordinates
current_lng = 85.3240
# --- ---

print(f"Starting automated data sender.")
print(f"Sending data to: {BACKEND_DATA_URL}")
print(f"Interval: {SEND_INTERVAL_SECONDS} seconds")
print("Press CTRL+C to stop.")

while True:
    try:
        # Simulate small changes (±0.5°C typical variation)
        current_temp += random.uniform(-0.5, 0.5)
        
        # Simulate occasional temperature excursion (10% chance)
        if random.random() < 0.1:
             # Cold chain breach: temperature goes up
             temp_jump = random.uniform(2, 5)
             current_temp += temp_jump
             print(f"*** ⚠️ Temperature excursion: +{temp_jump:.1f}°C ***")
        
        # Simulate recovery (5% chance to drop back down)
        if current_temp > 12.0 and random.random() < 0.05:
             temp_drop = random.uniform(2, 4)
             current_temp -= temp_drop
             print(f"*** ✅ Temperature recovering: -{temp_drop:.1f}°C ***")

        # Keep values within cold chain realistic bounds (5-15°C)
        # Normal operation: 5-10°C, Alert zone: 10-15°C, Critical: >15°C
        current_temp = max(5.0, min(18.0, current_temp))
        
        # Humidity: typical cold chain range 50-85%
        current_hum = random.uniform(50.0, 85.0)
        
        # GPS: slight movement simulation
        current_lat += random.uniform(-0.001, 0.001)
        current_lng += random.uniform(-0.001, 0.001)

        # Create the data payload (JSON)
        payload = {
            "temp": round(current_temp, 1),
            "hum": round(current_hum, 1),
            "lat": round(current_lat, 4),
            "lng": round(current_lng, 4)
        }

        # Send the POST request
        headers = {'Content-Type': 'application/json'}
        response = requests.post(BACKEND_DATA_URL, headers=headers, data=json.dumps(payload), timeout=10) # Added timeout

        # Check response
        if response.status_code == 200:
            print(f"Sent: {payload} -> Response: OK")
        else:
            print(f"Sent: {payload} -> Error: {response.status_code}, {response.text}")

    except requests.exceptions.RequestException as e:
        print(f"Error sending data: {e}")
    except KeyboardInterrupt:
        print("\nStopping data sender.")
        break
    except Exception as e:
         print(f"An unexpected error occurred: {e}")


    # Wait for the next interval
    time.sleep(SEND_INTERVAL_SECONDS)