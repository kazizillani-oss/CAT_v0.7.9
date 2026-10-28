#!/usr/bin/env bash
# CAT -- Coding Agent Terminal Quick Installer (POSIX: macOS & Linux)
# Supports:
#   curl -fsSL https://raw.githubusercontent.com/kazizillani-oss/CAT_v0.7.9/main/install.sh | bash
#   curl -fsSL https://raw.githubusercontent.com/kazizillani-oss/CAT_v0.7.9/main/install.sh | sudo bash
set -e

# ANSI Styling (Tokyo Night Theme)
CYAN='\033[0;36m'
MAGENTA='\033[0;35m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
WHITE='\033[1;37m'
DARKGRAY='\033[1;30m'
DARKCYAN='\033[0;34m'
RED='\033[0;31m'
NC='\033[0m' # No Color

echo ""
echo -e "${MAGENTA}        /\\_/\\     ${CYAN}  ____    _  _____ ${NC}"
echo -e "${MAGENTA}       ( o.o )    ${CYAN} / ___|  / \\|_   _|${NC}"
echo -e "${MAGENTA}        > ^ <     ${CYAN}| |     / _ \\ | |  ${NC}"
echo -e "${MAGENTA}                  ${CYAN}| |___ / ___ \\| |  ${NC}"
echo -e "${MAGENTA}                  ${CYAN} \\____/_/   \\_\\_|  ${NC}"
echo ""
echo -e "${CYAN}  ================================================================${NC}"
echo -e "${WHITE}     C A T  --  CODING AGENT TERMINAL (POSIX Installer)           ${NC}"
echo -e "${MAGENTA}     Autonomous AI Terminal  |  Tokyo Night Edition  |  v0.8.0b1  ${NC}"
echo -e "${CYAN}  ================================================================${NC}"
echo ""

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

echo -e "${GREEN}[OK] Found Python $("$PYTHON_BIN" --version 2>&1) at $(command -v "$PYTHON_BIN")${NC}"

# Hardware & Local Model Compatibility Inspection
echo ""
echo -e "${DARKCYAN}  ----------------------------------------------------------------${NC}"
echo -e "${YELLOW}  [DEVICE HARDWARE & LOCAL AI MODEL COMPATIBILITY ANALYSIS]${NC}"
echo -e "${DARKCYAN}  ----------------------------------------------------------------${NC}"

# CPU detection
CPU_INFO="Unknown"
if [ "$(uname)" = "Darwin" ]; then
    CPU_INFO=$(sysctl -n machdep.cpu.brand_string 2>/dev/null || uname -m)
elif [ -f /proc/cpuinfo ]; then
    CPU_INFO=$(grep -m1 "model name" /proc/cpuinfo | cut -d: -f2 | xargs 2>/dev/null || uname -m)
else
    CPU_INFO=$(uname -m)
fi

# RAM detection
TOTAL_RAM_GB=8
if [ "$(uname)" = "Darwin" ]; then
    TOTAL_RAM_BYTES=$(sysctl -n hw.memsize 2>/dev/null || echo 8589934592)
    TOTAL_RAM_GB=$((TOTAL_RAM_BYTES / 1073741824))
elif [ -f /proc/meminfo ]; then
    TOTAL_RAM_KB=$(grep MemTotal /proc/meminfo | awk '{print $2}')
    TOTAL_RAM_GB=$((TOTAL_RAM_KB / 1048576))
fi

# GPU / Accelerator
GPU_INFO="Standard Acceleration / CPU"
if command -v nvidia-smi >/dev/null 2>&1; then
    GPU_INFO=$(nvidia-smi --query-gpu=name,memory.total --format=csv,noheader,nounits 2>/dev/null | head -n1 || echo "NVIDIA GPU")
elif [ "$(uname)" = "Darwin" ]; then
    GPU_INFO="Apple Silicon Metal GPU Unified Memory"
fi

# Ollama check
OLLAMA_STATUS="Not Detected"
if command -v ollama >/dev/null 2>&1; then
    OLLAMA_STATUS="Installed ($(ollama --version 2>&1 | head -n1))"
fi

echo -e "${DARKGRAY}    CPU    : ${WHITE}$CPU_INFO${NC}"
echo -e "${DARKGRAY}    RAM    : ${WHITE}${TOTAL_RAM_GB} GB Unified / System RAM${NC}"
echo -e "${DARKGRAY}    GPU    : ${WHITE}$GPU_INFO${NC}"
echo -e "${DARKGRAY}    AI Hub : ${WHITE}Ollama $OLLAMA_STATUS | Hugging Face GGUF Ready${NC}"

# Hardware Tier
if [ "$TOTAL_RAM_GB" -ge 28 ]; then
    echo -e "${DARKGRAY}    Tier   : ${CYAN}Tier 3: Heavy Workstation (${TOTAL_RAM_GB} GB RAM Detected)${NC}"
    echo -e "${DARKCYAN}             Runs up to 14B-32B models effortlessly with acceleration!${NC}"
elif [ "$TOTAL_RAM_GB" -ge 14 ]; then
    echo -e "${DARKGRAY}    Tier   : ${CYAN}Tier 2: Advanced Developer (${TOTAL_RAM_GB} GB RAM Detected)${NC}"
    echo -e "${DARKCYAN}             Optimal for 7B-14B models with fast inference!${NC}"
else
    echo -e "${DARKGRAY}    Tier   : ${CYAN}Tier 1: Standard System (${TOTAL_RAM_GB} GB RAM Detected)${NC}"
    echo -e "${DARKCYAN}             Ideal for 1B-8B models (e.g. Qwen 2.5 Coder 7B, Llama 3.2 3B)!${NC}"
fi

echo ""
echo -e "${YELLOW}    Recommended Latest Ollama & Local Models for Your System:${NC}"
echo -e "${DARKGRAY}    --------------------------------------------------------------------------------${NC}"
echo -e "${DARKCYAN}    Model Identifier       Size    Category    Hardware Status${NC}"
echo -e "${DARKGRAY}    --------------------------------------------------------------------------------${NC}"
echo -e "${WHITE}    qwen2.5-coder:7b       4.7 GB  Coding      ${GREEN}[100% Compatible - Optimal]${NC}"
echo -e "${WHITE}    deepseek-r1:7b         4.7 GB  Reasoning   ${GREEN}[100% Compatible - Optimal]${NC}"
if [ "$TOTAL_RAM_GB" -ge 14 ]; then
    echo -e "${WHITE}    qwen2.5-coder:14b      9.0 GB  Coding      ${GREEN}[100% Compatible - Optimal]${NC}"
    echo -e "${WHITE}    deepseek-r1:14b        9.0 GB  Reasoning   ${GREEN}[100% Compatible - Optimal]${NC}"
    echo -e "${WHITE}    phi4:14b               9.1 GB  Reasoning   ${GREEN}[100% Compatible - Optimal]${NC}"
fi
echo -e "${WHITE}    llama3.2:3b            2.0 GB  Fast/Chat   ${GREEN}[Ultra-Fast Edge Inference]${NC}"
echo -e "${WHITE}    qwen2.5-coder:1.5b     1.0 GB  Autocomplete${GREEN}[Ultra-Low Latency]${NC}"
if [ "$TOTAL_RAM_GB" -ge 28 ]; then
    echo -e "${WHITE}    qwen2.5-coder:32b      19.0 GB Coding      ${CYAN}[Compatible - Workstation]${NC}"
    echo -e "${WHITE}    deepseek-r1:32b        19.0 GB Reasoning   ${CYAN}[Compatible - Workstation]${NC}"
fi
echo -e "${DARKGRAY}    --------------------------------------------------------------------------------${NC}"
echo ""
echo -e "${YELLOW}    Top Hugging Face GGUF Model Matches:${NC}"
echo -e "${DARKCYAN}      - Qwen/Qwen2.5-Coder-7B-Instruct-GGUF        (Q4_K_M ~4.7 GB) -> Fast Coding${NC}"
echo -e "${DARKCYAN}      - deepseek-ai/DeepSeek-R1-Distill-Qwen-7B-GGUF (Q4_K_M ~4.7 GB) -> Reasoning${NC}"
echo ""
echo -e "${YELLOW}    Quick-Start Local AI Command:${NC}"
echo -e "${CYAN}      ollama run qwen2.5-coder:7b     # Run recommended local coding model${NC}"
echo -e "${CYAN}      ollama run deepseek-r1:7b       # Run recommended local reasoning model${NC}"
echo -e "${CYAN}      cat model list                  # Inspect available models inside CAT${NC}"
echo -e "${DARKCYAN}  ----------------------------------------------------------------${NC}"
echo ""

# Check if running as root / sudo
IS_ROOT=0
if [ "$(id -u)" -eq 0 ]; then
    IS_ROOT=1
fi

if [ "$IS_ROOT" -eq 1 ]; then
    echo -e "${YELLOW}[INFO] Installing system-wide with administrative privileges (sudo)...${NC}"
    PIP_FLAGS="--upgrade"
    if "$PYTHON_BIN" -m pip install --help 2>&1 | grep -q -- '--break-system-packages'; then
        PIP_FLAGS="$PIP_FLAGS --break-system-packages"
    fi
    
    SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" 2>/dev/null && pwd || echo "")"
    if [ -n "$SCRIPT_DIR" ] && [ -f "$SCRIPT_DIR/pyproject.toml" ]; then
        echo -e "${YELLOW}Installing from local repository: $SCRIPT_DIR${NC}"
        "$PYTHON_BIN" -m pip install $PIP_FLAGS "$SCRIPT_DIR"
    else
        echo -e "${YELLOW}Installing cct-cli via pip...${NC}"
        "$PYTHON_BIN" -m pip install $PIP_FLAGS --pre cct-cli || "$PYTHON_BIN" -m pip install $PIP_FLAGS git+https://github.com/kazizillani-oss/CAT_v0.7.9.git
    fi
    
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
        "$PYTHON_BIN" -m pip install --user --upgrade --pre cct-cli || "$PYTHON_BIN" -m pip install --user --upgrade git+https://github.com/kazizillani-oss/CAT_v0.7.9.git
    fi
    
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
echo -e "  ${CYAN}cat model list${NC}       # View local models"
echo -e "  ${CYAN}cat curl --version${NC}   # Built-in HTTP/REST curl client"
echo -e "  ${CYAN}cat brew doctor${NC}      # Cross-platform Homebrew & package manager"
echo -e "  ${CYAN}cat sudo --status${NC}    # Universal administrative privilege manager"
echo -e "  ${CYAN}cat${NC}                  # Launch interactive Tokyo Night terminal"
echo ""
