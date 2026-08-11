import os
import sys
import json
import urllib.request
import urllib.error

DEFAULT_BASE_URL = "http://localhost:20128"
API_PREFIXES = ["/api/v1", "/v1"]


def load_env(env_path=".env"):
    """Load KEY=VALUE lines from a .env file into os.environ (does not override existing vars)."""
    if not os.path.exists(env_path):
        return
    with open(env_path, encoding="utf-8") as fh:
        for line in fh:
            line = line.strip()
            if not line or line.startswith("#") or "=" not in line:
                continue
            key, _, value = line.partition("=")
            os.environ.setdefault(key.strip(), value.strip().strip('"').strip("'"))


def get_base_url():
    """Base URL of the OmniRouter gateway (env OMNIROUTER_BASE_URL)."""
    return os.environ.get("OMNIROUTER_BASE_URL", DEFAULT_BASE_URL).rstrip("/")


def get_api_key():
    """Bearer API key (env OMNIROUTER_API_KEY)."""
    return os.environ.get("OMNIROUTER_API_KEY", "")


def _request(method, path, payload=None):
    """Send an authenticated request, trying each API prefix until one succeeds."""
    headers = {
        "Authorization": f"Bearer {get_api_key()}",
        "Content-Type": "application/json",
    }
    data = json.dumps(payload).encode("utf-8") if payload is not None else None
    last_error = None
    for prefix in API_PREFIXES:
        url = get_base_url() + prefix + path
        req = urllib.request.Request(url, data=data, headers=headers, method=method)
        try:
            with urllib.request.urlopen(req, timeout=60) as resp:
                return resp.status, json.loads(resp.read().decode("utf-8"))
        except urllib.error.HTTPError as e:
            last_error = Exception(f"HTTP {e.code} on {prefix}{path}: {e.read().decode('utf-8', errors='replace')}")
        except Exception as e:
            last_error = Exception(f"Network error on {prefix}{path}: {e}")
    raise last_error


def test_connection():
    """Verify auth and API availability via the models endpoint."""
    status, data = _request("GET", "/models")
    return {"status": status, "models": data.get("data", data)}


def chat(message, model=None, max_tokens=512):
    """Send a chat completion request. Uses the first available model if none given."""
    if model is None:
        _, data = _request("GET", "/models")
        models = data.get("data") or []
        if not models:
            raise Exception("No model available and none specified.")
        model = models[0]["id"]
    payload = {
        "model": model,
        "messages": [{"role": "user", "content": message}],
        "max_tokens": max_tokens,
        "stream": False,
    }
    status, data = _request("POST", "/chat/completions", payload)
    text = data["choices"][0]["message"]["content"]
    return {"status": status, "model": data.get("model"), "reply": text}


def main():
    load_env()
    args = sys.argv[1:]
    if not get_api_key():
        print(json.dumps({"error": "OMNIROUTER_API_KEY not set in .env"}))
        sys.exit(1)
    try:
        if args and args[0] == "models":
            print(json.dumps(test_connection()))
        elif args and args[0] == "chat":
            message = args[1] if len(args) > 1 else "Say hello in one short sentence."
            model = args[2] if len(args) > 2 else None
            print(json.dumps(chat(message, model)))
        else:
            print(json.dumps({"error": "Usage: omnirouter_client.py <models|chat> [message] [model]"}))
            sys.exit(1)
    except Exception as e:
        print(json.dumps({"error": str(e)}))
        sys.exit(1)


if __name__ == "__main__":
    main()
