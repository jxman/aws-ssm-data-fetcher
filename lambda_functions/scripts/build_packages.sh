#!/bin/bash
# Build Lambda deployment packages and shared layer
# This script creates ZIP files ready for Terraform deployment

set -e  # Exit on any error

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
LAMBDA_DIR="$(dirname "$SCRIPT_DIR")"
PROJECT_ROOT="$(dirname "$LAMBDA_DIR")"

echo "🚀 Building Lambda deployment packages..."
echo "   Project root: $PROJECT_ROOT"
echo "   Lambda functions: $LAMBDA_DIR"

# Colors for output
GREEN='\033[0;32m'
BLUE='\033[0;34m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

# Function to build a Lambda package
build_function_package() {
    local function_name=$1
    local function_dir="$LAMBDA_DIR/$function_name"
    
    if [ ! -d "$function_dir" ]; then
        echo "❌ Function directory not found: $function_dir"
        return 1
    fi
    
    echo -e "${BLUE}📦 Building $function_name package...${NC}"
    
    # Create build directory
    local build_dir="$function_dir/build"
    rm -rf "$build_dir"
    mkdir -p "$build_dir"
    
    # Copy function code
    cp "$function_dir/lambda_function.py" "$build_dir/"
    
    # Install dependencies if requirements.txt exists
    if [ -f "$function_dir/requirements.txt" ]; then
        echo "   Installing dependencies..."
        pip install -r "$function_dir/requirements.txt" -t "$build_dir" --quiet
        
        # Remove unnecessary files to reduce package size
        find "$build_dir" -type d -name "__pycache__" -exec rm -rf {} + 2>/dev/null || true
        find "$build_dir" -type f -name "*.pyc" -delete 2>/dev/null || true
        find "$build_dir" -type f -name "*.pyo" -delete 2>/dev/null || true
        find "$build_dir" -type d -name "*.dist-info" -exec rm -rf {} + 2>/dev/null || true
        find "$build_dir" -type d -name "*.egg-info" -exec rm -rf {} + 2>/dev/null || true
    fi
    
    # Create deployment package
    local package_file="$function_dir/deployment_package.zip"
    echo "   Creating deployment package: $(basename "$package_file")"
    
    cd "$build_dir"
    zip -r "../deployment_package.zip" . -q
    cd - > /dev/null
    
    # Get package size
    local package_size=$(du -h "$package_file" | cut -f1)
    echo -e "   ✅ Package created: ${GREEN}$package_size${NC}"
    
    # Validate package size (Lambda limit is 50MB)
    local size_bytes=$(stat -f%z "$package_file" 2>/dev/null || stat -c%s "$package_file" 2>/dev/null)
    local max_size=$((50 * 1024 * 1024))  # 50MB in bytes
    
    if [ "$size_bytes" -gt "$max_size" ]; then
        echo -e "   ⚠️  ${YELLOW}Warning: Package size ($package_size) exceeds 50MB Lambda limit${NC}"
    fi
    
    # Clean up build directory
    rm -rf "$build_dir"
}

# Function to build shared layer
build_shared_layer() {
    echo -e "${BLUE}📦 Building shared layer...${NC}"
    
    local layer_dir="$LAMBDA_DIR/shared_layer"
    local build_dir="$layer_dir/build"
    
    rm -rf "$build_dir"
    mkdir -p "$build_dir/python"
    
    # Copy our package modules
    if [ -d "$layer_dir/python/aws_ssm_fetcher" ]; then
        cp -r "$layer_dir/python/aws_ssm_fetcher" "$build_dir/python/"
        echo "   ✅ Copied aws_ssm_fetcher package"
    fi
    
    # Install shared dependencies
    if [ -f "$layer_dir/requirements.txt" ]; then
        echo "   Installing shared dependencies..."
        pip install -r "$layer_dir/requirements.txt" -t "$build_dir/python" --quiet
        
        # Remove unnecessary files
        find "$build_dir" -type d -name "__pycache__" -exec rm -rf {} + 2>/dev/null || true
        find "$build_dir" -type f -name "*.pyc" -delete 2>/dev/null || true
        find "$build_dir" -type f -name "*.pyo" -delete 2>/dev/null || true
        find "$build_dir" -type d -name "*.dist-info" -exec rm -rf {} + 2>/dev/null || true
        find "$build_dir" -type d -name "*.egg-info" -exec rm -rf {} + 2>/dev/null || true
    fi
    
    # Create layer package
    local layer_package="$layer_dir/layer.zip"
    echo "   Creating layer package: $(basename "$layer_package")"
    
    cd "$build_dir"
    zip -r "../layer.zip" . -q
    cd - > /dev/null
    
    # Get layer size
    local layer_size=$(du -h "$layer_package" | cut -f1)
    echo -e "   ✅ Layer created: ${GREEN}$layer_size${NC}"
    
    # Validate layer size (Lambda layer limit is 50MB compressed)
    local size_bytes=$(stat -f%z "$layer_package" 2>/dev/null || stat -c%s "$layer_package" 2>/dev/null)
    local max_size=$((50 * 1024 * 1024))  # 50MB in bytes
    
    if [ "$size_bytes" -gt "$max_size" ]; then
        echo -e "   ⚠️  ${YELLOW}Warning: Layer size ($layer_size) exceeds 50MB limit${NC}"
    fi
    
    # Clean up build directory
    rm -rf "$build_dir"
}

# Check if virtual environment is activated
if [ -z "$VIRTUAL_ENV" ]; then
    echo -e "${YELLOW}⚠️  Virtual environment not detected. Activating .venv...${NC}"
    if [ -f "$PROJECT_ROOT/.venv/bin/activate" ]; then
        source "$PROJECT_ROOT/.venv/bin/activate"
        echo "✅ Activated virtual environment"
    else
        echo "❌ Virtual environment not found at $PROJECT_ROOT/.venv/"
        echo "   Please run: python3 -m venv .venv && source .venv/bin/activate"
        exit 1
    fi
fi

# Check required tools
command -v pip >/dev/null 2>&1 || { echo "❌ pip is required but not installed"; exit 1; }
command -v zip >/dev/null 2>&1 || { echo "❌ zip is required but not installed"; exit 1; }

# Build shared layer first
build_shared_layer

# Build each function package
build_function_package "data_fetcher"
build_function_package "processor" 
build_function_package "report_generator"

echo ""
echo -e "${GREEN}🎉 All packages built successfully!${NC}"
echo ""
echo "📋 Generated files:"
echo "   🗂️  shared_layer/layer.zip"
echo "   📦 data_fetcher/deployment_package.zip"
echo "   📦 processor/deployment_package.zip"
echo "   📦 report_generator/deployment_package.zip"
echo ""
echo -e "${BLUE}📝 Next steps:${NC}"
echo "   1. Review package sizes (should be < 50MB each)"
echo "   2. Test packages locally if needed"
echo "   3. Use these packages in Terraform deployment (Day 4)"
echo ""
echo -e "${GREEN}✅ Ready for Terraform deployment!${NC}"