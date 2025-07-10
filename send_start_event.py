import sys
import requests

def send_start_event(duration):
    """Sends the test start event to the server via HTTP POST."""
    try:
        print(f"--- Notifying UI server of test start (duration: {duration}s) ---")
        response = requests.post("http://localhost:5000/api/start_test", json={'duration': int(duration)}, timeout=5)
        response.raise_for_status()  # Raise an exception for bad status codes
        print("--- Notification sent successfully ---")
    except requests.exceptions.RequestException as e:
        print(f"Error sending start event: {e}", file=sys.stderr)
        sys.exit(1)

if __name__ == '__main__':
    if len(sys.argv) < 2:
        print("Usage: python send_start_event.py <duration_seconds>", file=sys.stderr)
        sys.exit(1)
    
    duration_arg = sys.argv[1]
    send_start_event(duration_arg)
