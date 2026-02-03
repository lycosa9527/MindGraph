# ESP32 Smart Response (智回) Watch

This folder contains all code and resources related to the ESP32 Smart Response watch.

## Folder Structure

\\\
esp32/
├── firmware/          # ESP32 firmware code (C/C++)
│   ├── main/         # Main application code
│   ├── components/   # Reusable components (drivers, libraries)
│   └── assets/       # Images, fonts, wallpapers
├── backend/          # Backend integration code (Python)
│   ├── services/     # Backend services for watch management
│   └── routers/      # API endpoints and WebSocket handlers
├── docs/             # Documentation
└── README.md         # This file
\\\

## Hardware

- **Board**: Waveshare ESP32-S3-Touch-AMOLED-2.06
- **Display**: 2.06" AMOLED (410×502 pixels)
- **Audio**: ES8311 codec + ES7210 dual microphone array
- **Connectivity**: WiFi, WebSocket

## Development

### Firmware Development

The firmware uses PlatformIO or ESP-IDF framework.

**PlatformIO:**
\\\ash
cd firmware
pio run -e waveshare-esp32-s3-touch-amoled
pio upload -e waveshare-esp32-s3-touch-amoled
\\\

**ESP-IDF:**
\\\ash
& C:\Espressif\Initialize-Idf.ps1 -IdfId esp-idf-b29c58f93b4ca0f49cdfc4c3ef43b562
cd firmware
idf.py build
idf.py flash
\\\

## Features

- **Out-of-box ready**: Admin pre-configures, teacher assigns, students use immediately
- **Real-time voice**: Server-side STT + LLM + TTS processing
- **Rich UI**: LVGL-based display with wallpapers, animations, QR codes
- **Echo cancellation**: ES7210 dual mic array for hands-free operation
