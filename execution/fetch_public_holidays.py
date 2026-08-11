import sys
import json
import urllib.request
import urllib.error

def fetch_holidays(year, country_code):
    """
    Fetches public holidays for a given year and country code from Nager.Date API.
    Returns a list of dictionaries containing date, name, and description.
    """
    url = f"https://date.nager.at/api/v3/PublicHolidays/{year}/{country_code.upper()}"
    try:
        req = urllib.request.Request(url, headers={'User-Agent': 'Mozilla/5.0'})
        with urllib.request.urlopen(req, timeout=10) as response:
            data = json.loads(response.read().decode('utf-8'))
            holidays = []
            for item in data:
                holidays.append({
                    "date": item.get("date"),
                    "name": item.get("localName") or item.get("name"),
                    "description": item.get("name") if item.get("localName") != item.get("name") else ""
                })
            return holidays
    except urllib.error.HTTPError as e:
        if e.code == 404:
            raise ValueError(f"Country code '{country_code}' or year '{year}' not supported.")
        else:
            raise Exception(f"HTTP Error {e.code}: {e.reason}")
    except Exception as e:
        raise Exception(f"Network error: {e}")

if __name__ == "__main__":
    if len(sys.argv) < 3:
        print(json.dumps({"error": "Usage: fetch_public_holidays.py <year> <country_code>"}))
        sys.exit(1)
        
    try:
        year_arg = int(sys.argv[1])
        country_arg = sys.argv[2]
        res = fetch_holidays(year_arg, country_arg)
        print(json.dumps(res))
    except Exception as ex:
        print(json.dumps({"error": str(ex)}))
        sys.exit(1)
