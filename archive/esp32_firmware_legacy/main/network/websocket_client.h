#ifndef WEBSOCKET_CLIENT_H
#define WEBSOCKET_CLIENT_H

#include <stdint.h>
#include <stdbool.h>
#include <stddef.h>

struct cJSON;

#define WS_RECONNECT_INTERVAL 5000
#define WS_HEARTBEAT_INTERVAL 30000

enum WatchState {
    WATCH_STATE_DISCONNECTED,
    WATCH_STATE_CONNECTING,
    WATCH_STATE_CONNECTED,
    WATCH_STATE_AUTHENTICATING,
    WATCH_STATE_READY,
    WATCH_STATE_LEARNING_MODE
};

typedef void (*OnMessageCallback)(cJSON* doc);
typedef void (*OnStateChangeCallback)(WatchState state);

bool websocket_init();
void websocket_set_callbacks(OnMessageCallback on_msg, OnStateChangeCallback on_state);
bool websocket_connect(const char* server_url, const char* watch_id, const char* auth_token);
void websocket_disconnect();
void websocket_handle();
bool websocket_is_connected();
WatchState websocket_get_state();
bool websocket_send_json(cJSON* doc);
bool websocket_send_audio(const uint8_t* data, size_t len);

#endif
