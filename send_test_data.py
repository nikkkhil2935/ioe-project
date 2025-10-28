import requests
import time
import random
import json

# --- Configuration ---
# !!! IMPORTANT: Choose your backend URL
# For Render deployment (recommended):
BACKEND_DATA_URL = 'https://my-coldchain-backend.onrender.com/api/data'
# For local testing, use: 'http://127.0.0.1:5000/api/data'
SEND_INTERVAL_SECONDS = 3 # Send data every 3 seconds for testing
# --- ---

# --- Simulation Parameters ---
current_temp = 5.0 # Starting temp (cold chain temperature)
current_lat = 27.7172 # Kathmandu coordinates
current_lng = 85.3240
# --- ---

print(f"Starting automated data sender.")
print(f"Sending data to: {BACKEND_DATA_URL}")
print(f"Interval: {SEND_INTERVAL_SECONDS} seconds")
print("Press CTRL+C to stop.")

while True:
    try:
        # Simulate small changes
        current_temp += random.uniform(-1.0, 1.0)
        # Simulate occasional bigger jump (e.g., alert condition)
        if random.random() < 0.1: # 10% chance
             temp_jump = random.uniform(5, 10) * random.choice([-1, 1])
             current_temp += temp_jump
             print(f"*** Simulating temperature jump: {temp_jump:.1f} ***")

        # Keep values within reasonable bounds
        current_temp = max(10.0, min(35.0, current_temp)) # Limit between 10C and 35C for testing
        current_hum = random.uniform(50.0, 85.0)
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