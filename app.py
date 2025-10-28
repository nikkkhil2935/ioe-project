# ==============================================================================
# app.py - Enhanced Flask Backend for Intelligent Cold Chain Monitor
# ==============================================================================
# --- Imports ---
from flask import Flask, request, jsonify
from flask_cors import CORS
import joblib
import pandas as pd
import numpy as np
import os
import traceback
from datetime import datetime
import pytz  # For timezone handling

# --- Configuration Constants ---
PRODUCT_OPTIMAL_TEMP = 8.0  # Optimal cold chain temperature (8°C)
PRODUCT_Q10 = 2.0
SENSOR_INTERVAL_HOURS = 1 # **Important: Assumed interval for calculations**
CRITICAL_TEMP = 12.0  # Anything above 12°C is critical for cold chain
ALERT_TEMP_HIGH = 15.0  # High temperature alert (was 25°C)
ALERT_TEMP_LOW = 3.0  # Low temperature alert (was 15°C, now for freezing risk)
WINDOW_SIZE_HOURS = 6
HISTORY_MAX_LEN = 200 # ** Increased history size for demo **
TIMEZONE = 'Asia/Kathmandu'  # Nepal timezone (UTC+5:45)
# --- ---

# --- Load Model ---
script_dir = os.path.dirname(os.path.abspath(__file__))
model_filename = 'rsl_predictor_model.joblib'
model_path = os.path.join(script_dir, model_filename)
model = None
try: # Simplified load
    if os.path.exists(model_path): model = joblib.load(model_path); print("✅ ML Model loaded.")
    else: print(f"⚠️ Error: Model file not found: {model_path}")
except Exception as e: print(f"❌ Error loading model: {e}"); traceback.print_exc()
# --- ---

app = Flask(__name__)
CORS(app)

# --- In-Memory Storage ---
latest_data = { "status": "UNKNOWN" } # Will be populated fully on first data receipt
# Store more history for charts/KPIs
history = [] # Stores {'timestamp': str, 'hours': float, 'temperature': float, 'humidity': float, 'rsl': float or None}
alert_log = [] # Stores {'start_time': str, 'end_time': str or None, 'type': str, 'peak_value': float}
current_alert_info = None # Tracks the currently active alert
# --- ---

# === API Endpoints ===

@app.route('/api/data', methods=['POST'])
def receive_data():
    """Receives data, updates history, predicts, calculates KPIs, logs alerts."""
    global latest_data, history, model, alert_log, current_alert_info
    try:
        # 1. --- Get and Validate Input Data ---
        data = request.get_json()
        if not data: return jsonify({"error": "Invalid JSON"}), 400
        temp = data.get('temp')
        hum = data.get('hum')
        lat = data.get('lat', latest_data.get('lat'))
        lng = data.get('lng', latest_data.get('lng'))
        # Get current time in local timezone
        local_tz = pytz.timezone(TIMEZONE)
        timestamp_iso = datetime.now(local_tz).isoformat() # Record arrival time in local timezone

        if temp is None or not isinstance(temp, (int, float)): return jsonify({"error": "Invalid 'temp'"}), 400
        if hum is None or not isinstance(hum, (int, float)): return jsonify({"error": "Invalid 'hum'"}), 400
        temp_py, hum_py = float(temp), float(hum)
        lat_py = float(lat) if lat is not None else None
        lng_py = float(lng) if lng is not None else None

        # 2. --- Update History ---
        current_hours = len(history) * SENSOR_INTERVAL_HOURS
        # RSL will be added after prediction
        current_reading = {'timestamp': timestamp_iso, 'hours': current_hours, 'temperature': temp_py, 'humidity': hum_py, 'rsl': None}
        history.append(current_reading)
        if len(history) > HISTORY_MAX_LEN: history.pop(0)

        # 3. --- Predict RSL (if possible) ---
        predicted_rsl_py = None
        hist_df = pd.DataFrame(history) # Create DataFrame *after* appending new reading
        
        # Calculate RSL based on Q10 degradation model for cold chain (5-15°C range)
        if not hist_df.empty:
            try:
                # Use Q10 degradation model: For every 10°C above optimal, shelf life halves
                temp_diff = temp_py - PRODUCT_OPTIMAL_TEMP
                degradation_factor = PRODUCT_Q10 ** (temp_diff / 10.0)
                
                # Base shelf life at optimal temperature
                base_shelf_life = 20.0  # days
                
                # Calculate remaining shelf life
                predicted_rsl_py = base_shelf_life / degradation_factor
                
                # Adjust based on time already spent at various temperatures
                avg_temp = float(hist_df['temperature'].mean())
                avg_temp_diff = avg_temp - PRODUCT_OPTIMAL_TEMP
                avg_degradation = PRODUCT_Q10 ** (avg_temp_diff / 10.0)
                time_elapsed_days = current_hours / 24.0
                shelf_life_consumed = time_elapsed_days * avg_degradation
                
                # Final RSL = base - consumed
                predicted_rsl_py = max(0.1, base_shelf_life - shelf_life_consumed)
                
                # Clamp to reasonable range (0.1 to 30 days)
                predicted_rsl_py = float(max(0.1, min(30.0, predicted_rsl_py)))
                
                # Update RSL in the *last* history entry
                history[-1]['rsl'] = round(predicted_rsl_py, 2)
                
            except Exception as pred_e: 
                print(f"❌ Prediction Error: {pred_e}")
                traceback.print_exc()
                # Fallback to model prediction if Q10 fails
                if model is not None:
                    try:
                        current_features = {
                            'temperature': temp_py, 'humidity': hum_py,
                            'avg_temp_last_6h': float(hist_df['temperature'].rolling(WINDOW_SIZE_HOURS, min_periods=1).mean().iloc[-1]),
                            'max_temp_last_6h': float(hist_df['temperature'].rolling(WINDOW_SIZE_HOURS, min_periods=1).max().iloc[-1]),
                            'min_temp_last_6h': float(hist_df['temperature'].rolling(WINDOW_SIZE_HOURS, min_periods=1).min().iloc[-1]),
                            'time_above_critical': float((hist_df['temperature'] > CRITICAL_TEMP).sum() * SENSOR_INTERVAL_HOURS),
                            'journey_time_hours': float(current_hours)
                        }
                        feature_order = ['temperature', 'humidity', 'avg_temp_last_6h', 'max_temp_last_6h',
                                         'min_temp_last_6h', 'time_above_critical', 'journey_time_hours']
                        feature_values = pd.DataFrame([current_features], columns=feature_order)
                        predicted_rsl_np = model.predict(feature_values)[0]
                        predicted_rsl_py = float(max(0.1, predicted_rsl_np))
                        history[-1]['rsl'] = round(predicted_rsl_py, 2)
                    except Exception as model_e:
                        print(f"❌ Model Prediction also failed: {model_e}")
                        predicted_rsl_py = 15.0  # Safe fallback

        # 4. --- Determine Status & Log Alerts ---
        current_status = "NORMAL"
        alert_type = None
        if temp_py > ALERT_TEMP_HIGH:
            current_status = "ALERT"
            alert_type = "High Temperature"
        elif temp_py < ALERT_TEMP_LOW:
            current_status = "ALERT"
            alert_type = "Low Temperature"

        # Update Alert Log
        if current_status == "ALERT":
            if current_alert_info is None: # New alert starts
                current_alert_info = {'start_time': timestamp_iso, 'end_time': None, 'type': alert_type, 'peak_value': temp_py}
                alert_log.append(current_alert_info)
            else: # Alert continues
                # Update peak value if current temp is more extreme
                if (alert_type == "High Temperature" and temp_py > current_alert_info['peak_value']) or \
                   (alert_type == "Low Temperature" and temp_py < current_alert_info['peak_value']):
                    current_alert_info['peak_value'] = temp_py
                # If alert type changes mid-alert (e.g., high then low), end previous, start new
                if current_alert_info['type'] != alert_type:
                     current_alert_info['end_time'] = timestamp_iso # End previous
                     current_alert_info = {'start_time': timestamp_iso, 'end_time': None, 'type': alert_type, 'peak_value': temp_py}
                     alert_log.append(current_alert_info)

        elif current_status == "NORMAL" and current_alert_info is not None: # Alert ends
            current_alert_info['end_time'] = timestamp_iso
            current_alert_info = None # Reset current alert tracking

        # Keep alert log size manageable (optional)
        # MAX_ALERTS = 50
        # if len(alert_log) > MAX_ALERTS: alert_log = alert_log[-MAX_ALERTS:]


        # 5. --- Calculate KPIs ---
        kpis = {
            "avg_temp": None, "min_temp": None, "max_temp": None,
            "time_in_range_hrs": 0.0, "time_out_range_hrs": 0.0,
            "journey_time_hours": float(current_hours),
            "time_above_critical": float((hist_df['temperature'] > CRITICAL_TEMP).sum() * SENSOR_INTERVAL_HOURS) # Recalculate based on full history
        }
        if not hist_df.empty:
            kpis["avg_temp"] = round(float(hist_df['temperature'].mean()), 1)
            kpis["min_temp"] = round(float(hist_df['temperature'].min()), 1)
            kpis["max_temp"] = round(float(hist_df['temperature'].max()), 1)
            # Updated range for cold chain: 3°C to 15°C is acceptable
            in_range_mask = (hist_df['temperature'] >= ALERT_TEMP_LOW) & (hist_df['temperature'] <= ALERT_TEMP_HIGH)
            kpis["time_in_range_hrs"] = round(float(in_range_mask.sum() * SENSOR_INTERVAL_HOURS), 1)
            kpis["time_out_range_hrs"] = round(float((~in_range_mask).sum() * SENSOR_INTERVAL_HOURS), 1)


        # 6. --- Update latest_data Store ---
        latest_data = {
            "timestamp": timestamp_iso,
            "temperature": temp_py,
            "humidity": hum_py,
            "lat": lat_py,
            "lng": lng_py,
            "predicted_rsl_days": round(predicted_rsl_py, 2) if predicted_rsl_py is not None else None,
            "status": current_status,
            **kpis # Merge KPIs into the latest data
        }

        print(f"✅ Data Processed: T={temp_py:.1f}, RSL={latest_data['predicted_rsl_days']}, Status={latest_data['status']}, KPIs: MaxT={kpis['max_temp']}, TimeOut={kpis['time_out_range_hrs']}h")
        return jsonify({"message": "Data received successfully"}), 200

    except Exception as e:
        print(f"❌ FATAL error in /api/data: {e}")
        traceback.print_exc()
        latest_data["status"] = "ERROR" # Set status to error
        return jsonify({"error": f"Internal server error: {str(e)}"}), 500

# --- Endpoint for Frontend to get the latest status and KPIs ---
@app.route('/api/status', methods=['GET'])
def get_status():
    """Returns the most recent data snapshot including KPIs."""
    global latest_data
    return jsonify(latest_data)

# --- Endpoint for Frontend to get historical data ---
@app.route('/api/history', methods=['GET'])
def get_history():
    """Returns the stored historical sensor readings."""
    global history
    # Return last N points, or filter by time if implemented
    return jsonify(history) # Returns the entire list for now

# --- Endpoint for Frontend to get alert log ---
@app.route('/api/alerts', methods=['GET'])
def get_alerts():
    """Returns the log of alert events."""
    global alert_log
    # Return alerts, maybe most recent first
    return jsonify(sorted(alert_log, key=lambda x: x['start_time'], reverse=True))

# === Main Execution Block ===
if __name__ == '__main__':
    print("\n-----------------------------------------")
    print(" Starting Intelligent Cold Chain Monitor ")
    print("-----------------------------------------")
    if model is None: print("🚨 WARNING: ML Model failed to load. RSL Predictions unavailable.")
    else: print("👍 ML Model loaded.")
    print("\n🚀 Flask server starting...")
    print(f"   Local: http://127.0.0.1:5000")
    print(f"   Network: http://<Your-IP-Address>:5000")
    print("-----------------------------------------")
    app.run(debug=True, host='0.0.0.0', port=5000, use_reloader=True)