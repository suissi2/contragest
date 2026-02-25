import socket
try:
    import requests
except ImportError:
    requests = None
import platform

def get_pc_info():
    """Returns the computer name and local IP address."""
    try:
        hostname = socket.gethostname()
        # Note: gethostbyname can be slow on some network configs
        try:
            local_ip = socket.gethostbyname(hostname)
        except:
            local_ip = "127.0.0.1"
        return hostname, local_ip
    except Exception as e:
        print(f"Error getting PC info: {e}")
        return "Unknown", "127.0.0.1"

def get_location_and_weather():
    """
    Fetches location and weather data.
    Returns (city, country, temperature_c).
    """
    location = "Unknown City, Unknown Country"
    temp = "N/A"
    
    if not requests:
        return location, temp
    
    # 1. Get Location via IP
    # Using ip-api.com (free for non-commercial use, no key required for basic)
    try:
        loc_resp = requests.get("http://ip-api.com/json/", timeout=5)
        if loc_resp.status_code == 200:
            data = loc_resp.json()
            if data["status"] == "success":
                location = f"{data['city']}, {data['country']}"
        else:
            location = "Location Service Unavailable"
    except (requests.exceptions.Timeout, requests.exceptions.ConnectionError):
        print("DEBUG: Location service unreachable (timeout/connection)")
        location = "Location (Offline)"
    except Exception as e:
        print(f"DEBUG: Error getting location: {e}")

    # 2. Get Weather/Temperature
    # Using wttr.in (simple weather service)
    try:
        weather_resp = requests.get("https://wttr.in/?format=%t", timeout=5)
        if weather_resp.status_code == 200:
            temp = weather_resp.text.strip()
        else:
            temp = "N/A"
    except (requests.exceptions.Timeout, requests.exceptions.ConnectionError):
        print("DEBUG: Weather service unreachable (timeout/connection)")
        temp = "N/A (Offline)"
    except Exception as e:
        print(f"DEBUG: Error getting weather: {e}")
        
    return location, temp
