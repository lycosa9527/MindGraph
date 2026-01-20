#!/bin/bash
#
# Install Dependencies Script for MindGraph
# ==========================================
# 
# This script installs required dependencies for MindGraph:
# - Qdrant: Vector database server (required for Knowledge Space)
# - Celery: Distributed task queue (required for background processing)
# - Redis: Required by Celery (will check/install if needed)
#
# Usage:
#   chmod +x install_dependencies.sh
#   sudo ./install_dependencies.sh [--qdrant-only] [--celery-only] [--skip-redis-check]
#
# Options:
#   --qdrant-only      Only install Qdrant
#   --celery-only      Only install Celery (and Redis if needed)
#   --skip-redis-check Skip Redis installation check
#
# @author MindSpring Team
# @date December 2025
#

set -e

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Flags
INSTALL_QDRANT=true
INSTALL_CELERY=true
SKIP_REDIS_CHECK=false

# Parse arguments
for arg in "$@"; do
    case $arg in
        --qdrant-only)
            INSTALL_CELERY=false
            ;;
        --celery-only)
            INSTALL_QDRANT=false
            ;;
        --skip-redis-check)
            SKIP_REDIS_CHECK=true
            ;;
        *)
            echo -e "${RED}Unknown option: $arg${NC}"
            echo "Usage: $0 [--qdrant-only] [--celery-only] [--skip-redis-check]"
            exit 1
            ;;
    esac
done

echo "================================================"
echo "  MindGraph - Install Dependencies"
echo "================================================"
echo ""
echo "This script will install:"
if [ "$INSTALL_QDRANT" = true ]; then
    echo "  ✓ Qdrant Vector Database Server"
fi
if [ "$INSTALL_CELERY" = true ]; then
    echo "  ✓ Celery Python Package"
    if [ "$SKIP_REDIS_CHECK" = false ]; then
        echo "  ✓ Redis (if not installed)"
    fi
fi
echo ""

# Check if running as root for system-level installations
if [ "$EUID" -ne 0 ] && [ "$INSTALL_QDRANT" = true ]; then
    echo -e "${YELLOW}Note:${NC} Root privileges required for Qdrant installation."
    echo "Please run with sudo: sudo $0"
    exit 1
fi

# Warn if running with sudo (may affect conda environment detection)
if [ "$EUID" -eq 0 ] && [ -n "$SUDO_USER" ]; then
    echo -e "${YELLOW}Note:${NC} Running with sudo. The script will try to detect your conda environment."
    echo -e "${YELLOW}      If Python/pip are not found, try: sudo -E $0${NC}"
    echo -e "${YELLOW}      (This preserves your environment variables)${NC}"
    echo ""
fi

# Detect OS
if [ -f /etc/os-release ]; then
    . /etc/os-release
    OS=$ID
    OS_VERSION=$VERSION_ID
elif type lsb_release >/dev/null 2>&1; then
    OS=$(lsb_release -si | tr '[:upper:]' '[:lower:]')
    OS_VERSION=$(lsb_release -sr)
elif [ -f /etc/lsb-release ]; then
    . /etc/lsb-release
    OS=$DISTRIB_ID
    OS_VERSION=$DISTRIB_RELEASE
else
    echo -e "${RED}Could not detect OS. Please install manually.${NC}"
    exit 1
fi

echo -e "${BLUE}Detected OS: $OS $OS_VERSION${NC}"
echo ""

# Function to check if command exists
command_exists() {
    command -v "$1" >/dev/null 2>&1
}

# Function to detect conda environment
detect_conda_env() {
    # Check environment variables first (works when not using sudo)
    if [ -n "$CONDA_DEFAULT_ENV" ] || [ -n "$CONDA_PREFIX" ]; then
        return 0
    fi
    
    # If running with sudo, try to find conda from the original user
    if [ -n "$SUDO_USER" ]; then
        SUDO_USER_HOME=$(eval echo ~$SUDO_USER)
        
        # Check if conda is initialized in user's shell (bashrc, zshrc, etc.)
        if [ -f "$SUDO_USER_HOME/.bashrc" ] && grep -q "conda initialize" "$SUDO_USER_HOME/.bashrc" 2>/dev/null; then
            return 0
        fi
        if [ -f "$SUDO_USER_HOME/.zshrc" ] && grep -q "conda initialize" "$SUDO_USER_HOME/.zshrc" 2>/dev/null; then
            return 0
        fi
        
        # Try to find conda in common locations for the original user
        if [ -d "$SUDO_USER_HOME/.conda" ] || [ -d "$SUDO_USER_HOME/anaconda3" ] || [ -d "$SUDO_USER_HOME/miniconda3" ]; then
            return 0
        fi
        
        # Check if conda is in PATH for the original user
        if sudo -u "$SUDO_USER" bash -c 'command -v conda >/dev/null 2>&1'; then
            return 0
        fi
        
        # Check if Python path suggests conda (common conda Python paths)
        if sudo -u "$SUDO_USER" bash -c 'python -c "import sys; sys.exit(0 if \"conda\" in sys.executable.lower() or \"anaconda\" in sys.executable.lower() or \"miniconda\" in sys.executable.lower() else 1)"' 2>/dev/null; then
            return 0
        fi
    fi
    
    # Check system-wide conda installations
    if [ -d "/opt/conda" ] || [ -d "/usr/local/anaconda3" ] || [ -d "/usr/local/miniconda3" ]; then
        return 0
    fi
    
    # Check if conda is in PATH
    if command_exists conda; then
        return 0
    fi
    
    return 1
}

# Function to find the best Python command
find_python_cmd() {
    # If running with sudo, try to use Python from the original user's environment
    if [ -n "$SUDO_USER" ]; then
        SUDO_USER_HOME=$(eval echo ~$SUDO_USER)
        
        # Try to find conda environment Python
        if [ -n "$CONDA_PREFIX" ] && [ -f "$CONDA_PREFIX/bin/python" ]; then
            if "$CONDA_PREFIX/bin/python" -c "import sys; sys.exit(0)" 2>/dev/null; then
                echo "$CONDA_PREFIX/bin/python"
                return 0
            fi
        fi
        
        # Try common conda locations for the original user
        for CONDA_BASE in "$SUDO_USER_HOME/anaconda3" "$SUDO_USER_HOME/miniconda3" "$SUDO_USER_HOME/.conda" "/opt/conda" "/usr/local/anaconda3" "/usr/local/miniconda3"; do
            if [ -d "$CONDA_BASE" ]; then
                # Try to find conda environments directory
                if [ -d "$CONDA_BASE/envs" ]; then
                    # Try common environment names (python313, base, etc.)
                    for ENV_NAME in python313 python3.13 base; do
                        if [ -f "$CONDA_BASE/envs/$ENV_NAME/bin/python" ]; then
                            if sudo -u "$SUDO_USER" bash -c "\"$CONDA_BASE/envs/$ENV_NAME/bin/python\" -c 'import sys; sys.exit(0)'" 2>/dev/null; then
                                echo "sudo -u $SUDO_USER $CONDA_BASE/envs/$ENV_NAME/bin/python"
                                return 0
                            fi
                        fi
                    done
                    # Try any environment that has python
                    for ENV_DIR in "$CONDA_BASE/envs"/*; do
                        if [ -d "$ENV_DIR" ] && [ -f "$ENV_DIR/bin/python" ]; then
                            if sudo -u "$SUDO_USER" bash -c "\"$ENV_DIR/bin/python\" -c 'import sys; sys.exit(0)'" 2>/dev/null; then
                                echo "sudo -u $SUDO_USER $ENV_DIR/bin/python"
                                return 0
                            fi
                        fi
                    done
                fi
                # Try base environment
                if [ -f "$CONDA_BASE/bin/python" ]; then
                    if sudo -u "$SUDO_USER" bash -c "\"$CONDA_BASE/bin/python\" -c 'import sys; sys.exit(0)'" 2>/dev/null; then
                        echo "sudo -u $SUDO_USER $CONDA_BASE/bin/python"
                        return 0
                    fi
                fi
            fi
        done
        
        # Try to run python as the original user (will use their PATH including conda)
        if sudo -u "$SUDO_USER" bash -c 'command -v python >/dev/null 2>&1 && python -c "import sys; sys.exit(0)" 2>/dev/null'; then
            echo "sudo -u $SUDO_USER python"
            return 0
        fi
        if sudo -u "$SUDO_USER" bash -c 'command -v python3 >/dev/null 2>&1 && python3 -c "import sys; sys.exit(0)" 2>/dev/null'; then
            echo "sudo -u $SUDO_USER python3"
            return 0
        fi
    fi
    
    # First check if we're in a conda environment
    if detect_conda_env; then
        # Try python first (conda environments usually have python)
        if command_exists python && python -c "import sys; sys.exit(0)" 2>/dev/null; then
            echo "python"
            return 0
        fi
        # Fallback to python3 in conda
        if command_exists python3 && python3 -c "import sys; sys.exit(0)" 2>/dev/null; then
            echo "python3"
            return 0
        fi
    fi
    
    # Try python3 first (standard on most systems)
    if command_exists python3 && python3 -c "import sys; sys.exit(0)" 2>/dev/null; then
        echo "python3"
        return 0
    fi
    
    # Fallback to python
    if command_exists python && python -c "import sys; sys.exit(0)" 2>/dev/null; then
        echo "python"
        return 0
    fi
    
    return 1
}

# Helper function to execute Python command (handles sudo -u prefix)
execute_python_cmd() {
    PYTHON_CMD="$1"
    shift
    if echo "$PYTHON_CMD" | grep -q "^sudo -u"; then
        ACTUAL_PYTHON=$(echo "$PYTHON_CMD" | sed 's/sudo -u [^ ]* //')
        sudo -u "$SUDO_USER" bash -c "$ACTUAL_PYTHON $*"
    else
        $PYTHON_CMD "$@"
    fi
}

# Function to find the best pip command
find_pip_cmd() {
    PYTHON_CMD=$(find_python_cmd)
    if [ -z "$PYTHON_CMD" ]; then
        return 1
    fi
    
    # If Python command starts with "sudo -u", handle it specially
    if echo "$PYTHON_CMD" | grep -q "^sudo -u"; then
        # Extract the actual python command
        ACTUAL_PYTHON=$(echo "$PYTHON_CMD" | sed 's/sudo -u [^ ]* //')
        # Try python -m pip with sudo -u
        if sudo -u "$SUDO_USER" bash -c "$ACTUAL_PYTHON -m pip --version >/dev/null 2>&1"; then
            echo "sudo -u $SUDO_USER $ACTUAL_PYTHON -m pip"
            return 0
        fi
    else
        # Try python -m pip first (most reliable, works in conda)
        if $PYTHON_CMD -m pip --version >/dev/null 2>&1; then
            echo "$PYTHON_CMD -m pip"
            return 0
        fi
    fi
    
    # If running with sudo, try pip from original user
    if [ -n "$SUDO_USER" ]; then
        if sudo -u "$SUDO_USER" bash -c 'command -v pip3 >/dev/null 2>&1 && pip3 --version >/dev/null 2>&1'; then
            echo "sudo -u $SUDO_USER pip3"
            return 0
        fi
        if sudo -u "$SUDO_USER" bash -c 'command -v pip >/dev/null 2>&1 && pip --version >/dev/null 2>&1'; then
            echo "sudo -u $SUDO_USER pip"
            return 0
        fi
    fi
    
    # Try pip3
    if command_exists pip3 && pip3 --version >/dev/null 2>&1; then
        echo "pip3"
        return 0
    fi
    
    # Try pip
    if command_exists pip && pip --version >/dev/null 2>&1; then
        echo "pip"
        return 0
    fi
    
    return 1
}

# Function to check if service is running
service_running() {
    if command_exists systemctl; then
        systemctl is-active --quiet "$1" 2>/dev/null
    elif command_exists service; then
        service "$1" status >/dev/null 2>&1
    else
        return 1
    fi
}

# Function to install Redis (if needed)
install_redis() {
    if [ "$SKIP_REDIS_CHECK" = true ]; then
        return 0
    fi

    echo -e "${YELLOW}Checking Redis installation...${NC}"
    
    # Check if Redis is already running
    if service_running redis || service_running redis-server; then
        echo -e "${GREEN}✓ Redis is already running${NC}"
        return 0
    fi

    # Check if Redis is installed
    if command_exists redis-cli; then
        echo -e "${YELLOW}Redis is installed but not running. Starting...${NC}"
        if command_exists systemctl; then
            systemctl start redis-server 2>/dev/null || systemctl start redis 2>/dev/null || true
            systemctl enable redis-server 2>/dev/null || systemctl enable redis 2>/dev/null || true
        elif command_exists service; then
            service redis-server start 2>/dev/null || service redis start 2>/dev/null || true
        fi
        sleep 2
        if redis-cli ping >/dev/null 2>&1; then
            echo -e "${GREEN}✓ Redis started successfully${NC}"
            return 0
        fi
    fi

    # Install Redis
    echo -e "${YELLOW}Installing Redis...${NC}"
    case $OS in
        ubuntu|debian)
            apt-get update
            apt-get install -y redis-server
            systemctl enable redis-server
            systemctl start redis-server
            ;;
        centos|rhel|fedora|rocky|almalinux)
            if command_exists dnf; then
                dnf install -y redis
            else
                yum install -y redis
            fi
            systemctl enable redis
            systemctl start redis
            ;;
        arch|manjaro)
            pacman -S --noconfirm redis
            systemctl enable redis
            systemctl start redis
            ;;
        *)
            echo -e "${RED}Unsupported OS for automatic Redis installation.${NC}"
            echo "Please install Redis manually: https://redis.io/docs/getting-started/"
            return 1
            ;;
    esac

    sleep 2
    if redis-cli ping >/dev/null 2>&1; then
        echo -e "${GREEN}✓ Redis installed and started successfully${NC}"
    else
        echo -e "${RED}✗ Redis installation failed or service not responding${NC}"
        return 1
    fi
}

# Function to check if Qdrant Python package is installed
check_qdrant_python_package() {
    PYTHON_CMD=$(find_python_cmd)
    if [ -n "$PYTHON_CMD" ]; then
        # Handle sudo -u prefix
        if echo "$PYTHON_CMD" | grep -q "^sudo -u"; then
            sudo -u "$SUDO_USER" bash -c "$(echo "$PYTHON_CMD" | sed 's/sudo -u [^ ]* //') -c 'import qdrant_client'" 2>/dev/null && return 0
        else
            $PYTHON_CMD -c "import qdrant_client" 2>/dev/null && return 0
        fi
    fi
    return 1
}

# Function to check if Qdrant server binary exists
check_qdrant_binary() {
    # Check common locations
    if [ -f /usr/local/bin/qdrant ] && [ -x /usr/local/bin/qdrant ]; then
        return 0
    fi
    if [ -f /usr/bin/qdrant ] && [ -x /usr/bin/qdrant ]; then
        return 0
    fi
    if [ -f ~/qdrant/qdrant ] && [ -x ~/qdrant/qdrant ]; then
        return 0
    fi
    return 1
}

# Function to install Qdrant
install_qdrant() {
    echo ""
    echo "================================================"
    echo "  Checking Qdrant Installation"
    echo "================================================"
    echo ""

    # Check if Qdrant server is already running
    if curl -s http://localhost:6333/collections >/dev/null 2>&1; then
        echo -e "${GREEN}✓ Qdrant server is already running on port 6333${NC}"
        
        # Check Python package
        if check_qdrant_python_package; then
            echo -e "${GREEN}✓ Qdrant Python package (qdrant-client) is installed${NC}"
            echo -e "${GREEN}✓ Qdrant is fully installed and running${NC}"
            return 0
        else
            echo -e "${YELLOW}⚠ Qdrant server is running but Python package is missing${NC}"
            echo -e "${YELLOW}Installing Qdrant Python package...${NC}"
            PIP_CMD=$(find_pip_cmd)
            if [ -n "$PIP_CMD" ]; then
                $PIP_CMD install qdrant-client
            else
                echo -e "${RED}✗ pip not found. Please install qdrant-client manually: pip install qdrant-client${NC}"
                return 1
            fi
            if check_qdrant_python_package; then
                echo -e "${GREEN}✓ Qdrant Python package installed successfully${NC}"
                return 0
            else
                echo -e "${RED}✗ Failed to install Qdrant Python package${NC}"
                return 1
            fi
        fi
    fi

    # Check if Qdrant binary exists
    QDRANT_BINARY_EXISTS=false
    QDRANT_SERVICE_EXISTS=false
    QDRANT_NEEDS_SETUP=false
    
    if check_qdrant_binary; then
        QDRANT_BINARY_EXISTS=true
        echo -e "${GREEN}✓ Qdrant server binary found${NC}"
        
        # Check if systemd service exists
        if command_exists systemctl && systemctl list-unit-files 2>/dev/null | grep -q qdrant.service; then
            QDRANT_SERVICE_EXISTS=true
            echo -e "${GREEN}✓ Qdrant systemd service found${NC}"
            
            # Try to start the service
            echo -e "${YELLOW}Starting Qdrant service...${NC}"
            systemctl start qdrant 2>/dev/null || true
            sleep 3
            
            if curl -s http://localhost:6333/collections >/dev/null 2>&1; then
                echo -e "${GREEN}✓ Qdrant started successfully${NC}"
                
                # Check Python package
                if check_qdrant_python_package; then
                    echo -e "${GREEN}✓ Qdrant Python package is installed${NC}"
                    echo -e "${GREEN}✓ Qdrant is fully installed and running${NC}"
                    return 0
                else
                    echo -e "${YELLOW}Installing Qdrant Python package...${NC}"
                    PIP_CMD=$(find_pip_cmd)
                    if [ -n "$PIP_CMD" ]; then
                        $PIP_CMD install qdrant-client
                    fi
                    if check_qdrant_python_package; then
                        echo -e "${GREEN}✓ Qdrant Python package installed successfully${NC}"
                        return 0
                    fi
                fi
            else
                echo -e "${YELLOW}⚠ Qdrant service exists but is not responding. Will reconfigure...${NC}"
                QDRANT_NEEDS_SETUP=true
            fi
        else
            echo -e "${YELLOW}⚠ Qdrant binary found but systemd service not configured${NC}"
            QDRANT_NEEDS_SETUP=true
        fi
    fi

    # Check Python package
    if check_qdrant_python_package; then
        echo -e "${GREEN}✓ Qdrant Python package (qdrant-client) is installed${NC}"
    else
        echo -e "${YELLOW}⚠ Qdrant Python package (qdrant-client) not found${NC}"
    fi

    # Determine what needs to be done
    if [ "$QDRANT_BINARY_EXISTS" = false ]; then
        echo -e "${YELLOW}Installing Qdrant server binary...${NC}"
    elif [ "$QDRANT_NEEDS_SETUP" = true ]; then
        echo -e "${YELLOW}Setting up Qdrant service configuration...${NC}"
    fi

    # Only download and install binary if it doesn't exist
    if [ "$QDRANT_BINARY_EXISTS" = false ]; then
        # Detect architecture
        ARCH=$(uname -m)
        case $ARCH in
            x86_64)
                QDRANT_ARCH="x86_64-unknown-linux-gnu"
                ;;
            aarch64|arm64)
                QDRANT_ARCH="aarch64-unknown-linux-gnu"
                ;;
            *)
                echo -e "${RED}Unsupported architecture: $ARCH${NC}"
                echo "Please install Qdrant manually: https://github.com/qdrant/qdrant/releases"
                return 1
                ;;
        esac

        # Qdrant version (use latest stable)
        QDRANT_VERSION="1.15.5"
        QDRANT_URL="https://github.com/qdrant/qdrant/releases/download/v${QDRANT_VERSION}/qdrant-${QDRANT_ARCH}.tar.gz"

        echo -e "${YELLOW}Downloading Qdrant v${QDRANT_VERSION} for ${ARCH}...${NC}"
        
        # Create temporary directory
        TEMP_DIR=$(mktemp -d)
        cd "$TEMP_DIR"

        # Download Qdrant
        if command_exists wget; then
            wget -q "$QDRANT_URL" -O qdrant.tar.gz
        elif command_exists curl; then
            curl -sL "$QDRANT_URL" -o qdrant.tar.gz
        else
            echo -e "${RED}Neither wget nor curl found. Please install one.${NC}"
            rm -rf "$TEMP_DIR"
            return 1
        fi

        if [ ! -f qdrant.tar.gz ]; then
            echo -e "${RED}✗ Failed to download Qdrant${NC}"
            rm -rf "$TEMP_DIR"
            return 1
        fi

        echo -e "${YELLOW}Extracting Qdrant...${NC}"
        tar -xzf qdrant.tar.gz
        chmod +x qdrant

        # Install binary
        echo -e "${YELLOW}Installing Qdrant binary to /usr/local/bin...${NC}"
        mv qdrant /usr/local/bin/qdrant
        chmod +x /usr/local/bin/qdrant

        # Cleanup
        rm -rf "$TEMP_DIR"
    fi

    # Set up service configuration if needed
    if [ "$QDRANT_BINARY_EXISTS" = false ] || [ "$QDRANT_NEEDS_SETUP" = true ]; then
        # Create directories
        mkdir -p /var/lib/qdrant/storage
        mkdir -p /var/lib/qdrant/snapshots
        mkdir -p /etc/qdrant

        # Create configuration file (only if it doesn't exist or needs update)
        if [ ! -f /etc/qdrant/config.yaml ] || [ "$QDRANT_NEEDS_SETUP" = true ]; then
            echo -e "${YELLOW}Creating Qdrant configuration...${NC}"
            cat > /etc/qdrant/config.yaml <<EOF
storage:
  storage_path: "/var/lib/qdrant/storage"
  snapshots_path: "/var/lib/qdrant/snapshots"
service:
  host: "0.0.0.0"
  api_port: 6333
  grpc_port: 6334
log_level: INFO
EOF
        fi

        # Create systemd service (always recreate to ensure it's correct)
        echo -e "${YELLOW}Creating/updating systemd service...${NC}"
        cat > /etc/systemd/system/qdrant.service <<EOF
[Unit]
Description=Qdrant Vector Database
Documentation=https://qdrant.tech/documentation/
After=network.target

[Service]
Type=simple
ExecStart=/usr/local/bin/qdrant --config-path /etc/qdrant/config.yaml
Restart=always
RestartSec=5
User=root
WorkingDirectory=/var/lib/qdrant
StandardOutput=journal
StandardError=journal

[Install]
WantedBy=multi-user.target
EOF

        # Reload systemd and start service
        echo -e "${YELLOW}Starting Qdrant service...${NC}"
        systemctl daemon-reload
        systemctl enable qdrant
        systemctl start qdrant
    fi

    # Wait for service to start
    echo -e "${YELLOW}Waiting for Qdrant to start...${NC}"
    sleep 5

    # Install Python package if not already installed
    if ! check_qdrant_python_package; then
        echo -e "${YELLOW}Installing Qdrant Python package...${NC}"
        PIP_CMD=$(find_pip_cmd)
        if [ -n "$PIP_CMD" ]; then
            $PIP_CMD install qdrant-client
        else
            echo -e "${RED}✗ pip not found. Please install qdrant-client manually: pip install qdrant-client${NC}"
            return 1
        fi
    fi

    # Verify installation
    if curl -s http://localhost:6333/collections >/dev/null 2>&1; then
        echo -e "${GREEN}✓ Qdrant installed and started successfully${NC}"
        if check_qdrant_python_package; then
            echo -e "${GREEN}✓ Qdrant Python package is installed${NC}"
        fi
        echo ""
        echo "Qdrant is running on:"
        echo "  - API: http://localhost:6333"
        echo "  - gRPC: localhost:6334"
        echo ""
        echo "Service management:"
        echo "  - Status: sudo systemctl status qdrant"
        echo "  - Logs: sudo journalctl -u qdrant -f"
        echo "  - Stop: sudo systemctl stop qdrant"
        echo "  - Start: sudo systemctl start qdrant"
        return 0
    else
        echo -e "${RED}✗ Qdrant installation completed but service is not responding${NC}"
        echo "Check logs with: sudo journalctl -u qdrant -n 50"
        return 1
    fi
}

# Function to install Celery
install_celery() {
    echo ""
    echo "================================================"
    echo "  Checking Celery Installation"
    echo "================================================"
    echo ""

    # Find Python command
    PYTHON_CMD=$(find_python_cmd)
    if [ -z "$PYTHON_CMD" ]; then
        echo -e "${RED}✗ Python not found. Please install Python 3.8+ first.${NC}"
        return 1
    fi

    # Find pip command
    PIP_CMD=$(find_pip_cmd)
    if [ -z "$PIP_CMD" ]; then
        echo -e "${RED}✗ pip not found. Please install pip first.${NC}"
        return 1
    fi

    # Show environment info
    if detect_conda_env; then
        if [ -n "$CONDA_DEFAULT_ENV" ]; then
            echo -e "${BLUE}Detected conda environment: $CONDA_DEFAULT_ENV${NC}"
        elif [ -n "$SUDO_USER" ]; then
            echo -e "${BLUE}Detected conda environment for user: $SUDO_USER${NC}"
        fi
        # Get Python version safely
        if echo "$PYTHON_CMD" | grep -q "^sudo -u"; then
            ACTUAL_PYTHON=$(echo "$PYTHON_CMD" | sed 's/sudo -u [^ ]* //')
            PYTHON_VERSION_STR=$(sudo -u "$SUDO_USER" bash -c "$ACTUAL_PYTHON --version 2>&1")
        else
            PYTHON_VERSION_STR=$($PYTHON_CMD --version 2>&1)
        fi
        echo -e "${BLUE}Using Python: $PYTHON_CMD ($(echo "$PYTHON_VERSION_STR" | awk '{print $2}'))${NC}"
        echo -e "${BLUE}Using pip: $PIP_CMD${NC}"
    fi

    # Check Python version
    if echo "$PYTHON_CMD" | grep -q "^sudo -u"; then
        ACTUAL_PYTHON=$(echo "$PYTHON_CMD" | sed 's/sudo -u [^ ]* //')
        PYTHON_VERSION=$(sudo -u "$SUDO_USER" bash -c "$ACTUAL_PYTHON --version 2>&1" | awk '{print $2}' | cut -d. -f1,2)
    else
        PYTHON_VERSION=$($PYTHON_CMD --version 2>&1 | awk '{print $2}' | cut -d. -f1,2)
    fi
    PYTHON_MAJOR=$(echo $PYTHON_VERSION | cut -d. -f1)
    PYTHON_MINOR=$(echo $PYTHON_VERSION | cut -d. -f2)

    if [ "$PYTHON_MAJOR" -lt 3 ] || ([ "$PYTHON_MAJOR" -eq 3 ] && [ "$PYTHON_MINOR" -lt 8 ]); then
        echo -e "${RED}✗ Python 3.8+ required. Found: $PYTHON_VERSION${NC}"
        return 1
    fi

    echo -e "${GREEN}✓ Python $PYTHON_VERSION found${NC}"

    # Check if Celery is already installed
    CELERY_INSTALLED=false
    if echo "$PYTHON_CMD" | grep -q "^sudo -u"; then
        ACTUAL_PYTHON=$(echo "$PYTHON_CMD" | sed 's/sudo -u [^ ]* //')
        if sudo -u "$SUDO_USER" bash -c "$ACTUAL_PYTHON -c 'import celery'" 2>/dev/null; then
            CELERY_INSTALLED=true
            CELERY_VERSION=$(sudo -u "$SUDO_USER" bash -c "$ACTUAL_PYTHON -c 'import celery; print(celery.__version__)'" 2>/dev/null)
            echo -e "${GREEN}✓ Celery is already installed (version $CELERY_VERSION)${NC}"
        else
            echo -e "${YELLOW}⚠ Celery is not installed${NC}"
        fi
    else
        if $PYTHON_CMD -c "import celery" 2>/dev/null; then
            CELERY_INSTALLED=true
            CELERY_VERSION=$($PYTHON_CMD -c "import celery; print(celery.__version__)" 2>/dev/null)
            echo -e "${GREEN}✓ Celery is already installed (version $CELERY_VERSION)${NC}"
        else
            echo -e "${YELLOW}⚠ Celery is not installed${NC}"
        fi
    fi

    # Check if Redis Python package is installed
    REDIS_PKG_INSTALLED=false
    if echo "$PYTHON_CMD" | grep -q "^sudo -u"; then
        ACTUAL_PYTHON=$(echo "$PYTHON_CMD" | sed 's/sudo -u [^ ]* //')
        if sudo -u "$SUDO_USER" bash -c "$ACTUAL_PYTHON -c 'import redis'" 2>/dev/null; then
            REDIS_PKG_INSTALLED=true
            echo -e "${GREEN}✓ Redis Python package is installed${NC}"
        else
            echo -e "${YELLOW}⚠ Redis Python package is not installed${NC}"
        fi
    else
        if $PYTHON_CMD -c "import redis" 2>/dev/null; then
            REDIS_PKG_INSTALLED=true
            echo -e "${GREEN}✓ Redis Python package is installed${NC}"
        else
            echo -e "${YELLOW}⚠ Redis Python package is not installed${NC}"
        fi
    fi

    # Install Redis server if needed
    install_redis

    # If everything is already installed, return early
    if [ "$CELERY_INSTALLED" = true ] && [ "$REDIS_PKG_INSTALLED" = true ]; then
        echo -e "${GREEN}✓ Celery and dependencies are fully installed${NC}"
        return 0
    fi

    # Install missing components
    if [ "$CELERY_INSTALLED" = false ]; then
        echo -e "${YELLOW}Installing Celery...${NC}"
    fi

    # Install missing packages
    INSTALL_PACKAGES=""
    if [ "$CELERY_INSTALLED" = false ]; then
        INSTALL_PACKAGES="celery"
    fi
    if [ "$REDIS_PKG_INSTALLED" = false ]; then
        if [ -n "$INSTALL_PACKAGES" ]; then
            INSTALL_PACKAGES="$INSTALL_PACKAGES redis"
        else
            INSTALL_PACKAGES="redis"
        fi
    fi

    if [ -n "$INSTALL_PACKAGES" ]; then
        echo -e "${YELLOW}Installing: $INSTALL_PACKAGES${NC}"
        $PIP_CMD install $INSTALL_PACKAGES
    fi

    # Verify installation
    VERIFY_FAILED=false
    if [ "$CELERY_INSTALLED" = false ]; then
        if echo "$PYTHON_CMD" | grep -q "^sudo -u"; then
            ACTUAL_PYTHON=$(echo "$PYTHON_CMD" | sed 's/sudo -u [^ ]* //')
            if sudo -u "$SUDO_USER" bash -c "$ACTUAL_PYTHON -c 'import celery'" 2>/dev/null; then
                CELERY_VERSION=$(sudo -u "$SUDO_USER" bash -c "$ACTUAL_PYTHON -c 'import celery; print(celery.__version__)'" 2>/dev/null)
                echo -e "${GREEN}✓ Celery installed successfully (version $CELERY_VERSION)${NC}"
            else
                echo -e "${RED}✗ Celery installation failed${NC}"
                VERIFY_FAILED=true
            fi
        else
            if $PYTHON_CMD -c "import celery" 2>/dev/null; then
                CELERY_VERSION=$($PYTHON_CMD -c "import celery; print(celery.__version__)" 2>/dev/null)
                echo -e "${GREEN}✓ Celery installed successfully (version $CELERY_VERSION)${NC}"
            else
                echo -e "${RED}✗ Celery installation failed${NC}"
                VERIFY_FAILED=true
            fi
        fi
    fi

    if [ "$REDIS_PKG_INSTALLED" = false ]; then
        if echo "$PYTHON_CMD" | grep -q "^sudo -u"; then
            ACTUAL_PYTHON=$(echo "$PYTHON_CMD" | sed 's/sudo -u [^ ]* //')
            if sudo -u "$SUDO_USER" bash -c "$ACTUAL_PYTHON -c 'import redis'" 2>/dev/null; then
                echo -e "${GREEN}✓ Redis Python package installed${NC}"
            else
                echo -e "${RED}✗ Redis Python package installation failed${NC}"
                VERIFY_FAILED=true
            fi
        else
            if $PYTHON_CMD -c "import redis" 2>/dev/null; then
                echo -e "${GREEN}✓ Redis Python package installed${NC}"
            else
                echo -e "${RED}✗ Redis Python package installation failed${NC}"
                VERIFY_FAILED=true
            fi
        fi
    fi

    if [ "$VERIFY_FAILED" = true ]; then
        return 1
    fi

    echo -e "${GREEN}✓ Celery and dependencies are ready${NC}"
    return 0
}

# Main installation flow
SUCCESS=true

if [ "$INSTALL_QDRANT" = true ]; then
    if ! install_qdrant; then
        SUCCESS=false
    fi
fi

if [ "$INSTALL_CELERY" = true ]; then
    if ! install_celery; then
        SUCCESS=false
    fi
fi

echo ""
echo "================================================"
if [ "$SUCCESS" = true ]; then
    echo -e "${GREEN}Installation completed successfully!${NC}"
    echo ""
    echo "Next steps:"
    echo "1. Add to your .env file:"
    if [ "$INSTALL_QDRANT" = true ]; then
        echo "   QDRANT_HOST=localhost:6333"
    fi
    if [ "$INSTALL_CELERY" = true ]; then
        echo "   REDIS_URL=redis://localhost:6379/0"
    fi
    echo ""
    echo "2. Verify installations:"
    if [ "$INSTALL_QDRANT" = true ]; then
        echo "   curl http://localhost:6333/collections"
    fi
    if [ "$INSTALL_CELERY" = true ]; then
        echo "   redis-cli ping"
        echo "   python3 -c 'import celery; print(celery.__version__)'"
    fi
else
    echo -e "${RED}Installation completed with errors.${NC}"
    echo "Please check the output above for details."
    exit 1
fi
echo "================================================"
