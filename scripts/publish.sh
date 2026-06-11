#!/bin/bash
set -e

echo "Cleaning previous builds..."
rm -rf dist/ build/ *.egg-info

echo "Building package..."
python -m build

echo "Checking package..."
twine check dist/*

echo ""
echo "Package built successfully!"
echo ""
echo "To publish to PyPI:"
echo "  twine upload dist/*"
echo ""
echo "To publish to TestPyPI:"
echo "  twine upload --repository testpypi dist/*"
