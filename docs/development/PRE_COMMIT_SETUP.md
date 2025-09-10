# Pre-commit Hooks Setup Guide

This document explains how to set up and use pre-commit hooks for the AWS SSM Data Fetcher project to ensure code quality and prevent CI pipeline failures.

## Overview

Pre-commit hooks automatically run code quality checks before each commit, catching formatting and linting issues early. This prevents CI pipeline failures and maintains consistent code quality.

## Quick Setup

### 1. Install Pre-commit (First Time Setup)

If you're setting up the project for the first time:

```bash
# Activate virtual environment
source .venv/bin/activate

# Install dependencies (includes pre-commit)
pip install -r requirements.txt

# Install pre-commit hooks
pre-commit install
```

### 2. For Existing Development Environment

If you already have the project set up:

```bash
# Activate virtual environment
source .venv/bin/activate

# Update dependencies
pip install --upgrade -r requirements.txt

# Install/reinstall pre-commit hooks
pre-commit install
```

## What Gets Checked

The pre-commit hooks mirror our GitHub Actions CI pipeline and check:

### Python Code Quality
- **Black**: Code formatting (line length, quotes, spacing)
- **isort**: Import organization and sorting
- **flake8**: Code linting (syntax, style, complexity)
- **mypy**: Static type checking
- **bandit**: Security vulnerability scanning

### Infrastructure & Configuration
- **Terraform fmt**: Terraform file formatting
- **YAML/JSON validation**: Syntax checking for config files
- **Secrets scanning**: Prevent accidental credential commits

### General Code Quality
- **Trailing whitespace**: Remove trailing spaces
- **End of file**: Ensure files end with newline
- **Large files**: Prevent commits of files >10MB
- **Merge conflicts**: Check for unresolved conflicts

## How It Works

### Automatic Execution
Pre-commit hooks run automatically when you execute `git commit`:

```bash
git add .
git commit -m "Your commit message"
# Hooks run automatically here
```

### What Happens During Commit

1. **Automatic Fixes**: Some hooks (like Black, trailing-whitespace) automatically fix issues
2. **Commit Blocked**: If unfixable issues are found, the commit is blocked
3. **Files Modified**: If hooks make changes, you need to review and commit again

Example successful run:
```
trim trailing whitespace.................................................Passed
fix end of files.........................................................Passed
black....................................................................Passed
isort....................................................................Passed
flake8...................................................................Passed
mypy.....................................................................Passed
bandit...................................................................Passed
Terraform fmt............................................................Passed
```

### Manual Execution

You can run hooks manually on all files:

```bash
# Run all hooks on all files
pre-commit run --all-files

# Run specific hook
pre-commit run black --all-files
pre-commit run flake8 --all-files
```

## Troubleshooting

### Hook Failures

When a hook fails, you'll see output like:
```
black....................................................................Failed
- hook id: black
- files were modified by this hook

README.md
```

**Solution**: Review the changes, add them, and commit again:
```bash
git add .
git commit -m "Your commit message"
```

### Configuration Issues

If hooks fail due to missing configuration:

1. **Check configuration files exist**:
   - `pyproject.toml` (Black, isort, flake8, mypy, bandit config)
   - `.pre-commit-config.yaml` (pre-commit configuration)

2. **Reinstall hooks**:
   ```bash
   pre-commit clean
   pre-commit install
   ```

### Emergency Commits

If you need to commit urgently bypassing hooks:

```bash
# Skip all hooks (use sparingly!)
git commit -m "Emergency fix" --no-verify
```

**Note**: Emergency commits will still fail in CI if they have quality issues.

## Configuration

### Pre-commit Configuration

The hooks are configured in `.pre-commit-config.yaml`. Key settings:

```yaml
repos:
  - repo: https://github.com/psf/black
    rev: 24.10.0
    hooks:
      - id: black
        args: ['--config=pyproject.toml']
```

### Python Tools Configuration

All Python tools are configured in `pyproject.toml`:

```toml
[tool.black]
line-length = 88
target-version = ['py311']

[tool.isort]
profile = "black"
multi_line_output = 3

[tool.flake8]
max-line-length = 88
extend-ignore = "E203,W503"
```

## Benefits

### For Developers
- **Immediate feedback**: Catch issues before CI
- **Automatic fixes**: Many issues fixed automatically
- **Consistent style**: Enforced code formatting
- **Faster development**: No waiting for CI to find simple issues

### For the Team
- **Clean CI pipelines**: Fewer failed builds
- **Consistent codebase**: Uniform code style
- **Reduced review time**: Focus on logic, not formatting
- **Security**: Prevent credential commits

## Integration with CI/CD

Pre-commit hooks use the **exact same tools and configurations** as the GitHub Actions CI pipeline:

- ✅ **Same Black version and config**
- ✅ **Same flake8 rules**
- ✅ **Same mypy settings**
- ✅ **Same Terraform formatting**

This ensures that passing pre-commit hooks means passing CI checks.

## Commands Reference

```bash
# Setup
pre-commit install              # Install hooks
pre-commit uninstall           # Remove hooks

# Execution
pre-commit run                 # Run on staged files
pre-commit run --all-files     # Run on all files
pre-commit run <hook-id>       # Run specific hook

# Maintenance
pre-commit autoupdate         # Update hook versions
pre-commit clean              # Clean hook environments
```

## Best Practices

1. **Run hooks regularly**: Use `pre-commit run --all-files` after major changes
2. **Keep hooks updated**: Run `pre-commit autoupdate` monthly
3. **Review automatic changes**: Always review what hooks changed before committing
4. **Don't bypass hooks**: Use `--no-verify` only for true emergencies
5. **Fix issues promptly**: Address hook failures immediately rather than bypassing

## Next Steps

After setting up pre-commit hooks:

1. **Test the setup**: Make a small change and commit to verify hooks run
2. **Run on all files**: Execute `pre-commit run --all-files` to fix any existing issues
3. **Share with team**: Ensure all team members have hooks installed
4. **Monitor CI**: Verify that CI pipelines pass consistently

For questions or issues with pre-commit setup, see the [GitHub Issues](https://github.com/jxman/aws-ssm-data-fetcher/issues) or refer to the [pre-commit documentation](https://pre-commit.com/).
