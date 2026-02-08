# Audio Passthru Example

## Introduction

This example demonstrates how to use the `av_processor` component to implement audio recording and playback functionality. It mainly showcases the usage of two core functional modules: `audio_recorder` (recorder) and `audio_feeder` (player).

## Hardware Requirements

This example is implemented based on the **ESP32-S3-KORVO2-V3** development board, which integrates a microphone array and speakers, supporting audio capture and playback functions.


## Feature Description

### av_processor Component

The `av_processor` component provides a unified audio processing interface, mainly including the following functional modules:

- **audio_recorder (Recorder)**: Responsible for capturing audio data from the microphone, supporting AFE (Audio Front-End) processing functions such as echo cancellation and noise reduction
- **audio_feeder (Player)**: Responsible for feeding audio data into the playback pipeline for playback, suitable for real-time audio stream playback scenarios

### Recording and Playback Function

This example implements a simple audio recording and playback function:

1. **Recording**: Capture audio data from the microphone through `audio_recorder`
2. **Playback**: Play the captured audio data in real-time through `audio_feeder`

Implementation flow:
- Initialize the audio manager and configure audio device parameters
- Open and configure the recorder, set encoding format to PCM
- Open and configure the player, set decoding format to PCM
- Start the player
- Continuously read recording data in the main loop and feed it to the player for real-time playback

## Usage Instructions

1. Execute the `. ./prebuild.sh` script and select the development board model according to the prompts
2. Use the `idf.py flash monitor -p` command to flash and run the program
3. After running, speak into the microphone, and the sound will be played back through the speaker in real-time

## Configuration Parameters

- Sample rate: 16000 Hz
- Bit depth: 32 bit
- Channels: 2 (mono)
- Frame duration: 20 ms

