# load_test

## Overview

This repository contains tools for conducting load tests on applications. It includes a UI component and a script for orchestrating load tests with configurable parameters.

## Getting Started

### Prerequisites

- Python 3.x
- Bash shell environment

### Installation

Clone this repository and ensure all scripts have execute permissions:

```bash
git clone <repository-url>
cd load_test
chmod +x orchestrate_load_test.sh
```

## Usage

### UI Component

To start the UI application:

```bash
python3 ./ui/app.py
```

### Running Load Tests

To execute a load test with the orchestration script:

```bash
./orchestrate_load_test.sh 10 60 config.json 40
```

Parameters:
- `10`: Number of concurrent users/connections
- `60`: Duration of the test in seconds
- `config.json`: Configuration file for the test
- `40`: Request rate per second

## Configuration

Edit `config.json` to customize your load test parameters, endpoints, and other settings.

## Results

After running tests, results will be available in the output directory specified in your configuration.