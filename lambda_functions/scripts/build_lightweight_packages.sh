#!/bin/bash
# Build lightweight Lambda packages that rely entirely on shared layer
# These packages contain ONLY the lambda_function.py file

set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
LAMBDA_DIR="$(dirname "$SCRIPT_DIR")"

echo "🚀 Building lightweight Lambda packages (code only)..."

# Colors for output
GREEN='\033[0;32m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Function to build lightweight package (code only)
build_lightweight_package() {
    local function_name=$1
    local function_dir="$LAMBDA_DIR/$function_name"

    if [ ! -d "$function_dir" ]; then
        echo "❌ Function directory not found: $function_dir"
        return 1
    fi

    echo -e "${BLUE}📦 Building $function_name (code only)...${NC}"

    # Create build directory
    local build_dir="$function_dir/build"
    rm -rf "$build_dir"
    mkdir -p "$build_dir"

    # Copy ONLY the Lambda function code (no dependencies)
    cp "$function_dir/lambda_function.py" "$build_dir/"

    # Create deployment package
    local package_file="$function_dir/deployment_package.zip"
    echo "   Creating lightweight deployment package..."

    cd "$build_dir"
    zip -r "../deployment_package.zip" . -q
    cd - > /dev/null

    # Get package size
    local package_size=$(du -h "$package_file" | cut -f1)
    echo -e "   ✅ Lightweight package created: ${GREEN}$package_size${NC}"

    # Should be very small (< 10KB)
    local size_bytes=$(stat -f%z "$package_file" 2>/dev/null || stat -c%s "$package_file" 2>/dev/null)
    if [ "$size_bytes" -gt 10240 ]; then
        echo -e "   ⚠️  Package larger than expected (>10KB)"
    fi

    # Clean up
    rm -rf "$build_dir"
}

echo ""
echo -e "${BLUE}🔨 Building Code-Only Function Packages:${NC}"
echo "   Dependencies will be provided by shared layer"
echo ""

# Build all function packages
build_lightweight_package "data_fetcher"
build_lightweight_package "processor"
build_lightweight_package "json_csv_generator"
build_lightweight_package "excel_generator"
build_lightweight_package "report_orchestrator"

echo ""
echo -e "${GREEN}🎉 Lightweight packages complete!${NC}"
echo ""
echo "📋 Generated packages (code only):"
echo "   📦 data_fetcher/deployment_package.zip"
echo "   📦 processor/deployment_package.zip"
echo "   📦 json_csv_generator/deployment_package.zip"
echo "   📦 excel_generator/deployment_package.zip"
echo "   📦 report_orchestrator/deployment_package.zip"
echo ""
echo -e "${GREEN}✅ All functions will use shared layer for dependencies!${NC}"
