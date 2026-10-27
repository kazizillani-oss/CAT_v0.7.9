#!/usr/bin/env bash
# CAT — Coding Agent Terminal Quick Installer (POSIX: macOS & Linux)
# Supports:
#   curl -fsSL https://raw.githubusercontent.com/kazizillani-oss/CAT_v0.7.9/main/install.sh | bash
#   curl -fsSL https://raw.githubusercontent.com/kazizillani-oss/CAT_v0.7.9/main/install.sh | sudo bash
set -e

# Styling
CYAN='\033[0;36m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
RED='\033[0;31m'
NC='\033[0m' # No Color

echo -e "${CYAN}================================================================${NC}"
echo -e "${CYAN}   CAT — Coding Agent Terminal (macOS & Linux Installer)        ${NC}"
echo -e "${CYAN}   Version: 0.8.0b1 | Tokyo Night Edition                       ${NC}"
echo -e "${CYAN}================================================================${NC}"

# Find Python 3.10+
PYTHON_BIN=""
for cmd in python3 python py; do
    if command -v "$cmd" >/dev/null 2>&1; then
        VER=$("$cmd" -c 'import sys; print(f"{sys.version_info.major}.{sys.version_info.minor}")' 2>/dev/null || true)
        MAJOR=$(echo "$VER" | cut -d. -f1)
        MINOR=$(echo "$VER" | cut -d. -f2)
        if [ "$MAJOR" -ge 3 ] && [ "$MINOR" -ge 10 ]; then
            PYTHON_BIN="$cmd"
            break
        fi
    fi
done

if [ -z "$PYTHON_BIN" ]; then
    echo -e "${RED}[ERROR] Python 3.10 or higher is required but not found in PATH.${NC}"
    echo -e "Please install Python 3.10+ using your system package manager:"
    echo -e "  macOS:  brew install python@3.12"
    echo -e "  Debian/Ubuntu: sudo apt-get install python3 python3-pip"
    exit 1
fi

echo -e "${GREEN}[OK] Found Python $("$PYTHON_BIN" --version) at $(command -v "$PYTHON_BIN")${NC}"

# Check if running as root / sudo
IS_ROOT=0
if [ "$(id -u)" -eq 0 ]; then
    IS_ROOT=1
fi

if [ "$IS_ROOT" -eq 1 ]; then
    echo -e "${YELLOW}[INFO] Installing system-wide with administrative privileges (sudo)...${NC}"
    # Use break-system-packages if modern PEP 668 environment
    PIP_FLAGS="--upgrade"
    if "$PYTHON_BIN" -m pip install --help 2>&1 | grep -q -- '--break-system-packages'; then
        PIP_FLAGS="$PIP_FLAGS --break-system-packages"
    fi
    
    # Check if local repo exists or install from PyPI
    SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" 2>/dev/null && pwd || echo "")"
    if [ -n "$SCRIPT_DIR" ] && [ -f "$SCRIPT_DIR/pyproject.toml" ]; then
        echo -e "${YELLOW}Installing from local repository: $SCRIPT_DIR${NC}"
        "$PYTHON_BIN" -m pip install $PIP_FLAGS "$SCRIPT_DIR"
    else
        echo -e "${YELLOW}Installing cct-cli via pip...${NC}"
        "$PYTHON_BIN" -m pip install $PIP_FLAGS cct-cli || "$PYTHON_BIN" -m pip install $PIP_FLAGS git+https://github.com/kazizillani-oss/CAT_v0.7.9.git
    fi
    
    # Symlink cat / catx / cct / cat-curl / cat-brew / cat-sudo into /usr/local/bin if needed
    for alias_cmd in catx cct cat-curl cat-brew cat-sudo; do
        if command -v "$alias_cmd" >/dev/null 2>&1; then
            SRC=$(command -v "$alias_cmd")
            if [ -d "/usr/local/bin" ] && [ "$SRC" != "/usr/local/bin/$alias_cmd" ]; then
                ln -sf "$SRC" "/usr/local/bin/$alias_cmd" 2>/dev/null || true
            fi
        fi
    done
else
    echo -e "${YELLOW}[INFO] Installing in user space (--user)...${NC}"
    SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" 2>/dev/null && pwd || echo "")"
    if [ -n "$SCRIPT_DIR" ] && [ -f "$SCRIPT_DIR/pyproject.toml" ]; then
        echo -e "${YELLOW}Installing from local repository: $SCRIPT_DIR${NC}"
        "$PYTHON_BIN" -m pip install --user --upgrade "$SCRIPT_DIR"
    else
        echo -e "${YELLOW}Installing cct-cli via pip...${NC}"
        "$PYTHON_BIN" -m pip install --user --upgrade cct-cli || "$PYTHON_BIN" -m pip install --user --upgrade git+https://github.com/kazizillani-oss/CAT_v0.7.9.git
    fi
    
    # Check if user bin is in PATH
    USER_BASE=$("$PYTHON_BIN" -m site --user-base 2>/dev/null || echo "$HOME/.local")
    USER_BIN="$USER_BASE/bin"
    if [[ ":$PATH:" != *":$USER_BIN:"* ]]; then
        echo -e "${YELLOW}[NOTE] Add '$USER_BIN' to your PATH in ~/.bashrc or ~/.zshrc:${NC}"
        echo -e "  export PATH=\"\$PATH:$USER_BIN\""
    fi
fi

echo ""
echo -e "${GREEN}================================================================${NC}"
echo -e "${GREEN}   [SUCCESS] CAT CLI Installed Successfully!                    ${NC}"
echo -e "${GREEN}================================================================${NC}"
echo ""
echo -e "Try running:"
echo -e "  ${CYAN}cat --version${NC}        # Check version (or ${CYAN}catx --version${NC} on GNU Linux)"
echo -e "  ${CYAN}cat curl --version${NC}   # Built-in HTTP/REST curl client"
echo -e "  ${CYAN}cat brew doctor${NC}      # Cross-platform Homebrew & package manager"
echo -e "  ${CYAN}cat sudo --status${NC}    # Universal administrative privilege manager"
echo -e "  ${CYAN}cat${NC}                  # Launch interactive Tokyo Night terminal"
echo ""
