/*
 * SPDX-FileCopyrightText: 2025 Espressif Systems (Shanghai) CO., LTD
 * SPDX-License-Identifier: LicenseRef-Espressif-Modified-MIT
 *
 * See LICENSE file for details.
 */

#include <stdio.h>
#include <string.h>
#include <stdbool.h>
#include <stdint.h>
#include <stddef.h>
#include <errno.h>
#include <sys/types.h>
#include <unistd.h>

#include "esp_log.h"
#include "esp_timer.h"
#include "sdkconfig.h"

#include "media_dump.h"

#if CONFIG_MEDIA_DUMP_SINK_UDP
#include "lwip/inet.h"
#include "lwip/sockets.h"
#endif  /* CONFIG_MEDIA_DUMP_SINK_UDP */

#if CONFIG_MEDIA_DUMP_ENABLE

static const char *TAG = "MEDIA_DUMP";

typedef struct {
    bool    opened;
    int64_t start_time_us;
    int64_t max_duration_us;
    bool    expired;
    bool    notified;
#if CONFIG_MEDIA_DUMP_SINK_SDCARD
    FILE *fp;
#endif  /* CONFIG_MEDIA_DUMP_SINK_SDCARD */
#if CONFIG_MEDIA_DUMP_SINK_UDP
    int                sock;
    struct sockaddr_in dest;
#endif  /* CONFIG_MEDIA_DUMP_SINK_UDP */
} media_dump_ctx_t;

static media_dump_ctx_t s_ctx = {0};

static inline bool media_dump_time_exceeded(void)
{
    media_dump_ctx_t *ctx = &s_ctx;
    if (!ctx->opened) {
        return false;
    }
    int64_t now = esp_timer_get_time();
    if ((now - ctx->start_time_us) >= ctx->max_duration_us) {
        ctx->expired = true;
        if (!ctx->notified) {
            ESP_LOGI(TAG, "Dump duration reached (%ds)", (int)CONFIG_MEDIA_DUMP_DURATION_SEC);
            ctx->notified = true;
        }
        return true;
    }
    return false;
}

static void media_dump_release(media_dump_ctx_t *ctx)
{
#if CONFIG_MEDIA_DUMP_SINK_SDCARD
    if (ctx->fp) {
        fflush(ctx->fp);
        fclose(ctx->fp);
        ctx->fp = NULL;
    }
#endif  /* CONFIG_MEDIA_DUMP_SINK_SDCARD */
#if CONFIG_MEDIA_DUMP_SINK_UDP
    if (ctx->sock >= 0) {
        close(ctx->sock);
        ctx->sock = -1;
    }
#endif  /* CONFIG_MEDIA_DUMP_SINK_UDP */
    ctx->opened = false;
}

int media_dump_open(const char *filename)
{
    media_dump_ctx_t *ctx = &s_ctx;
    /* allow re-open anytime: close existing and start a new session */
    if (ctx->opened) {
        media_dump_release(ctx);
    }
    /* reset state and start fresh */
    memset(ctx, 0, sizeof(*ctx));
    ctx->max_duration_us = (int64_t)CONFIG_MEDIA_DUMP_DURATION_SEC * 1000000LL;
    ctx->start_time_us = esp_timer_get_time();

#if CONFIG_MEDIA_DUMP_SINK_SDCARD
    const char *path = NULL;
    if (filename) {
        path = filename;
    } else {
        path = CONFIG_MEDIA_DUMP_SDCARD_FILENAME;
    }
    ctx->fp = fopen(path, "wb");
    if (!ctx->fp) {
        ESP_LOGE(TAG, "Dump open file failed: %s, error: %s", path, strerror(errno));
        return -1;
    }
    ESP_LOGI(TAG, "Dump file: %s, %ds", path, CONFIG_MEDIA_DUMP_DURATION_SEC);
#endif  /* CONFIG_MEDIA_DUMP_SINK_SDCARD */

#if CONFIG_MEDIA_DUMP_SINK_UDP
    ctx->sock = socket(AF_INET, SOCK_DGRAM, IPPROTO_IP);
    if (ctx->sock < 0) {
        ESP_LOGE(TAG, "Dump create UDP socket failed");
        return -1;
    }
    memset(&ctx->dest, 0, sizeof(ctx->dest));
    ctx->dest.sin_family = AF_INET;
    ctx->dest.sin_port = htons(CONFIG_MEDIA_DUMP_UDP_PORT);
    ctx->dest.sin_addr.s_addr = inet_addr(CONFIG_MEDIA_DUMP_UDP_IP);
    ESP_LOGI(TAG, "Dump UDP %s:%d, %ds", CONFIG_MEDIA_DUMP_UDP_IP,
             CONFIG_MEDIA_DUMP_UDP_PORT, CONFIG_MEDIA_DUMP_DURATION_SEC);
#endif  /* CONFIG_MEDIA_DUMP_SINK_UDP */

    ctx->opened = true;
    return 0;
}

int media_dump_write(const uint8_t *data, size_t size)
{
    media_dump_ctx_t *ctx = &s_ctx;
    if (!ctx->opened || ctx->expired || !data || size == 0) {
        return -1;
    }
    if (media_dump_time_exceeded()) {
        ESP_LOGW(TAG, "Dump duration reached, ignore write");
        return 0;
    }

#if CONFIG_MEDIA_DUMP_SINK_SDCARD
    if (ctx->fp) {
        size_t w = fwrite(data, 1, size, ctx->fp);
        if (w != size) {
            ESP_LOGW(TAG, "Dump short file write: %u/%u", (unsigned)w, (unsigned)size);
        }
        return (int)w;
    }
#endif  /* CONFIG_MEDIA_DUMP_SINK_SDCARD */

#if CONFIG_MEDIA_DUMP_SINK_UDP
    if (ctx->sock >= 0) {
        int sent = sendto(ctx->sock, data, size, 0, (struct sockaddr *)&ctx->dest, sizeof(ctx->dest));
        if (sent < 0) {
            ESP_LOGW(TAG, "Dump UDP send failed");
            return -1;
        }
        return sent;
    }
#endif  /* CONFIG_MEDIA_DUMP_SINK_UDP */
    return -1;
}

int media_dump_close(void)
{
    media_dump_ctx_t *ctx = &s_ctx;
    if (!ctx->opened) {
        return 0;
    }
    /* normal close: always release immediately */
    media_dump_release(ctx);
    return 0;
}

int media_dump_feed(const char *filename, const uint8_t *data, size_t size)
{
    media_dump_ctx_t *ctx = &s_ctx;
    /* feed mode: maintain a single open session across calls */
    if (ctx->expired) {
        return 0;
    }
    if (!ctx->opened) {
        if (media_dump_open(filename) != 0) {
            return -1;
        }
    }
    ESP_LOGI(TAG, "Dump duration not reached, write now");
    int ret = media_dump_write(data, size);
    /* If duration reached during this write, close now */
    if (ctx->expired && ctx->opened) {
        (void)media_dump_close();
        ESP_LOGI(TAG, "Dump duration reached, close now");
    }
    return ret;
}

#else  /* !CONFIG_MEDIA_DUMP_ENABLE */

int media_dump_open(const char *filename)
{
    return 0;
}

int media_dump_write(const uint8_t *data, size_t size)
{
    (void)data;
    (void)size;
    return 0;
}

int media_dump_close(void)
{
    return 0;
}

int media_dump_feed(const char *filename, const uint8_t *data, size_t size)
{
    (void)filename;
    (void)data;
    (void)size;
    return 0;
}

#endif  /* CONFIG_MEDIA_DUMP_ENABLE */
