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
    
    # 1. Get Location via IP (with retry)
    # Using ip-api.com (free for non-commercial use, no key required for basic)
    for attempt in range(2):
        try:
            loc_resp = requests.get("http://ip-api.com/json/", timeout=10)
            if loc_resp.status_code == 200:
                data = loc_resp.json()
                if data["status"] == "success":
                    location = f"{data['city']}, {data['country']}"
                    break
            else:
                location = "Location Service Unavailable"
        except (requests.exceptions.Timeout, requests.exceptions.ConnectionError):
            if attempt == 0: continue
            print("DEBUG: Location service unreachable (timeout/connection)")
            location = "Location (Offline)"
        except Exception as e:
            print(f"DEBUG: Error getting location: {e}")
            break

    # 2. Get Weather/Temperature (with retry)
    # Using wttr.in (simple weather service)
    for attempt in range(2):
        try:
            weather_resp = requests.get("https://wttr.in/?format=%t", timeout=10)
            if weather_resp.status_code == 200:
                temp = weather_resp.text.strip()
                break
            else:
                temp = "N/A"
        except (requests.exceptions.Timeout, requests.exceptions.ConnectionError):
            if attempt == 0: continue
            print("DEBUG: Weather service unreachable (timeout/connection)")
            temp = "N/A (Offline)"
        except Exception as e:
            print(f"DEBUG: Error getting weather: {e}")
            break
        
    return location, temp
