#!/bin/bash
#
# db-up installation script
# Installs the db-up PostgreSQL database connectivity monitor
#

set -e

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

# Minimum Python version required
MIN_PYTHON_MAJOR=3
MIN_PYTHON_MINOR=8

print_success() {
    echo -e "${GREEN}[OK]${NC} $1"
}

print_warning() {
    echo -e "${YELLOW}[WARNING]${NC} $1"
}

print_error() {
    echo -e "${RED}[ERROR]${NC} $1"
}

print_info() {
    echo -e "     $1"
}

# Find the script's directory (works even if symlinked)
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

echo ""
echo "====================================="
echo "  db-up Installation Script"
echo "====================================="
echo ""

# Check if Python 3 is installed
PYTHON_CMD=""
for cmd in python3 python; do
    if command -v "$cmd" &> /dev/null; then
        # Check if this is Python 3
        if "$cmd" -c "import sys; sys.exit(0 if sys.version_info[0] == 3 else 1)" 2>/dev/null; then
            PYTHON_CMD="$cmd"
            break
        fi
    fi
done

if [ -z "$PYTHON_CMD" ]; then
    print_error "Python 3 is required but not found."
    echo ""
    print_info "Please install Python 3.8 or later:"
    print_info "  - Ubuntu/Debian: sudo apt install python3 python3-pip python3-venv"
    print_info "  - macOS: brew install python3"
    print_info "  - Fedora: sudo dnf install python3 python3-pip"
    echo ""
    exit 1
fi

print_success "Found Python: $PYTHON_CMD"

# Check Python version
PYTHON_VERSION=$("$PYTHON_CMD" -c "import sys; print(f'{sys.version_info.major}.{sys.version_info.minor}')")
PYTHON_MAJOR=$("$PYTHON_CMD" -c "import sys; print(sys.version_info.major)")
PYTHON_MINOR=$("$PYTHON_CMD" -c "import sys; print(sys.version_info.minor)")

if [ "$PYTHON_MAJOR" -lt "$MIN_PYTHON_MAJOR" ] || { [ "$PYTHON_MAJOR" -eq "$MIN_PYTHON_MAJOR" ] && [ "$PYTHON_MINOR" -lt "$MIN_PYTHON_MINOR" ]; }; then
    print_error "Python $MIN_PYTHON_MAJOR.$MIN_PYTHON_MINOR or later is required (found $PYTHON_VERSION)"
    exit 1
fi

print_success "Python version $PYTHON_VERSION is supported"

# Check if pip is available
if ! "$PYTHON_CMD" -m pip --version &> /dev/null; then
    print_error "pip is not available for $PYTHON_CMD"
    echo ""
    print_info "Please install pip:"
    print_info "  - Ubuntu/Debian: sudo apt install python3-pip"
    print_info "  - macOS: python3 -m ensurepip"
    print_info "  - Or: curl https://bootstrap.pypa.io/get-pip.py | $PYTHON_CMD"
    echo ""
    exit 1
fi

print_success "pip is available"

# Check if venv module is available
if ! "$PYTHON_CMD" -c "import venv" &> /dev/null; then
    print_warning "venv module not found. Virtual environment creation may fail."
    print_info "Install with: sudo apt install python3-venv (Ubuntu/Debian)"
fi

# Parse command line arguments
USE_VENV=false
VENV_PATH=""
DEV_INSTALL=false
GLOBAL_INSTALL=false

show_help() {
    echo "Usage: $0 [OPTIONS]"
    echo ""
    echo "Options:"
    echo "  --venv PATH     Install in a virtual environment at PATH"
    echo "  --dev           Install development dependencies as well"
    echo "  --global        Install globally (requires sudo for system Python)"
    echo "  --help          Show this help message"
    echo ""
    echo "Examples:"
    echo "  $0                    # Install for current user"
    echo "  $0 --venv ./venv      # Install in virtual environment"
    echo "  $0 --dev              # Install with dev dependencies"
    echo "  $0 --venv .venv --dev # Virtual env with dev dependencies"
    echo ""
}

while [[ $# -gt 0 ]]; do
    case $1 in
        --venv)
            USE_VENV=true
            VENV_PATH="$2"
            shift 2
            ;;
        --dev)
            DEV_INSTALL=true
            shift
            ;;
        --global)
            GLOBAL_INSTALL=true
            shift
            ;;
        --help|-h)
            show_help
            exit 0
            ;;
        *)
            print_error "Unknown option: $1"
            show_help
            exit 1
            ;;
    esac
done

# Determine pip command
PIP_CMD="$PYTHON_CMD -m pip"

# Handle virtual environment
if [ "$USE_VENV" = true ]; then
    echo ""
    echo "Creating virtual environment at: $VENV_PATH"

    if [ -d "$VENV_PATH" ]; then
        print_warning "Virtual environment already exists at $VENV_PATH"
        read -p "Do you want to recreate it? [y/N] " -n 1 -r
        echo
        if [[ $REPLY =~ ^[Yy]$ ]]; then
            rm -rf "$VENV_PATH"
            "$PYTHON_CMD" -m venv "$VENV_PATH"
            print_success "Virtual environment recreated"
        else
            print_info "Using existing virtual environment"
        fi
    else
        "$PYTHON_CMD" -m venv "$VENV_PATH"
        print_success "Virtual environment created"
    fi

    # Update pip command to use venv
    PIP_CMD="$VENV_PATH/bin/pip"

    # Upgrade pip in venv
    echo ""
    echo "Upgrading pip in virtual environment..."
    "$PIP_CMD" install --upgrade pip -q
    print_success "pip upgraded"
fi

# Install the package
echo ""
echo "Installing db-up..."

INSTALL_ARGS=""
if [ "$DEV_INSTALL" = true ]; then
    INSTALL_ARGS="[dev]"
    print_info "Including development dependencies"
fi

if [ "$GLOBAL_INSTALL" = true ] && [ "$USE_VENV" = false ]; then
    # Global install - might need sudo
    if [ "$(id -u)" -ne 0 ]; then
        print_warning "Global install may require sudo privileges"
    fi
    $PIP_CMD install "$SCRIPT_DIR$INSTALL_ARGS"
else
    # User install (default) or venv install
    if [ "$USE_VENV" = true ]; then
        $PIP_CMD install -e "$SCRIPT_DIR$INSTALL_ARGS"
    else
        $PIP_CMD install --user -e "$SCRIPT_DIR$INSTALL_ARGS"
    fi
fi

if [ $? -eq 0 ]; then
    print_success "db-up installed successfully!"
else
    print_error "Installation failed"
    exit 1
fi

# Verify installation
echo ""
echo "Verifying installation..."

if [ "$USE_VENV" = true ]; then
    DB_UP_CMD="$VENV_PATH/bin/db-up"
else
    # Check various locations
    if command -v db-up &> /dev/null; then
        DB_UP_CMD="db-up"
    elif [ -f "$HOME/.local/bin/db-up" ]; then
        DB_UP_CMD="$HOME/.local/bin/db-up"
    else
        print_warning "db-up command not found in PATH"
        print_info "You may need to add ~/.local/bin to your PATH:"
        print_info "  export PATH=\"\$HOME/.local/bin:\$PATH\""
        print_info ""
        print_info "Add this to your ~/.bashrc or ~/.zshrc for persistence"
        DB_UP_CMD=""
    fi
fi

if [ -n "$DB_UP_CMD" ]; then
    if "$DB_UP_CMD" --version &> /dev/null; then
        VERSION=$("$DB_UP_CMD" --version 2>&1)
        print_success "Installation verified: $VERSION"
    else
        print_warning "db-up command found but may not be working correctly"
    fi
fi

# Print next steps
echo ""
echo "====================================="
echo "  Installation Complete!"
echo "====================================="
echo ""
echo "Quick start:"
echo ""

if [ "$USE_VENV" = true ]; then
    echo "  1. Activate the virtual environment:"
    echo "     source $VENV_PATH/bin/activate"
    echo ""
    echo "  2. Set required environment variables:"
else
    echo "  1. Set required environment variables:"
fi

echo "     export DB_NAME=mydb"
echo "     export DB_PASSWORD=secret"
echo ""

if [ "$USE_VENV" = true ]; then
    echo "  3. Run db-up:"
else
    echo "  2. Run db-up:"
fi
echo "     db-up"
echo ""
echo "For more options, run: db-up --help"
echo "Documentation: https://github.com/yourusername/db-up"
echo ""
