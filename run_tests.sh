#!/bin/bash

# Install test dependencies
echo "Installing test dependencies..."
pip install -r test_requirements.txt

# Run the test suite
echo "Running test suite..."
pytest -v --tb=short

# Generate coverage report if coverage is available
if command -v coverage &> /dev/null; then
    echo "Generating coverage report..."
    coverage run -m pytest
    coverage report -m
    coverage html
    echo "Coverage report generated in htmlcov/"
fi