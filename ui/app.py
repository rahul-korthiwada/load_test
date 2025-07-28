import sys
import time
import threading
import uuid
import subprocess
import os
from flask import Flask, render_template, request, jsonify

app = Flask(__name__)

# --- Global State Management ---
state = {
    'test_config': {'start_time': None, 'duration': None, 'test_running': False},
    'metrics': {},
    'running_requests': {}
}
latest_snapshot = {}
state_lock = threading.Lock()
active_process = None

# --- Business Logic ---
def calculate_percentile(latencies, percentile):
    if not latencies: return 0
    sorted_latencies = sorted(latencies)
    index = int(len(sorted_latencies) * percentile)
    index = max(0, min(index, len(sorted_latencies) - 1))
    return sorted_latencies[index]

def aggregate_metrics_periodically():
    """Periodically calculates metrics and stores them in a snapshot."""
    global latest_snapshot
    while True:
        time.sleep(1)
        with state_lock:
            if not state['running_requests']:
                state['test_config']['test_running'] = False
                

            if not state['test_config']['test_running']:
                continue

            total_requests = sum(m['total_requests'] for m in state['metrics'].values())
            success_count = sum(m['success_count'] for m in state['metrics'].values())
            failure_count = sum(m['failure_count'] for m in state['metrics'].values())
            latencies = []
            for m in state['metrics'].values():
                latencies.extend(m['latencies'])

            prev_total = sum(m['prev_total'] for m in state['metrics'].values())
            prev_success = sum(m['prev_success'] for m in state['metrics'].values())
            prev_failure = sum(m['prev_failure'] for m in state['metrics'].values())

            # Calculate per-second rates
            total_rate = total_requests - prev_total
            success_rate = success_count - prev_success
            failure_rate = failure_count - prev_failure

            for request_id in state['metrics']:
                state['metrics'][request_id]['prev_total'] = state['metrics'][request_id]['total_requests']
                state['metrics'][request_id]['prev_success'] = state['metrics'][request_id]['success_count']
                state['metrics'][request_id]['prev_failure'] = state['metrics'][request_id]['failure_count']

            # Calculate average RPS
            if state['test_config']['start_time'] is not None:
                elapsed_time = time.time() - state['test_config']['start_time']
                avg_rps = total_requests / elapsed_time   # Prevent division by zero
            else:
                avg_rps = 0

            # Calculate percentiles
            tp50 = calculate_percentile(latencies, 0.50)
            tp95 = calculate_percentile(latencies, 0.95)
            tp99 = calculate_percentile(latencies, 0.99)
            
            latest_snapshot = {
                'test_config': state['test_config'],
                'metrics': {
                    'total_requests': total_requests,
                    'success_count': success_count,
                    'failure_count': failure_count,
                    'avg_rps': round(avg_rps, 2),
                    'tp50': round(tp50, 2), 
                    'tp95': round(tp95, 2), 
                    'tp99': round(tp99, 2),
                    'total_rps': round(total_rate, 2), 
                    'success_rps': round(success_rate, 2), 
                    'failure_rps': round(failure_rate, 2),
                }
            }
            for request_id in state['metrics']:
                state['metrics'][request_id]['latencies'] = []

# --- API Endpoints ---
@app.route('/')
def index():
    """Serves the main dashboard page."""
    api_url = os.environ.get('API_URL', 'http://localhost:5000')
    return render_template('index.html', api_url=api_url)

@app.route('/api/register', methods=['POST'])
def register():
    """Registers a new load test client and returns a unique ID."""
    with state_lock:
        request_id = str(uuid.uuid4())
        state['metrics'][request_id] = {
            'total_requests': 0, 'success_count': 0, 'failure_count': 0,
            'latencies': [], 'prev_total': 0, 'prev_success': 0, 'prev_failure': 0,
        }
        state['running_requests'][request_id] = True
        if not state['test_config']['test_running'] or state['running_requests'][request_id] == False:
            state['test_config']['start_time'] = time.time()
            state['test_config']['test_running'] = True
    return jsonify({"request_id": request_id})

@app.route('/api/shutdown', methods=['POST'])
def shutdown():
    """Marks a load test client as finished."""
    with state_lock:
        request_id = request.json['request_id']
        if request_id in state['running_requests']:
            del state['running_requests'][request_id]
    return jsonify({"status": "ok"})

@app.route('/api/test_data', methods=['POST'])
def test_data():
    """Receives data from a load test client."""
    with state_lock:
        data = request.json
        request_id = data['request_id']
        if request_id not in state['metrics']:
            state['metrics'][request_id] = {
                'total_requests': 0, 'success_count': 0, 'failure_count': 0,
                'latencies': [], 'prev_total': 0, 'prev_success': 0, 'prev_failure': 0,
            }
        
        state['metrics'][request_id]['total_requests'] = data['total_requests']
        state['metrics'][request_id]['success_count'] = data['success_count']
        state['metrics'][request_id]['failure_count'] = data['failure_count']
        if data.get('latency'):
            state['metrics'][request_id]['latencies'] = data['latency']
    return jsonify({"status": "ok"})

@app.route('/api/data')
def get_data():
    """Provides the latest data snapshot to the frontend."""
    return jsonify(latest_snapshot)

@app.route('/api/start_test', methods=['POST'])
def start_test():
    """Starts the load test."""
    global active_process
    with state_lock:
        # Reset metrics
        state['metrics'] = {}
        state['running_requests'] = {}
        state['test_config'] = {'start_time': None, 'duration': None, 'test_running': False}
        global latest_snapshot
        latest_snapshot = {}

    data = request.get_json()
    rps = data.get('rps')
    duration = data.get('duration')
    if not rps:
        return jsonify({"status": "error", "message": "RPS value is required"}), 400
    if not duration:
        return jsonify({"status": "error", "message": "Duration value is required"}), 400

    command = f"./orchestrate_load_test.sh 1 {duration} ./config.json {rps}"
    try:
        # Using Popen for non-blocking execution
        active_process = subprocess.Popen(command, shell=True)
        return jsonify({"status": "ok", "message": f"Load test started with {rps} RPS for {duration} seconds."})
    except Exception as e:
        return jsonify({"status": "error", "message": str(e)}), 500

@app.route('/api/stop_test', methods=['POST'])
def stop_test():
    """Stops the test and metric aggregation."""
    global active_process
    with state_lock:
        state['test_config']['test_running'] = False
        if active_process:
            try:
                active_process.terminate()
                active_process = None
                state['metrics'] = {}
                state['running_requests'] = {}
                state['test_config'] = {'start_time': None, 'duration': None, 'test_running': False}
                global latest_snapshot
                latest_snapshot = {}
            except Exception as e:
                return jsonify({"status": "error", "message": str(e)}), 500
        

    return jsonify({"status": "ok", "message": "Test stopped"})

if __name__ == '__main__':
    # Start the background thread for metric aggregation
    aggregator_thread = threading.Thread(target=aggregate_metrics_periodically, daemon=True)
    aggregator_thread.start()
    # Run the Flask app
    app.run(host='0.0.0.0', port=5000, debug=True)
