#!/bin/bash
# Linux Chromium Dependencies Installer for MindGraph
#
# This script installs all required system dependencies for Chromium on Linux.
# It should be run on a Linux system with sudo/root privileges.
#
# Usage:
#     sudo bash scripts/install_linux_dependencies.sh
#     # Or:
#     chmod +x scripts/install_linux_dependencies.sh
#     sudo ./scripts/install_linux_dependencies.sh

set -e

echo "============================================================"
echo "MindGraph Linux Chromium Dependencies Installer"
echo "============================================================"
echo ""

# Detect Linux distribution
if [ -f /etc/os-release ]; then
    . /etc/os-release
    DISTRO=$ID
    VERSION=$VERSION_ID
else
    echo "[ERROR] Cannot detect Linux distribution"
    exit 1
fi

echo "[INFO] Detected distribution: $DISTRO $VERSION"
echo ""

# Function to install dependencies for Debian/Ubuntu
install_debian_deps() {
    echo "[INFO] Installing dependencies for Debian/Ubuntu..."
    sudo apt-get update
    sudo apt-get install -y \
        libnss3 \
        libnspr4 \
        libatk1.0-0 \
        libatk-bridge2.0-0 \
        libcups2 \
        libdrm2 \
        libdbus-1-3 \
        libxkbcommon0 \
        libxcomposite1 \
        libxdamage1 \
        libxfixes3 \
        libxrandr2 \
        libgbm1 \
        libasound2 \
        libpango-1.0-0 \
        libcairo2 \
        libatspi2.0-0 \
        libxshmfence1 \
        libxss1 \
        libgdk-pixbuf2.0-0 \
        libgtk-3-0 \
        libgdk-pixbuf2.0-0 \
        libx11-xcb1 \
        libxcomposite1 \
        libxcursor1 \
        libxdamage1 \
        libxi6 \
        libxtst6 \
        libnss3 \
        libcups2 \
        libxss1 \
        libxrandr2 \
        libasound2 \
        libpangocairo-1.0-0 \
        libatk1.0-0 \
        libcairo-gobject2 \
        libgtk-3-0 \
        libgdk-pixbuf2.0-0 \
        fonts-liberation \
        libappindicator3-1 \
        xdg-utils \
        libxkbcommon0 \
        libgbm1 \
        libxshmfence1
}

# Function to install dependencies for RHEL/CentOS/Fedora
install_rhel_deps() {
    echo "[INFO] Installing dependencies for RHEL/CentOS/Fedora..."
    if command -v dnf &> /dev/null; then
        sudo dnf install -y \
            nss \
            nspr \
            atk \
            cups-libs \
            libdrm \
            dbus-glib \
            libxkbcommon \
            libXcomposite \
            libXdamage \
            libXfixes \
            libXrandr \
            mesa-libgbm \
            alsa-lib \
            pango \
            cairo \
            at-spi2-atk \
            libxshmfence \
            libXScrnSaver \
            gtk3 \
            gdk-pixbuf2 \
            libX11-xcb \
            libXcomposite \
            libXcursor \
            libXdamage \
            libXi \
            libXtst \
            nss \
            cups-libs \
            libXScrnSaver \
            libXrandr \
            alsa-lib \
            pango \
            cairo \
            atk \
            gtk3 \
            gdk-pixbuf2 \
            liberation-fonts \
            libappindicator \
            xdg-utils \
            libxkbcommon \
            mesa-libgbm \
            libxshmfence
    elif command -v yum &> /dev/null; then
        sudo yum install -y \
            nss \
            nspr \
            atk \
            cups-libs \
            libdrm \
            dbus-glib \
            libxkbcommon \
            libXcomposite \
            libXdamage \
            libXfixes \
            libXrandr \
            mesa-libgbm \
            alsa-lib \
            pango \
            cairo \
            at-spi2-atk \
            libxshmfence \
            libXScrnSaver \
            gtk3 \
            gdk-pixbuf2 \
            libX11-xcb \
            libXcomposite \
            libXcursor \
            libXdamage \
            libXi \
            libXtst \
            nss \
            cups-libs \
            libXScrnSaver \
            libXrandr \
            alsa-lib \
            pango \
            cairo \
            atk \
            gtk3 \
            gdk-pixbuf2 \
            liberation-fonts \
            libappindicator \
            xdg-utils \
            libxkbcommon \
            mesa-libgbm \
            libxshmfence
    fi
}

# Function to install dependencies for Arch Linux
install_arch_deps() {
    echo "[INFO] Installing dependencies for Arch Linux..."
    sudo pacman -S --noconfirm \
        nss \
        nspr \
        atk \
        cups \
        libdrm \
        dbus \
        libxkbcommon \
        libxcomposite \
        libxdamage \
        libxfixes \
        libxrandr \
        mesa \
        alsa-lib \
        pango \
        cairo \
        at-spi2-atk \
        libxshmfence \
        libxss \
        gtk3 \
        gdk-pixbuf2 \
        libx11 \
        libxcomposite \
        libxcursor \
        libxdamage \
        libxi \
        libxtst \
        nss \
        cups \
        libxss \
        libxrandr \
        alsa-lib \
        pango \
        cairo \
        atk \
        gtk3 \
        gdk-pixbuf2 \
        ttf-liberation \
        libappindicator \
        xdg-utils \
        libxkbcommon \
        mesa \
        libxshmfence
}

# Install dependencies based on distribution
case $DISTRO in
    ubuntu|debian)
        install_debian_deps
        ;;
    fedora|rhel|centos|rocky|almalinux)
        install_rhel_deps
        ;;
    arch|manjaro)
        install_arch_deps
        ;;
    *)
        echo "[WARNING] Unsupported distribution: $DISTRO"
        echo "[INFO] Attempting to use Playwright's install-deps command..."
        if command -v playwright &> /dev/null; then
            playwright install-deps chromium
        elif command -v python &> /dev/null; then
            python -m playwright install-deps chromium
        else
            echo "[ERROR] Cannot install dependencies automatically"
            echo "[INFO] Please install Chromium dependencies manually"
            echo "[INFO] See: https://playwright.dev/docs/browsers#installing-system-dependencies"
            exit 1
        fi
        ;;
esac

echo ""
echo "[SUCCESS] Linux dependencies installed successfully!"
echo ""
echo "[INFO] Next steps:"
echo "    1. Run setup script: python scripts/setup.py"
echo "       (This will install Chromium and handle offline setup automatically)"
echo "    2. Or manually install Chromium: python -m playwright install chromium"
echo ""

