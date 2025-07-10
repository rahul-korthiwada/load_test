import requests

def stop_ui_test():
    """Sends a POST request to stop the UI test."""
    try:
        response = requests.post("http://localhost:5000/api/stop_test")
        if response.status_code == 200:
            print("UI test stopped successfully.")
        else:
            print(f"Failed to stop UI test. Status code: {response.status_code}")
    except requests.exceptions.RequestException as e:
        print(f"Error stopping UI test: {e}")

if __name__ == "__main__":
    stop_ui_test()
