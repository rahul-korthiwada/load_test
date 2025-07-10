import json
import sys
import os
import glob

def calculate_percentile(latencies_list, percentile_value):
    """Compute latency percentile from a list of latencies.
    Assumes latencies_list contains values in milliseconds."""
    if not latencies_list:
        return 0.0 # Return float for consistency
    sorted_latencies = sorted(latencies_list) # latencies are already in ms
    index = int(len(sorted_latencies) * percentile_value) - 1
    index = max(0, min(index, len(sorted_latencies) - 1))  # Ensure index is within bounds
    return float(sorted_latencies[index]) # returns latency in ms

def aggregate_logs(log_file_paths):
    """
    Aggregates data from multiple JSON log files.

    Args:
        log_file_paths (list): A list of paths to the JSON log files.

    Returns:
        dict: Aggregated results or None if errors occur.
    """
    total_successful_requests = 0
    total_attempted_requests = 0
    all_latencies = []
    sum_of_individual_actual_rps = 0.0

    for file_path in log_file_paths:
        try:
            with open(file_path, 'r') as f:
                data = json.load(f)
                total_successful_requests += data.get("successful_requests", 0)
                total_attempted_requests += data.get("total_attempted_requests", 0)
                all_latencies.extend(data.get("latencies", []))
                sum_of_individual_actual_rps += data.get("actual_rps_instance", 0.0)
        except FileNotFoundError:
            print(f"Error: Log file not found: {file_path}", file=sys.stderr)
            return None
        except json.JSONDecodeError:
            print(f"Error: Could not decode JSON from file: {file_path}", file=sys.stderr)
            return None
        except Exception as e:
            print(f"An unexpected error occurred while processing {file_path}: {e}", file=sys.stderr)
            return None

    if not all_latencies:
        print("No latency data found in the provided log files.", file=sys.stderr)
        # Still return totals if they exist, even if latencies are empty
        return {
            "total_successful_requests": total_successful_requests,
            "total_attempted_requests": total_attempted_requests,
            "final_rps_sum_of_instances": float(f"{sum_of_individual_actual_rps:.2f}"),
            "combined_latencies_count": 0,
            "tp50": 0,
            "tp90": 0,
            "tp95": 0,
            "tp99": 0,
        }

    tp50 = calculate_percentile(all_latencies, 0.50)
    tp90 = calculate_percentile(all_latencies, 0.90)
    tp95 = calculate_percentile(all_latencies, 0.95)
    tp99 = calculate_percentile(all_latencies, 0.99)

    return {
        "total_successful_requests": total_successful_requests,
        "total_attempted_requests": total_attempted_requests,
        "final_rps_sum_of_instances": float(f"{sum_of_individual_actual_rps:.2f}"),
        "combined_latencies_count": len(all_latencies),
        "tp50": tp50,
        "tp90": tp90,
        "tp95": tp95,
        "tp99": tp99,
    }

if __name__ == "__main__":
    log_files = []
    if len(sys.argv) > 1:
        # If log files are provided as arguments, use them
        log_files = sys.argv[1:]
    else:
        # Otherwise, find all log_*.json files in the current directory
        log_files = glob.glob("log_*.json")

    if not log_files:
        print("No log files found or provided to analyze.", file=sys.stderr)
        sys.exit(1)

    aggregated_data = aggregate_logs(log_files)

    if aggregated_data:
        print("\n=== Aggregated Load Test Analysis ===")
        print(f"Log files processed: {', '.join(log_files)}")
        print(f"Total Successful Requests: {aggregated_data['total_successful_requests']}")
        print(f"Total Attempted Requests: {aggregated_data['total_attempted_requests']}")
        print(f"Final RPS (Sum of each instance's actual RPS): {aggregated_data['final_rps_sum_of_instances']:.2f}")
        print(f"Total Latencies Recorded: {aggregated_data['combined_latencies_count']}")
        if aggregated_data['combined_latencies_count'] > 0:
            # Values are already in ms, format to 2 decimal places
            print(f"Overall TP50 Latency: {aggregated_data['tp50']:.2f}ms")
            print(f"Overall TP90 Latency: {aggregated_data['tp90']:.2f}ms")
            print(f"Overall TP95 Latency: {aggregated_data['tp95']:.2f}ms")
            print(f"Overall TP99 Latency: {aggregated_data['tp99']:.2f}ms")
        else:
            print("No latency data to calculate percentiles.")
        print("===================================")
