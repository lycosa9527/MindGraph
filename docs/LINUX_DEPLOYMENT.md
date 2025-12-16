# Linux Deployment Guide for MindGraph

This guide covers deploying MindGraph on Linux systems, including installing Chromium and its dependencies.

## Quick Start

### Option 1: Automated Setup (Recommended)

```bash
# Run the complete setup script (handles everything automatically)
python scripts/setup.py
```

The setup script will:
- Install Python dependencies
- Install Chromium browser (with system dependencies on Linux)
- Set up offline Chromium installation automatically

### Option 2: Manual Setup

```bash
# Install Python dependencies
pip install -r requirements.txt

# Install Linux system dependencies for Chromium (optional, setup.py handles this)
sudo bash scripts/install_linux_dependencies.sh

# Install Chromium browser
python -m playwright install chromium --with-deps
```

Note: The setup script (`python scripts/setup.py`) handles all of this automatically.

## Manual Dependency Installation

If the automated scripts don't work for your distribution, you can install dependencies manually:

### Debian/Ubuntu

```bash
sudo apt-get update
sudo apt-get install -y \
    libnss3 libnspr4 libatk1.0-0 libatk-bridge2.0-0 \
    libcups2 libdrm2 libdbus-1-3 libxkbcommon0 \
    libxcomposite1 libxdamage1 libxfixes3 libxrandr2 \
    libgbm1 libasound2 libpango-1.0-0 libcairo2 \
    libatspi2.0-0 libxshmfence1 libxss1 \
    libgdk-pixbuf2.0-0 libgtk-3-0 libx11-xcb1 \
    libxcursor1 libxi6 libxtst6 fonts-liberation \
    libappindicator3-1 xdg-utils
```

### RHEL/CentOS/Fedora

```bash
# For Fedora/RHEL 8+
sudo dnf install -y \
    nss nspr atk cups-libs libdrm dbus-glib \
    libxkbcommon libXcomposite libXdamage libXfixes \
    libXrandr mesa-libgbm alsa-lib pango cairo \
    at-spi2-atk libxshmfence libXScrnSaver gtk3 \
    gdk-pixbuf2 libX11-xcb libXcomposite libXcursor \
    libXdamage libXi libXtst liberation-fonts \
    libappindicator xdg-utils

# For CentOS 7/RHEL 7
sudo yum install -y \
    nss nspr atk cups-libs libdrm dbus-glib \
    libxkbcommon libXcomposite libXdamage libXfixes \
    libXrandr mesa-libgbm alsa-lib pango cairo \
    at-spi2-atk libxshmfence libXScrnSaver gtk3 \
    gdk-pixbuf2 libX11-xcb libXcomposite libXcursor \
    libXdamage libXi libXtst liberation-fonts \
    libappindicator xdg-utils
```

### Arch Linux

```bash
sudo pacman -S --noconfirm \
    nss nspr atk cups libdrm dbus libxkbcommon \
    libxcomposite libxdamage libxfixes libxrandr \
    mesa alsa-lib pango cairo at-spi2-atk \
    libxshmfence libxss gtk3 gdk-pixbuf2 \
    libx11 libxcomposite libxcursor libxdamage \
    libxi libxtst ttf-liberation libappindicator \
    xdg-utils
```

## Offline Installation

If you need to deploy on a system without internet access:

1. **On a machine with internet access:**
   ```bash
   # Download Chromium and dependencies
   python scripts/setup.py
   # Or manually:
   python -m playwright install chromium --with-deps
   ```

2. **Copy the following to the offline machine:**
   - `browsers/chromium/` directory (contains Chromium binary)
   - `requirements.txt` and Python packages (use `pip download` to get wheels)
   - System dependency packages (download `.deb`, `.rpm`, or `.pkg.tar.xz` files)

3. **On the offline machine:**
   ```bash
   # Install Python packages from downloaded wheels
   pip install --find-links ./wheels -r requirements.txt
   
   # Install system dependencies from downloaded packages
   # Debian/Ubuntu:
   sudo dpkg -i *.deb
   # RHEL/CentOS/Fedora:
   sudo rpm -ivh *.rpm
   # Arch:
   sudo pacman -U *.pkg.tar.xz
   
   # Chromium is already in browsers/chromium/, no installation needed
   ```

## Verification

After installation, verify everything works:

```bash
# Check Chromium installation
python -c "from playwright.sync_api import sync_playwright; p = sync_playwright().start(); browser = p.chromium.launch(headless=True); print('Chromium OK'); browser.close(); p.stop()"

# Check offline Chromium (should be in browsers/chromium/)
ls -la browsers/chromium/
```

## Troubleshooting

### Chromium fails to launch

1. **Check system dependencies:**
   ```bash
   ldd browsers/chromium/chrome-linux/chrome | grep "not found"
   ```
   Install any missing libraries.

2. **Check permissions:**
   ```bash
   chmod +x browsers/chromium/chrome-linux/chrome
   ```

3. **Run with debug output:**
   ```bash
   browsers/chromium/chrome-linux/chrome --version
   ```

### Missing fonts

Install font packages:
```bash
# Debian/Ubuntu
sudo apt-get install -y fonts-liberation fonts-noto-color-emoji

# RHEL/CentOS/Fedora
sudo dnf install -y liberation-fonts google-noto-emoji-fonts

# Arch
sudo pacman -S --noconfirm ttf-liberation noto-fonts-emoji
```

### Permission denied errors

Ensure the Chromium executable has execute permissions:
```bash
chmod +x browsers/chromium/chrome-linux/chrome
```

## Production Deployment

For production servers, consider:

1. **Using systemd service** (see `scripts/setup_systemd.sh`)
2. **Running as non-root user** with proper permissions
3. **Setting up log rotation** for browser logs
4. **Configuring firewall** to restrict access
5. **Using reverse proxy** (nginx/Apache) for HTTPS

## Additional Resources

- [Playwright Linux Dependencies](https://playwright.dev/docs/browsers#installing-system-dependencies)
- [Chromium System Requirements](https://chromium.googlesource.com/chromium/src/+/main/docs/linux_build_instructions.md)

