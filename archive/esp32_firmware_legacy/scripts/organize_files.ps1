# Script to organize firmware files into logical folders
# Run this from the firmware directory

$mainDir = "main"
$firmwareDir = "."

# Create directories
Write-Host "Creating folder structure..."
New-Item -ItemType Directory -Force -Path "$mainDir\core" | Out-Null
New-Item -ItemType Directory -Force -Path "$mainDir\managers" | Out-Null
New-Item -ItemType Directory -Force -Path "$mainDir\screens" | Out-Null
New-Item -ItemType Directory -Force -Path "$mainDir\drivers" | Out-Null
New-Item -ItemType Directory -Force -Path "$mainDir\network" | Out-Null
New-Item -ItemType Directory -Force -Path "$mainDir\storage" | Out-Null
New-Item -ItemType Directory -Force -Path "$mainDir\utils" | Out-Null
New-Item -ItemType Directory -Force -Path "$mainDir\docs" | Out-Null
New-Item -ItemType Directory -Force -Path "$firmwareDir\scripts" | Out-Null

# Move core files
Write-Host "Moving core files..."
Move-Item -Path "$mainDir\main.cpp" -Destination "$mainDir\core\" -Force -ErrorAction SilentlyContinue
Move-Item -Path "$mainDir\app_state.*" -Destination "$mainDir\core\" -Force -ErrorAction SilentlyContinue
Move-Item -Path "$mainDir\state_coordinator.*" -Destination "$mainDir\core\" -Force -ErrorAction SilentlyContinue

# Move manager files
Write-Host "Moving manager files..."
Get-ChildItem -Path "$mainDir" -Filter "*_manager.*" | Move-Item -Destination "$mainDir\managers\" -Force -ErrorAction SilentlyContinue

# Move screen files
Write-Host "Moving screen files..."
Move-Item -Path "$mainDir\*_screen.*" -Destination "$mainDir\screens\" -Force -ErrorAction SilentlyContinue
Move-Item -Path "$mainDir\launcher.*" -Destination "$mainDir\screens\" -Force -ErrorAction SilentlyContinue
Move-Item -Path "$mainDir\watch_face_enhanced.*" -Destination "$mainDir\screens\" -Force -ErrorAction SilentlyContinue

# Move driver files
Write-Host "Moving driver files..."
Move-Item -Path "$mainDir\*_handler.*" -Destination "$mainDir\drivers\" -Force -ErrorAction SilentlyContinue
Move-Item -Path "$mainDir\motion_sensor.*" -Destination "$mainDir\drivers\" -Force -ErrorAction SilentlyContinue
Move-Item -Path "$mainDir\i2c_bus_manager.*" -Destination "$mainDir\drivers\" -Force -ErrorAction SilentlyContinue

# Move network files
Write-Host "Moving network files..."
Move-Item -Path "$mainDir\websocket_client.*" -Destination "$mainDir\network\" -Force -ErrorAction SilentlyContinue
Move-Item -Path "$mainDir\weather_api.*" -Destination "$mainDir\network\" -Force -ErrorAction SilentlyContinue
Move-Item -Path "$mainDir\ntp_sync.*" -Destination "$mainDir\network\" -Force -ErrorAction SilentlyContinue

# Move storage files
Write-Host "Moving storage files..."
Move-Item -Path "$mainDir\sd_storage.*" -Destination "$mainDir\storage\" -Force -ErrorAction SilentlyContinue
Move-Item -Path "$mainDir\usb_msc.*" -Destination "$mainDir\storage\" -Force -ErrorAction SilentlyContinue

# Move utility files
Write-Host "Moving utility files..."
Move-Item -Path "$mainDir\qrcode_generator.*" -Destination "$mainDir\utils\" -Force -ErrorAction SilentlyContinue
Move-Item -Path "$mainDir\echo_cancellation.*" -Destination "$mainDir\utils\" -Force -ErrorAction SilentlyContinue
Move-Item -Path "$mainDir\ui_icons.*" -Destination "$mainDir\utils\" -Force -ErrorAction SilentlyContinue

# Move documentation files (excluding fonts subdirectory)
Write-Host "Moving documentation files..."
Get-ChildItem -Path "$mainDir" -Filter "*.md" -Exclude "ASSET_MANAGEMENT.md", "README.md" | Move-Item -Destination "$mainDir\docs\" -Force -ErrorAction SilentlyContinue

# Move scripts
Write-Host "Moving scripts..."
Move-Item -Path "$firmwareDir\*.ps1" -Destination "$firmwareDir\scripts\" -Force -ErrorAction SilentlyContinue
Move-Item -Path "$firmwareDir\format_sd.py" -Destination "$firmwareDir\scripts\" -Force -ErrorAction SilentlyContinue

Write-Host "File organization complete!"
Write-Host "Note: You may need to update include paths in source files."
