import aiohttp
import asyncio
import sys
import time
import json
import random
import os
import threading
import requests

# --- Configuration & Argument Parsing ---

if len(sys.argv) < 4:
    print("Usage: python load_test.py <duration_seconds> <log_file_path> <config_file> [requests_per_second]")
    sys.exit(1)

DURATION = int(sys.argv[1])
LOG_FILE_PATH = sys.argv[2]
CONFIG_FILE = sys.argv[3]
# Default to 5 requests per second if not provided
REQUESTS_PER_SECOND = int(sys.argv[4]) if len(sys.argv) > 4 else 5
SERVER_URL = os.environ.get("SERVER_URL", "http://localhost:5000")
        

# --- Global State ---

# Global flag to signal when the test is complete.
DONE = False

# Global dictionary for collecting statistics.
global_data = {
    'total_requests': 0,
    'success_count': 0,
    'failure_count': 0,
    'latency': []
}

def load_config(config_path):
    """Loads the request configuration from a JSON file."""
    try:
        with open(config_path, 'r') as f:
            return json.load(f)
    except FileNotFoundError:
        print(f"Error: Config file not found at {config_path}", flush=True)
        sys.exit(1)
    except json.JSONDecodeError:
        print(f"Error: Could not decode JSON from {config_path}", flush=True)
        sys.exit(1)

CONFIGS = load_config(CONFIG_FILE)


# --- Statistics Functions ---

def add_total():
    """Increments the total requests counter."""
    global global_data
    global_data['total_requests'] += 1

def add_success(latency):
    """Adds a successful request's data."""
    global global_data
    global_data['success_count'] += 1
    global_data['latency'].append(latency)

def add_failure():
    """Increments the failure counter."""
    global global_data
    global_data['failure_count'] += 1

def calculate_percentile(value, latencies):
    """Calculates a given percentile from a list of latencies."""
    if not latencies:
        return 0
    sorted_latencies = sorted(latencies)
    index = int(len(sorted_latencies) * value) - 1
    index = max(0, min(index, len(sorted_latencies) - 1))
    return sorted_latencies[index]


# --- Core Logic ---

def construct_request(session, config):
    """Constructs an aiohttp request object based on the config."""
    headers = config.get("headers", {})
    timeout = aiohttp.ClientTimeout(total=5)
    if config.get("body") is not None:
        return session.post(config["url"], json=config["body"], timeout=timeout, headers=headers)
    else:
        return session.get(config["url"], timeout=timeout, headers=headers)

async def send_request(session, config):
    """Sends a single async request, records latency, and updates stats."""
    await asyncio.sleep(random.uniform(0, 0.5))
    start_time = time.time()
    add_total()
    try:
        async with construct_request(session, config) as response:
            if 200 <= response.status < 300:
                latency = time.time() - start_time
                add_success(latency * 1000) # Store latency in ms
                return 1
            else:
                response_text = await response.text()
                print(f"Request failed with status {response.status}: {response_text[:100]}", flush=True)
    except Exception as e:
        print(f"Request failed with exception: {e}", flush=True)
    add_failure()
    return 0

def register_with_server():
    """Registers with the server to get a unique request_id."""
    try:
        response = requests.post(f"{SERVER_URL}/api/register")
        response.raise_for_status()
        return response.json()["request_id"]
    except requests.exceptions.RequestException as e:
        print(f"Could not register with server: {e}", flush=True)
        return None

def send_data_to_server(request_id, data):
    """Sends a single data point to the server via HTTP POST."""
    try:
        data['request_id'] = request_id
        requests.post(f"{SERVER_URL}/api/test_data", json=data, timeout=0.5)
    except requests.exceptions.RequestException:
        # It's okay if some of these fail, we don't want to slow down the load test
        pass

def shutdown_server(request_id):
    """Sends a shutdown request to the server."""
    try:
        requests.post(f"{SERVER_URL}/api/shutdown", json={"request_id": request_id}, timeout=0.5)
    except requests.exceptions.RequestException:
        pass

def monitor(request_id):
    """
    Prints the current load test status every second.
    This is a standard synchronous function run in a separate thread.
    """
    print("Monitor starting...", flush=True)
    start_time = time.time()
    
    while not DONE:
        # Use standard time.sleep for blocking delay in a thread
        time.sleep(1)
        
        # Accessing global data; for simple monitoring, this is okay.
        if global_data['total_requests'] > 0:
            success_rate = (global_data['success_count'] / global_data['total_requests']) * 100
            failure_rate = (global_data['failure_count'] / global_data['total_requests']) * 100
            
            # Make a copy of latencies to avoid race conditions during calculation
            latencies_copy = global_data['latency'][:]
            tp50 = calculate_percentile(0.50, latencies_copy)
            tp90 = calculate_percentile(0.90, latencies_copy)
            tp99 = calculate_percentile(0.99, latencies_copy)

            elapsed_time = time.time() - start_time
            print(
                f"Time: {int(elapsed_time)}s, "
                f"Total Reqs: {global_data['total_requests']}, "
                f"Success: {success_rate:.2f}%, "
                f"Failure: {failure_rate:.2f}%, "
                f"TP50: {tp50:.2f}ms, "
                f"TP90: {tp90:.2f}ms, "
                f"TP99: {tp99:.2f}ms",
                flush=True
            )
            send_data_to_server(request_id, global_data)

    print("Monitor finished.", flush=True)


async def load_test():
    """Main function to orchestrate the load test."""
    request_id = register_with_server()
    if not request_id:
        return

    if not CONFIGS:
        print("Error: No configurations found in the config file.", flush=True)
        return

    num_configs = len(CONFIGS)
    print(f"Starting load test: {REQUESTS_PER_SECOND} RPS for {DURATION} seconds.", flush=True)
    
    # KEY CHANGE: Run the monitor in a separate thread.
    # daemon=True ensures the thread will not block program exit.
    monitor_thread = threading.Thread(target=monitor, args=(request_id,), daemon=True)
    monitor_thread.start()

    test_start_time = time.time()
    all_tasks = []
    async with aiohttp.ClientSession() as session:
        for _ in range(DURATION):
            second_start_time = time.time()
            for i in range(REQUESTS_PER_SECOND):
                config = CONFIGS[i % num_configs]
                task = asyncio.create_task(send_request(session, config))
                all_tasks.append(task)
            
            elapsed_this_second = time.time() - second_start_time
            if elapsed_this_second < 1.0:
                await asyncio.sleep(1.0 - elapsed_this_second)

    # Wait for all the request-sending tasks to complete
    # await asyncio.gather(*all_tasks)
    for task in all_tasks:
        try:
            await task
        except Exception as e:
            print(f"Error in task: {e}", flush=True)
        except asyncio.exceptions.CancelledError as e:
            print(f"Error in task: {e}", flush=True)
    
    # Signal the monitor thread to stop
    global DONE
    DONE = True
    # Wait for the monitor thread to finish its final print and exit
    monitor_thread.join()

    shutdown_server(request_id)

    total_duration = time.time() - test_start_time

    # --- Final Summary ---
    print("\n=== Load Test Summary ===")
    print(f"Target RPS: {REQUESTS_PER_SECOND}")
    print(f"Target Duration: {DURATION}s")
    print(f"Actual Duration: {total_duration:.2f}s")
    print(f"Total Successful Requests: {global_data['success_count']}")
    print(f"Total Failed Requests: {global_data['failure_count']}")
    
    actual_rps = global_data['success_count'] / total_duration if total_duration > 0 else 0
    print(f"Actual Successful RPS: {actual_rps:.2f}")

    final_tp50 = calculate_percentile(0.50, global_data['latency'])
    final_tp90 = calculate_percentile(0.90, global_data['latency'])
    final_tp95 = calculate_percentile(0.95, global_data['latency'])
    final_tp99 = calculate_percentile(0.99, global_data['latency'])

    print(f"Final TP50 Latency: {final_tp50:.2f}ms")
    print(f"Final TP90 Latency: {final_tp90:.2f}ms")
    print(f"Final TP95 Latency: {final_tp95:.2f}ms")
    print(f"Final TP99 Latency: {final_tp99:.2f}ms")

    # Log results to file if enabled
    if os.environ.get("WRITE_LOGS", "false").lower() == "true":
        log_data = {
            "target_rps_instance": REQUESTS_PER_SECOND,
            "target_duration_instance": DURATION,
            "actual_duration_instance": float(f"{total_duration:.2f}"),
            "successful_requests": global_data['success_count'],
            "failed_requests": global_data['failure_count'],
            "total_attempted_requests": global_data['total_requests'],
            "actual_rps_instance": float(f"{actual_rps:.2f}"),
            "latencies_ms": sorted([float(f"{l:.2f}") for l in global_data['latency']])
        }
        with open(LOG_FILE_PATH, "w") as f:
            json.dump(log_data, f, indent=4)
        print(f"\nLog data written in JSON format to {LOG_FILE_PATH}")


if __name__ == "__main__":
    try:
        asyncio.run(load_test())
    except KeyboardInterrupt:
        print("\nLoad test interrupted by user.", flush=True)
    finally:
        # Ensure the DONE flag is set so the monitor can exit.
        DONE = True
