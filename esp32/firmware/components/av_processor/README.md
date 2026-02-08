# AV Processor Component (Audio/Video Processing)

This component provides a unified encapsulation for audio recording/playback/data feeding and video capture/decoding/rendering on ESP platforms, implemented based on middleware such as GMF (General Media Framework), esp-audio-render, esp-video-codec, and esp-capture.

## Feature Overview 🎛️

- **Audio 🎧**:
  - Recording (AEC/VAD/AFE optional)
  - Playback (supports URL and local files, decoding depends on configuration)
  - Data feeding (feeder, suitable for scenarios like RTC/streaming where receiving and playing happen simultaneously)
  - Optional mixer with volume fade and focus control between multiple streams
- **Video 🎥**:
  - Multi-channel video capture
  - Video decoding and rendering callbacks

---

## Quick Start

### 1. Audio Usage

1. Initialize audio manager:

```c
// Method 1: Use default configuration macro (recommended)
audio_manager_config_t cfg = DEFAULT_AUDIO_MANAGER_CONFIG();
cfg.play_dev = your_play_dev;
cfg.rec_dev = your_rec_dev;
strcpy(cfg.mic_layout, "RMNM"); // Microphone layout (optional, for AFE configuration)
cfg.board_sample_rate = 16000;
cfg.board_bits = 32;
cfg.board_channels = 2;
cfg.play_volume = 80;
cfg.rec_volume = 60;
cfg.rec_ref_volume = 60;
cfg.enable_mixer = true; // Enable when mixing feeder and playback is needed

audio_manager_init(&cfg);
```

2. Recording (polling read):

```c
// Recording event callback (optional)
void recorder_event_cb(void *event, void *ctx) {
    // Handle recording events (e.g., AFE events)
}

// Configure recorder (using default configuration macro)
audio_recorder_config_t recorder_cfg = DEFAULT_AUDIO_RECORDER_CONFIG();
// Optional: Configure AFE (runtime configuration, takes priority over Kconfig)
recorder_cfg.afe_config.vad_enable = true;
recorder_cfg.afe_config.vad_mode = 4;
recorder_cfg.afe_config.agc_enable = true;
recorder_cfg.recorder_event_cb = recorder_event_cb;

// Open recorder
audio_recorder_open(&recorder_cfg);
uint8_t buf[2048];
audio_recorder_read_data(buf, sizeof(buf));

audio_recorder_close();
```

3. Feeder playback (suitable for external stream → local playback):

```c
// Configure feeder (using default configuration macro)
audio_feeder_config_t feeder_cfg = DEFAULT_AUDIO_FEEDER_CONFIG();
// Optional: When using OPUS decoder, task_stack is recommended to be >= 4096 * 10
// feeder_cfg.feeder_task_config.task_stack = 4096 * 10;

audio_feeder_open(&feeder_cfg);
audio_feeder_run();
// Feed external data blocks multiple times as needed
audio_feeder_feed_data(pkt, pkt_len);

audio_feeder_stop();
audio_feeder_close();
```

4. Normal playback (URL or local):

```c
// Configure player (using default configuration macro)
audio_playback_config_t playback_cfg = DEFAULT_AUDIO_PLAYBACK_CONFIG();

audio_playback_open(&playback_cfg);
audio_playback_play("http://<ip>:<port>/audio.mp3");

audio_playback_pause();
audio_playback_resume();
audio_playback_stop();
audio_playback_close();
```

5. Prompt playback:

```c
// Configure player (using default configuration macro)
audio_prompt_config_t prompt_cfg = DEFAULT_AUDIO_PROMPT_CONFIG();

audio_prompt_open(&prompt_cfg);
audio_prompt_play("spiffs://audio.mp3");
audio_prompt_close();
```
> Prompt playback is similar to normal playback, but `prompt playback` is blocking playback, suitable for short audio playback. The purpose is to have good responsiveness when you need to play prompt sounds while using normal playback.

6. Focus/fade control (when mixer is enabled):

```c
// Note: Mixer must be opened after both playback and feeder are opened
audio_processor_mixer_open();
audio_processor_ramp_control(AUDIO_MIXER_FOCUS_FEEDER);     // Focus on feeder audio
audio_processor_ramp_control(AUDIO_MIXER_FOCUS_PLAYBACK);   // Focus on playback audio
audio_processor_mixer_close();
```

### 2. Video Usage

1. Render (decode) callback:

```c
void decoded_cb(void *ctx, const uint8_t *data, size_t size) {
    // Handle decoded frame data
}

video_render_config_t rcfg = {
    .decode_cfg = your_vdec_cfg,
    .resolution = {.width = 640, .height = 480},
    .decode_cb = decoded_cb,
};
video_render_handle_t r = video_render_open(&rcfg);
video_render_start(r);

video_frame_t f = {.data = enc_frame, .size = enc_size};
video_render_frame_feed(r, &f);

video_render_stop(r);
video_render_close(r);
```

2. Capture (multi-channel):

```c
void capture_cb(void *ctx, int index, video_frame_t *frame) {
    // Handle captured video frame
}

video_capture_config_t ccfg = {0};
ccfg.camera_config = &your_cam_cfg;
ccfg.sink_num = 2;
ccfg.sink_cfg[0] = your_sink0_cfg;
ccfg.sink_cfg[1] = your_sink1_cfg;
ccfg.capture_frame_cb = capture_cb;

video_capture_handle_t c = video_capture_open(&ccfg);
video_capture_start(c);
video_capture_stop(c);
video_capture_close(c);
```

---

## Media Dump 💾

- Enable condition ✅: Takes effect after enabling `MEDIA_DUMP_ENABLE` in `menuconfig`.
- Save methods 📤: Supports SD card and UDP outputs (choose one).
  - SD card 💾: Enable `CONFIG_MEDIA_DUMP_SINK_SDCARD`, output to file `CONFIG_MEDIA_DUMP_SDCARD_FILENAME`, duration controlled by `CONFIG_MEDIA_DUMP_DURATION_SEC`.
  - UDP 📡: Enable `CONFIG_MEDIA_DUMP_SINK_UDP`, send raw media data via `CONFIG_MEDIA_DUMP_UDP_IP` and `CONFIG_MEDIA_DUMP_UDP_PORT` (can use `script/udp_reciver.py` script).
- Save point 🎚️ (before/after AEC processing): Select in "Audio Save Mode (AEC point)" in `menuconfig`
  - `MEDIA_DUMP_AUDIO_BEFORE_AEC` (Save Before AEC): Save raw microphone audio before AEC (for analyzing noise/feedback)
  - `MEDIA_DUMP_AUDIO_AFTER_AEC` (Save After AEC): Save audio after AEC processing (for evaluating AEC effectiveness)
- Typical usage 🔍: Export raw audio/video data when reproducing issues, check saturation, feedback, and format correctness offline using tools like Audacity.

## Configuration ⚙️

### Runtime Configuration (Recommended)

AFE configuration can be set at runtime via the `afe_config` field in the `audio_recorder_config_t` structure, which takes priority over Kconfig configuration:

```c
audio_recorder_config_t recorder_cfg = DEFAULT_AUDIO_RECORDER_CONFIG();
// Configure AFE
recorder_cfg.afe_config.ai_mode_wakeup = false;        // AI mode: true=wakeup mode, false=direct mode
recorder_cfg.afe_config.vad_enable = true;              // Enable VAD
recorder_cfg.afe_config.vad_mode = 4;                   // VAD mode (1-4), larger values are more sensitive
recorder_cfg.afe_config.vad_min_speech_ms = 64;        // Minimum speech duration (ms)
recorder_cfg.afe_config.vad_min_noise_ms = 1000;       // Minimum noise duration (ms)
recorder_cfg.afe_config.agc_enable = true;              // Enable AGC
recorder_cfg.afe_config.enable_vcmd_detect = false;     // Enable VCMD
recorder_cfg.afe_config.vcmd_timeout_ms = 5000;         // VCMD timeout (ms)
recorder_cfg.afe_config.mn_language = "cn";             // Model language: "cn" or "en"
recorder_cfg.afe_config.wakeup_time_ms = 10000;         // Wakeup time (ms)
recorder_cfg.afe_config.wakeup_end_time_ms = 2000;      // Wakeup end time (ms)

// Pass configuration when opening recorder
audio_recorder_open(&recorder_cfg);
```

### Kconfig Configuration (Alternative)

If fields in `audio_recorder_config_t.afe_config` use default values or are not set, Kconfig configuration will be used. Configure via `idf.py menuconfig`:

#### 💾 Media Dump Configuration

Configure under **"Component config" -> "Audio/Video Processor Configuration" -> "Media Dump"** in `menuconfig`:

- **`MEDIA_DUMP_ENABLE`**: Enable media data dump functionality, disabled by default
  - When enabled, raw audio/video data can be saved for debugging and analysis

- **`MEDIA_DUMP_AUDIO_POINT`**: Audio save point selection (choice type)
  - **`MEDIA_DUMP_AUDIO_BEFORE_AEC`**: Save raw audio before AEC processing
    - Useful for analyzing noise and feedback issues
  - **`MEDIA_DUMP_AUDIO_AFTER_AEC`**: Save audio after AEC processing
    - Useful for evaluating AEC processing effectiveness
  - **`MEDIA_DUMP_AUDIO_NONE`**: Do not save audio (default)

- **`MEDIA_DUMP_DURATION_SEC`**: Save duration in seconds, default 20
  - Type: integer (int)
  - Range: 1-3600 seconds

- **`MEDIA_DUMP_SINK`**: Save method selection (choice type)
  - **`MEDIA_DUMP_SINK_SDCARD`**: Save to SD card file (default)
    - File path configuration: `CONFIG_MEDIA_DUMP_SDCARD_FILENAME` (default: `/sdcard/media_dump.bin`)
    - Ensure SD card is properly mounted
  - **`MEDIA_DUMP_SINK_UDP`**: Send via UDP
    - Target IP configuration: `CONFIG_MEDIA_DUMP_UDP_IP` (default: `192.168.1.100`)
    - Target port configuration: `CONFIG_MEDIA_DUMP_UDP_PORT` (default: 5000)
    - Can use `script/udp_reciver.py` script to receive data

### Task Configuration

The audio processing component uses multiple FreeRTOS tasks internally, which can be customized via task configuration fields in each module's configuration structure:

#### Task Configuration for Each Module

- **Recorder** (`audio_recorder_config_t`):
  - `afe_feed_task_config`: AFE feed task configuration (default stack size 3KB)
  - `afe_fetch_task_config`: AFE fetch task configuration (default stack size 3KB)
  - `recorder_task_config`: Recorder task configuration (default stack size 5KB, recommend >= 40KB when using OPUS encoder)

- **Player** (`audio_playback_config_t`):
  - `playback_task_config`: Playback task configuration (default stack size 4KB)

- **Feeder** (`audio_feeder_config_t`):
  - `feeder_task_config`: Feeder task configuration (default stack size 5KB, recommend >= 40KB when using OPUS decoder)

**Important Notes**:
- When using OPUS encoder or decoder, `task_stack` of `recorder_task_config` and `feeder_task_config` should be set to at least `4096 * 10` bytes (40KB).
- When `task_stack` in task configuration is set to 0, default values will be used.
- When `task_stack_in_ext` is set to `true`, task stack will be allocated in external memory, helping to save internal RAM.
- Task configuration should be set in each module's configuration structure (e.g., `audio_recorder_config_t`, `audio_playback_config_t`, `audio_feeder_config_t`), not in `audio_manager_config_t`.

---

## API Reference 📚

Header files:

- `include/audio_processor.h`
- `include/video_processor.h`
- `include/av_processor_type.h`

Common functions (selection):

- Audio management:
  - `audio_manager_init`/`audio_manager_deinit`: Initialize/deinitialize audio manager
- Recording:
  - `audio_recorder_open`: Open recorder (supports encoder configuration and event callback)
  - `audio_recorder_read_data`: Read recording data
  - `audio_recorder_get_afe_manager_handle`: Get AFE manager handle
  - `audio_recorder_close`: Close recorder
- Feeder:
  - `audio_feeder_open`: Open feeder (supports decoder configuration)
  - `audio_feeder_run`: Start feeder
  - `audio_feeder_feed_data`: Feed audio data
  - `audio_feeder_stop`: Stop feeder
  - `audio_feeder_close`: Close feeder
- Playback:
  - `audio_playback_open`/`audio_playback_close`: Open/close player
  - `audio_playback_play`: Play audio (supports URL or local file, e.g., `http://...` or `file:///sdcard/...`)
  - `audio_playback_stop`: Stop playback
  - `audio_playback_pause`/`audio_playback_resume`: Pause/resume playback
  - `audio_playback_get_state`: Get playback state
- Mixer:
  - `audio_processor_mixer_open`: Open mixer (must be called after both playback and feeder are opened)
  - `audio_processor_mixer_close`: Close mixer
  - `audio_processor_ramp_control`: Control audio focus and volume fade
- Video rendering:
  - `video_render_open`/`video_render_close`: Open/close video renderer
  - `video_render_start`/`video_render_stop`: Start/stop rendering
  - `video_render_frame_feed`: Feed video frame
- Video capture:
  - `video_capture_open`/`video_capture_close`: Open/close video capturer
  - `video_capture_start`/`video_capture_stop`: Start/stop capture

---

## FAQ ❓

### Audio Issues

- **"Self-questioning" phenomenon occurs (device playback sound is repeatedly captured by microphone)**:
  - Enable `MEDIA_DUMP_ENABLE` in `menuconfig`, reproduce the issue and export saved audio data for further analysis
  - Open the exported audio file using [Audacity](https://www.audacityteam.org/download/), observe waveform/spectrum to determine if saturation or feedback exists
  - If saturation clipping occurs, reduce microphone gain (`esp_codec_dev_set_in_gain`); or appropriately reduce speaker volume (`esp_codec_dev_set_out_vol`) to avoid excessive feedback

- **Stack overflow when using OPUS encoder/decoder**:
  - Ensure `task_stack` of `recorder_task_config` and `feeder_task_config` is set to at least `4096 * 10` bytes (40KB)
  - Consider allocating task stack in external memory (set `task_stack_in_ext = true`)

- **Mixer not working properly**:
  - Ensure that both player (`audio_playback_open`) and feeder (`audio_feeder_open`) are opened before calling `audio_processor_mixer_open()`
  - Ensure `enable_mixer = true` is set when calling `audio_manager_init`

### Development and Debugging

- **Media data dump (Media Dump)**:
  - UDP method: Can use `script/media_dump_server.py` script to receive data
  - SD card method: Ensure SD card is properly mounted and file path is accessible

---

## Version Information

Current version: v0.1.0

## License

This component follows the MIT license. See the `LICENSE` file included in the repository for details.

## Related Resources

- Project repository: https://github.com/espressif/esp-gmf/tree/main/components/av_processor
- Issue reporting: https://github.com/espressif/esp-gmf/issues
- Documentation: https://github.com/espressif/esp-gmf/blob/main/components/av_processor/README.md
