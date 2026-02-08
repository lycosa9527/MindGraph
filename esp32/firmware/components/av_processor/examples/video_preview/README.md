# Video Preview Example

## Introduction

This example demonstrates how to use the `video_processor` component to implement video passthrough functionality. It mainly showcases the usage of two core functional modules: `video_capture` (video capturer) and `video_render` (video renderer).

## Hardware Requirements

This example requires a camera module with DVP interface support and an LCD display screen. The camera is connected via the DVP (Digital Video Port) interface, and the LCD display screen is used to display video frames.

## Function Description

### video_processor Component

The `video_processor` provides a unified video processing interface, mainly including the following functional modules:

- **video_capture (Video Capturer)**: Responsible for capturing video data from the camera, supporting MJPEG format encoding
- **video_render (Video Renderer)**: Responsible for decoding video data and rendering it to the LCD display screen, supporting MJPEG format decoding

### Video Passthrough Function

This example implements a simple video passthrough function:

1. **Video Capture**: Capture video frames from the DVP camera through `video_capture`
2. **Video Display**: Display the captured video frames on the LCD screen in real-time through `video_render`

Implementation Flow:

- Initialize basic board-level peripherals (including LCD panel)
- Configure and open the video renderer, set the decode format to MJPEG and output format to RGB565
- Start the video renderer
- Configure and open the video capturer, set the capture format to MJPEG
- Start the video capturer
- Feed the captured video frames to the renderer for display in the callback function

## Usage Instructions

1. Execute the `. ./prebuild.sh` script and select the development board model according to the prompts
2. Connect the DVP interface camera module and LCD display screen
3. Use the `idf.py flash monitor -p` command to flash and run the program
4. After running, the video frames captured by the camera will be displayed on the LCD screen in real-time

## Configuration Parameters

### Video Parameters

- Resolution: 320 x 240
- Frame Rate: 10 fps
- Encoding Format: MJPEG
- Output Pixel Format: RGB565_LE
