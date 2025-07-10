#!/bin/bash

# Ensure all child processes are killed on exit
trap 'echo "--- Cleaning up child processes ---"; kill $(jobs -p) &>/dev/null' EXIT

# Script to run multiple instances of load_test.py in parallel

# Check for minimum number of arguments
if [ "$#" -lt 3 ]; then
    echo "Usage: $0 <num_processes> <duration_seconds> <config_file> [requests_per_second]"
    echo "Example: $0 3 60 config.json 10"
    kill $UI_PID
    exit 1
fi

NUM_PROCESSES=$1
DURATION=$2
CONFIG_FILE=$3
BASE_LOG_NAME="log" # Hardcoded base log name
REQUESTS_PER_SECOND=${4:-5} # Default to 5 RPS if not provided

echo "Starting $NUM_PROCESSES load test instance(s)..."
echo "Duration per instance: ${DURATION}s"
echo "Base log name: ${BASE_LOG_NAME} (hardcoded)"
echo "Requests per second per instance: ${REQUESTS_PER_SECOND}"
echo "----------------------------------------------------"

pwd
# Ensure the .venv is activated if it exists and python3 is available
# This assumes the script is run from the project root where .venv is located
if [ -d ".venv" ]; then
    echo "Activating virtual environment..."
    source .venv/bin/activate
else
    echo "Warning: .venv directory not found. Assuming python3 and dependencies are globally available."
fi

# Check if load_test.py exists
if [ ! -f "load_test.py" ]; then
    echo "Error: load_test.py not found in the current directory."
    exit 1
fi

# Check if analyze_logs.py exists
if [ ! -f "analyze_logs.py" ]; then
    echo "Error: analyze_logs.py not found in the current directory."
    exit 1
fi

declare -a LOG_FILES_ARRAY=() # Array to store log file names

for i in $(seq 1 "$NUM_PROCESSES"); do
    LOG_FILE_NAME="${BASE_LOG_NAME}_${i}.json"
    LOG_FILES_ARRAY+=("$LOG_FILE_NAME") # Add to array
    # echo "Starting instance $i: python3 load_test.py $DURATION \"$LOG_FILE_NAME\" $CONFIG_FILE $REQUESTS_PER_SECOND"
    # Run the python script in the background
    python3 load_test.py "$DURATION" "$LOG_FILE_NAME" "$CONFIG_FILE" "$REQUESTS_PER_SECOND" &
done

# Wait for all background processes to complete
wait
echo "----------------------------------------------------"
echo "All load test instances have completed."
# echo "Generated log files: ${LOG_FILES_ARRAY[*]}"

# Call the analysis script if ANALYZE_LOGS is set to true
if [ "${ANALYZE_LOGS}" = "true" ]; then
    echo "----------------------------------------------------"
    echo "Running log analysis..."
    python3 analyze_logs.py
fi

# Deactivate virtual environment if it was activated by this script
if [ -d ".venv" ] && type deactivate > /dev/null; then
    echo "Deactivating virtual environment..."
    deactivate
fi

# The trap at the beginning of the script handles the cleanup of all child processes.
