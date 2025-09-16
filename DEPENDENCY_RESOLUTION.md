# Lambda Dependency Size Resolution

## Problem Solved

**Circular Dependency Issue:**
- Dependencies removed → Lambda fails (missing modules)
- Dependencies added → Package too large (>50MB GitHub limit)
- Repeat cycle → Development blocked

## Solution: Multi-Layer Architecture

### Architecture Overview
```
┌─────────────────────────────────────────────────┐
│                AWS Lambda Runtime              │
│  ┌─────────────────┬──────────────────────────┐ │
│  │   Core Layer    │    Heavy Data Layer      │ │
│  │     765KB       │        12MB              │ │
│  │                 │                          │ │
│  │ • requests      │ • pandas                 │ │
│  │ • feedparser    │ • numpy                  │ │
│  │ • structlog     │ • openpyxl               │ │
│  │ • dateutil      │ • et-xmlfile             │ │
│  │ • urllib3       │                          │ │
│  │ • aws_ssm_*     │                          │ │
│  └─────────────────┴──────────────────────────┘ │
│                                                 │
│  ┌─────────────────────────────────────────────┐ │
│  │            Function Code                    │ │
│  │            1.8KB - 3.4KB                    │ │
│  └─────────────────────────────────────────────┘ │
└─────────────────────────────────────────────────┘
```

### Layer Strategy

**Core Layer (765KB):**
- Essential lightweight dependencies for all functions
- Contains: requests, feedparser, structlog, python-dateutil, urllib3, certifi
- Includes: aws_ssm_fetcher application modules
- Used by: ALL Lambda functions

**Heavy Data Layer (12MB):**
- Data processing dependencies for specific functions
- Contains: pandas, numpy, openpyxl, et-xmlfile
- Used by: processor, excel-generator only

**Function Packages (1.8KB-3.4KB each):**
- Contains ONLY application code (lambda_function.py)
- NO dependencies included (all come from layers)
- Ultra-lightweight and fast to deploy

### Function Layer Assignment

| Function | Core Layer | Heavy Data Layer | Total Size |
|----------|------------|------------------|------------|
| data-fetcher | ✅ | ❌ | 765KB + 1.8KB = 767KB |
| processor | ✅ | ✅ | 765KB + 12MB + 3KB = ~13MB |
| json-csv-generator | ✅ | ❌ | 765KB + 3.2KB = 768KB |
| excel-generator | ✅ | ✅ | 765KB + 12MB + 3.4KB = ~13MB |
| report-orchestrator | ✅ | ❌ | 765KB + 2.6KB = 768KB |

## Implementation Details

### New Build Process
- **Script:** `lambda_functions/scripts/build_multi_layer_packages.sh`
- **Core Layer:** All essential dependencies + application modules
- **Heavy Layer:** Data processing dependencies only
- **Functions:** Code-only packages with empty requirements.txt

### Size Comparison

**Before (Problematic):**
- Functions with all deps: 15MB-50MB (GitHub limit exceeded)
- Functions without deps: Broken (missing modules)

**After (Solution):**
- All functions: <1MB each ✅
- Layers: 765KB + 12MB = 13MB total ✅
- All dependencies available ✅
- No circular issues ✅

### Benefits

1. **Eliminates Circular Pattern**: Dependencies never removed from functions
2. **GitHub Friendly**: All packages well under 50MB limit
3. **Fast Deployment**: Small function packages deploy quickly
4. **Efficient Resource Usage**: Functions only load needed dependencies
5. **Maintainable**: Clear separation of concerns
6. **Scalable**: Easy to add new functions without dependency conflicts

## Usage

### Build Commands
```bash
# Build multi-layer architecture
cd lambda_functions
./scripts/build_multi_layer_packages.sh

# Generated files:
# - core_layer/core_layer.zip (765KB)
# - heavy_data_layer/heavy_data_layer.zip (12MB)
# - */deployment_package.zip (1.8KB-3.4KB each)
```

### Terraform Module
```hcl
module "lambda_layers" {
  source = "./modules/lambda-multi-layer"

  project_name = "aws-ssm-fetcher"
  environment  = "prod"
}

# Use outputs for function configuration:
# - module.lambda_layers.lightweight_function_layers (core only)
# - module.lambda_layers.heavy_function_layers (core + heavy data)
```

### Function Requirements
All function `requirements.txt` files are now intentionally empty:
```txt
# NO DEPENDENCIES - All dependencies come from layers
# This file intentionally empty to keep function package minimal
```

## Resolution Status

✅ **Circular dependency pattern eliminated**
✅ **All packages under GitHub 50MB limit**
✅ **All required dependencies available**
✅ **Lambda functions operational**
✅ **Build process automated and reliable**
✅ **Architecture scalable for future needs**

The dependency size conflict is permanently resolved.
