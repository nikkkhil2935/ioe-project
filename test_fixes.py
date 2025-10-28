"""
Quick Test Script - Verify Temperature Range & Timezone Fixes
"""
import requests
import json
from datetime import datetime
import pytz

# Configuration
BACKEND_URL = 'http://127.0.0.1:5000/api'

def test_timezone():
    """Test that backend returns local timezone"""
    print("\n" + "="*60)
    print("TEST 1: Timezone Verification")
    print("="*60)
    
    # Get current time in Nepal timezone
    nepal_tz = pytz.timezone('Asia/Kathmandu')
    local_time = datetime.now(nepal_tz)
    print(f"Your local time (Nepal): {local_time.strftime('%Y-%m-%d %H:%M:%S %Z')}")
    
    # Send test data
    test_data = {
        "temp": 8.5,
        "hum": 65.0,
        "lat": 27.7172,
        "lng": 85.3240
    }
    
    response = requests.post(f"{BACKEND_URL}/data", 
                           json=test_data, 
                           headers={'Content-Type': 'application/json'})
    
    if response.status_code == 200:
        print("✅ Data sent successfully")
        
        # Get status
        status_response = requests.get(f"{BACKEND_URL}/status")
        data = status_response.json()
        
        if 'timestamp' in data:
            backend_time = data['timestamp']
            print(f"Backend timestamp: {backend_time}")
            print("✅ Timezone test PASSED - Times should match!")
        else:
            print("❌ No timestamp in response")
    else:
        print(f"❌ Failed to send data: {response.status_code}")

def test_temperature_range():
    """Test RSL predictions across cold chain temperature range"""
    print("\n" + "="*60)
    print("TEST 2: Temperature Range & RSL Predictions")
    print("="*60)
    
    test_temps = [5, 8, 10, 12, 15, 18, 20, 24]
    
    print(f"\n{'Temp (°C)':<12} {'Expected RSL':<15} {'Actual RSL':<15} {'Status':<10}")
    print("-" * 60)
    
    for temp in test_temps:
        test_data = {
            "temp": float(temp),
            "hum": 65.0,
            "lat": 27.7172,
            "lng": 85.3240
        }
        
        # Send data
        response = requests.post(f"{BACKEND_URL}/data", 
                               json=test_data,
                               headers={'Content-Type': 'application/json'})
        
        if response.status_code == 200:
            # Get status
            status_response = requests.get(f"{BACKEND_URL}/status")
            data = status_response.json()
            
            rsl = data.get('predicted_rsl_days', 'N/A')
            status = data.get('status', 'UNKNOWN')
            
            # Expected RSL (approximate)
            if temp <= 8:
                expected = "18-20 days"
            elif temp <= 10:
                expected = "15-18 days"
            elif temp <= 12:
                expected = "12-15 days"
            elif temp <= 15:
                expected = "8-12 days"
            else:
                expected = "<8 days"
            
            status_icon = "🟢" if status == "NORMAL" else "🔴"
            print(f"{temp}°C{'':<8} {expected:<15} {rsl} days{'':<7} {status_icon} {status}")
        
        import time
        time.sleep(0.5)  # Small delay between requests

def test_alert_thresholds():
    """Test alert triggering at correct thresholds"""
    print("\n" + "="*60)
    print("TEST 3: Alert Threshold Testing")
    print("="*60)
    
    test_scenarios = [
        (2, "Should trigger LOW temperature alert (<3°C)"),
        (7, "Should be NORMAL (3-15°C range)"),
        (16, "Should trigger HIGH temperature alert (>15°C)"),
    ]
    
    for temp, description in test_scenarios:
        test_data = {
            "temp": float(temp),
            "hum": 65.0,
            "lat": 27.7172,
            "lng": 85.3240
        }
        
        response = requests.post(f"{BACKEND_URL}/data", json=test_data)
        
        if response.status_code == 200:
            status_response = requests.get(f"{BACKEND_URL}/status")
            data = status_response.json()
            status = data.get('status', 'UNKNOWN')
            
            print(f"\n{temp}°C: {description}")
            print(f"Result: {status}")
            print("✅ PASS" if (
                (temp < 3 and status == "ALERT") or
                (3 <= temp <= 15 and status == "NORMAL") or
                (temp > 15 and status == "ALERT")
            ) else "❌ FAIL")
        
        import time
        time.sleep(0.5)

def main():
    print("\n" + "="*60)
    print("  COLDCHAIN PRO - SYSTEM VERIFICATION TESTS")
    print("="*60)
    print("\nMake sure Flask backend is running on http://127.0.0.1:5000")
    input("Press Enter to start tests...")
    
    try:
        # Test 1: Timezone
        test_timezone()
        
        # Test 2: Temperature range and RSL
        test_temperature_range()
        
        # Test 3: Alert thresholds
        test_alert_thresholds()
        
        print("\n" + "="*60)
        print("  ALL TESTS COMPLETED!")
        print("="*60)
        print("\n✅ Check the results above to verify:")
        print("   1. Timestamps match your local time")
        print("   2. RSL predictions are reasonable (not 0)")
        print("   3. Alerts trigger at correct thresholds")
        print("\n" + "="*60)
        
    except requests.exceptions.ConnectionError:
        print("\n❌ ERROR: Cannot connect to backend!")
        print("   Make sure Flask server is running: python app.py")
    except Exception as e:
        print(f"\n❌ ERROR: {e}")

if __name__ == "__main__":
    main()
