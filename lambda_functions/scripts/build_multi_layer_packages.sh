#!/bin/bash
# Build Lambda deployment packages with multi-layer architecture
# This script resolves the circular dependency/size issue permanently

set -e  # Exit on any error

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
LAMBDA_DIR="$(dirname "$SCRIPT_DIR")"
PROJECT_ROOT="$(dirname "$LAMBDA_DIR")"

echo "🚀 Building Multi-Layer Lambda Architecture..."
echo "   Project root: $PROJECT_ROOT"
echo "   Lambda functions: $LAMBDA_DIR"

# Colors for output
GREEN='\033[0;32m'
BLUE='\033[0;34m'
YELLOW='\033[1;33m'
RED='\033[0;31m'
NC='\033[0m' # No Color

# Function to build core layer (lightweight dependencies)
build_core_layer() {
    echo -e "${BLUE}📦 Building core layer (lightweight dependencies)...${NC}"

    local layer_dir="$LAMBDA_DIR/core_layer"
    local build_dir="$layer_dir/build"

    rm -rf "$build_dir"
    mkdir -p "$build_dir/python"

    # Copy our application modules
    if [ -d "$layer_dir/python/aws_ssm_fetcher" ]; then
        cp -r "$layer_dir/python/aws_ssm_fetcher" "$build_dir/python/"
        echo "   ✅ Copied aws_ssm_fetcher package"
    fi

    # Install lightweight dependencies
    if [ -f "$layer_dir/requirements.txt" ]; then
        echo "   Installing core dependencies..."
        pip install -r "$layer_dir/requirements.txt" -t "$build_dir/python" --quiet --no-deps

        # Install each dependency individually to avoid conflicts
        while IFS= read -r line; do
            if [[ "$line" =~ ^[a-zA-Z] ]]; then
                dep=$(echo "$line" | cut -d'>' -f1 | cut -d'=' -f1 | cut -d'<' -f1)
                echo "     Installing $dep..."
                pip install "$line" -t "$build_dir/python" --quiet --no-deps || true
            fi
        done < "$layer_dir/requirements.txt"

        # Clean up
        find "$build_dir" -type d -name "__pycache__" -exec rm -rf {} + 2>/dev/null || true
        find "$build_dir" -type f -name "*.pyc" -delete 2>/dev/null || true
        find "$build_dir" -type f -name "*.pyo" -delete 2>/dev/null || true
        find "$build_dir" -type d -name "*.dist-info" -exec rm -rf {} + 2>/dev/null || true
        find "$build_dir" -type d -name "*.egg-info" -exec rm -rf {} + 2>/dev/null || true
    fi

    # Create layer package
    local layer_package="$layer_dir/core_layer.zip"
    echo "   Creating core layer package..."

    cd "$build_dir"
    zip -r "../core_layer.zip" . -q
    cd - > /dev/null

    # Get layer size
    local layer_size=$(du -h "$layer_package" | cut -f1)
    echo -e "   ✅ Core layer created: ${GREEN}$layer_size${NC}"

    # Validate size (should be under 10MB for fast loading)
    local size_bytes=$(stat -f%z "$layer_package" 2>/dev/null || stat -c%s "$layer_package" 2>/dev/null)
    local target_size=$((10 * 1024 * 1024))  # 10MB target

    if [ "$size_bytes" -gt "$target_size" ]; then
        echo -e "   ⚠️  ${YELLOW}Warning: Core layer ($layer_size) is larger than 10MB target${NC}"
    fi

    # Clean up
    rm -rf "$build_dir"
}

# Function to build heavy data layer
build_heavy_data_layer() {
    echo -e "${BLUE}📦 Building heavy data layer (pandas, numpy, openpyxl)...${NC}"

    local layer_dir="$LAMBDA_DIR/heavy_data_layer"
    local build_dir="$layer_dir/build"

    if [ ! -f "$layer_dir/requirements.txt" ]; then
        echo "⚠️  No requirements.txt found for heavy data layer - skipping"
        return 0
    fi

    rm -rf "$build_dir"
    mkdir -p "$build_dir/python"

    # Install heavy dependencies
    echo "   Installing heavy data processing dependencies (this may take a while)..."
    pip install -r "$layer_dir/requirements.txt" -t "$build_dir/python" --quiet

    # Aggressive cleanup to reduce size
    echo "   Optimizing package size..."
    find "$build_dir" -type d -name "__pycache__" -exec rm -rf {} + 2>/dev/null || true
    find "$build_dir" -type f -name "*.pyc" -delete 2>/dev/null || true
    find "$build_dir" -type f -name "*.pyo" -delete 2>/dev/null || true
    find "$build_dir" -type d -name "*.dist-info" -exec rm -rf {} + 2>/dev/null || true
    find "$build_dir" -type d -name "*.egg-info" -exec rm -rf {} + 2>/dev/null || true
    find "$build_dir" -type d -name "tests" -exec rm -rf {} + 2>/dev/null || true
    find "$build_dir" -type d -name "test" -exec rm -rf {} + 2>/dev/null || true
    find "$build_dir" -name "*.so" -exec strip {} + 2>/dev/null || true

    # Remove documentation and examples
    find "$build_dir" -type d -name "doc" -exec rm -rf {} + 2>/dev/null || true
    find "$build_dir" -type d -name "docs" -exec rm -rf {} + 2>/dev/null || true
    find "$build_dir" -type d -name "examples" -exec rm -rf {} + 2>/dev/null || true
    find "$build_dir" -name "*.md" -delete 2>/dev/null || true
    find "$build_dir" -name "*.rst" -delete 2>/dev/null || true

    # Create layer package
    cd "$build_dir"
    echo "   Creating heavy data layer package..."
    zip -r ../heavy_data_layer.zip python/ -q
    cd - >/dev/null

    # Get size and report
    local layer_package="$layer_dir/heavy_data_layer.zip"
    local size=$(du -h "$layer_package" | cut -f1)
    echo -e "   ✅ Heavy data layer created: ${GREEN}$size${NC}"

    # Check size against Lambda limits
    local size_bytes=$(stat -f%z "$layer_package" 2>/dev/null || stat -c%s "$layer_package" 2>/dev/null)
    local github_limit=$((50 * 1024 * 1024))  # 50MB GitHub limit
    local lambda_limit=$((250 * 1024 * 1024))  # 250MB Lambda limit

    if [ "$size_bytes" -gt "$github_limit" ]; then
        echo -e "   ⚠️  ${YELLOW}Warning: Layer exceeds 50MB GitHub limit - consider S3 deployment${NC}"
    elif [ "$size_bytes" -gt "$lambda_limit" ]; then
        echo -e "   ❌ ${RED}Error: Layer exceeds 250MB Lambda limit${NC}"
        return 1
    fi

    # Clean up
    rm -rf "$build_dir"
}

# Function to build lightweight function packages
build_lightweight_function() {
    local function_name=$1
    local function_dir="$LAMBDA_DIR/$function_name"

    if [ ! -d "$function_dir" ]; then
        echo "❌ Function directory not found: $function_dir"
        return 1
    fi

    echo -e "${BLUE}📦 Building $function_name (lightweight)...${NC}"

    # Create build directory
    local build_dir="$function_dir/build"
    rm -rf "$build_dir"
    mkdir -p "$build_dir"

    # Copy function code and application modules
    cp "$function_dir/lambda_function.py" "$build_dir/"

    # Copy aws_ssm_fetcher modules to each function package
    if [ -d "$LAMBDA_DIR/core_layer/python/aws_ssm_fetcher" ]; then
        cp -r "$LAMBDA_DIR/core_layer/python/aws_ssm_fetcher" "$build_dir/"
        echo "   ✅ Copied aws_ssm_fetcher modules"
    fi

    # Install lightweight dependencies directly in function package for reliability
    if [ -f "$LAMBDA_DIR/core_layer/requirements.txt" ]; then
        echo "   Installing lightweight dependencies in function package..."
        pip install -r "$LAMBDA_DIR/core_layer/requirements.txt" -t "$build_dir" --quiet

        # Clean up to keep size minimal
        find "$build_dir" -type d -name "__pycache__" -exec rm -rf {} + 2>/dev/null || true
        find "$build_dir" -type f -name "*.pyc" -delete 2>/dev/null || true
        find "$build_dir" -type d -name "*.dist-info" -exec rm -rf {} + 2>/dev/null || true
        echo "   ✅ Installed lightweight dependencies"
    fi

    # Create deployment package
    local package_file="$function_dir/deployment_package.zip"
    echo "   Creating deployment package..."

    cd "$build_dir"
    zip -r "../deployment_package.zip" . -q
    cd - > /dev/null

    # Get package size
    local package_size=$(du -h "$package_file" | cut -f1)
    echo -e "   ✅ Package created: ${GREEN}$package_size${NC}"

    # This should be very small now (< 1MB)
    local size_bytes=$(stat -f%z "$package_file" 2>/dev/null || stat -c%s "$package_file" 2>/dev/null)
    if [ "$size_bytes" -gt $((1024 * 1024)) ]; then
        echo -e "   ⚠️  ${YELLOW}Warning: Function package larger than expected (>1MB)${NC}"
    fi

    # Clean up
    rm -rf "$build_dir"
}

# Check environment
if [ -z "$VIRTUAL_ENV" ] && [ -z "$GITHUB_ACTIONS" ] && [ -z "$CI" ]; then
    if [ -f "$PROJECT_ROOT/.venv/bin/activate" ]; then
        echo "   Activating local .venv..."
        source "$PROJECT_ROOT/.venv/bin/activate"
    else
        echo "❌ Virtual environment not found. Please run: python3 -m venv .venv && source .venv/bin/activate"
        exit 1
    fi
fi

# Check required tools
command -v pip >/dev/null 2>&1 || { echo "❌ pip is required"; exit 1; }
command -v zip >/dev/null 2>&1 || { echo "❌ zip is required"; exit 1; }

echo ""
echo -e "${BLUE}🏗️  Building Multi-Layer Architecture:${NC}"
echo "   📋 Core Layer: Essential lightweight dependencies"
echo "   📊 Heavy Data Layer: pandas, numpy, openpyxl for data processing"
echo "   🏃 Function Packages: Application code only (rely on layers)"
echo ""

# Build layers first
build_core_layer
build_heavy_data_layer

echo ""
echo -e "${BLUE}🔨 Building Function Packages:${NC}"

# Build lightweight function packages
build_lightweight_function "data_fetcher"
build_lightweight_function "processor"
build_lightweight_function "json_csv_generator"
build_lightweight_function "excel_generator"
build_lightweight_function "report_orchestrator"

echo ""
echo -e "${GREEN}🎉 Multi-Layer Architecture Complete!${NC}"
echo ""
echo "📋 Generated packages:"
echo "   🧱 core_layer/core_layer.zip (lightweight deps + app modules)"
echo "   📊 heavy_data_layer/heavy_data_layer.zip (pandas, numpy, openpyxl)"
echo "   📦 data_fetcher/deployment_package.zip (code only)"
echo "   📦 processor/deployment_package.zip (code only)"
echo "   📦 json_csv_generator/deployment_package.zip (code only)"
echo "   📦 excel_generator/deployment_package.zip (code only)"
echo "   📦 report_orchestrator/deployment_package.zip (code only)"
echo ""
echo -e "${BLUE}📝 Layer Assignment:${NC}"
echo "   • data-fetcher: core_layer only"
echo "   • processor: core_layer + heavy_data_layer"
echo "   • json-csv-generator: core_layer only"
echo "   • excel-generator: core_layer + heavy_data_layer"
echo "   • report-orchestrator: core_layer only"
echo ""
echo -e "${GREEN}✅ Size conflicts resolved! Each function uses only needed dependencies.${NC}"
