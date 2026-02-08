#include "audio_handler.h"
#include "../components/es7210/es7210_driver.h"
#include "../components/es8311/es8311_driver.h"
#include "echo_cancellation.h"
#include "esp_log.h"

static const char* TAG = "AUDIO";

static bool audio_initialized = false;
static bool capturing = false;
static bool playing = false;
static int16_t capture_buffer[AUDIO_BUFFER_SIZE];
static int16_t mic1_buffer[AUDIO_BUFFER_SIZE];
static int16_t mic2_buffer[AUDIO_BUFFER_SIZE];
static int16_t echo_cancelled_buffer[AUDIO_BUFFER_SIZE];
static int16_t playback_buffer[AUDIO_BUFFER_SIZE];
static size_t capture_samples = 0;
static size_t playback_samples = 0;
static size_t playback_position = 0;

bool audio_init() {
    if (audio_initialized) {
        return true;
    }
    
    ESP_LOGI(TAG, "Initializing...");
    
    if (!es7210_init()) {
        ESP_LOGE(TAG, "Failed to initialize ES7210");
        return false;
    }
    
    if (!es8311_init()) {
        ESP_LOGE(TAG, "Failed to initialize ES8311");
        return false;
    }
    
    es7210_set_sample_rate(AUDIO_SAMPLE_RATE);
    es8311_set_sample_rate(AUDIO_SAMPLE_RATE);
    
    es7210_set_gain(0, 24);
    es7210_set_gain(1, 24);
    
    echo_cancellation_init();
    
    audio_initialized = true;
    ESP_LOGI(TAG, "Initialized");
    return true;
}

void audio_start_capture() {
    if (!audio_initialized) {
        if (!audio_init()) {
            return;
        }
    }
    
    if (!capturing) {
        ESP_LOGI(TAG, "Starting capture");
        if (es7210_start()) {
            capturing = true;
            capture_samples = 0;
        } else {
            ESP_LOGE(TAG, "Failed to start ES7210");
        }
    }
}

void audio_stop_capture() {
    if (capturing) {
        ESP_LOGI(TAG, "Stopping capture");
        es7210_stop();
        capturing = false;
        capture_samples = 0;
    }
}

void audio_start_playback() {
    if (!audio_initialized) {
        if (!audio_init()) {
            return;
        }
    }
    
    if (!playing) {
        ESP_LOGI(TAG, "Starting playback");
        if (es8311_start()) {
            playing = true;
            playback_samples = 0;
            playback_position = 0;
        } else {
            ESP_LOGE(TAG, "Failed to start ES8311");
        }
    }
}

void audio_stop_playback() {
    if (playing) {
        ESP_LOGI(TAG, "Stopping playback");
        es8311_stop();
        playing = false;
        playback_samples = 0;
        playback_position = 0;
    }
}

bool audio_is_capturing() {
    return capturing;
}

bool audio_is_playing() {
    return playing;
}

void audio_process() {
    if (!audio_initialized) {
        return;
    }
    
    if (capturing) {
        size_t samples_to_read = AUDIO_BUFFER_SIZE;
        if (es7210_read_pdm(mic1_buffer, mic2_buffer, samples_to_read)) {
            int16_t* speaker_out = playback_buffer;
            
            echo_cancellation_process(
                mic1_buffer,
                mic2_buffer,
                speaker_out,
                echo_cancelled_buffer,
                samples_to_read
            );
            
            for (size_t i = 0; i < samples_to_read; i++) {
                capture_buffer[i] = echo_cancelled_buffer[i];
            }
            
            capture_samples = samples_to_read;
        }
    }
    
    if (playing && playback_samples > 0 && playback_position < playback_samples) {
        size_t samples_to_write = playback_samples - playback_position;
        if (samples_to_write > AUDIO_BUFFER_SIZE) {
            samples_to_write = AUDIO_BUFFER_SIZE;
        }
        
        if (es8311_write_audio(&playback_buffer[playback_position], samples_to_write)) {
            playback_position += samples_to_write;
            if (playback_position >= playback_samples) {
                playback_samples = 0;
                playback_position = 0;
            }
        }
    }
}

int16_t* audio_get_capture_buffer(size_t* samples) {
    if (!capturing) {
        *samples = 0;
        return nullptr;
    }
    
    *samples = capture_samples;
    return capture_buffer;
}

void audio_play_buffer(int16_t* data, size_t samples) {
    if (!playing || data == nullptr || samples == 0) {
        return;
    }
    
    size_t samples_to_copy = samples;
    if (samples_to_copy > AUDIO_BUFFER_SIZE) {
        samples_to_copy = AUDIO_BUFFER_SIZE;
    }
    
    for (size_t i = 0; i < samples_to_copy; i++) {
        playback_buffer[i] = data[i];
    }
    
    playback_samples = samples_to_copy;
    playback_position = 0;
}