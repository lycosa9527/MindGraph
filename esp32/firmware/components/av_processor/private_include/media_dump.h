/*
 * SPDX-FileCopyrightText: 2025 Espressif Systems (Shanghai) CO., LTD
 * SPDX-License-Identifier: LicenseRef-Espressif-Modified-MIT
 *
 * See LICENSE file for details.
 */

#pragma once

#ifdef __cplusplus
extern "C" {
#endif  /* __cplusplus */

#include <stddef.h>
#include <stdint.h>

/**
 * @brief  Open a media dump session
 *
 *         When enabled by Kconfig, subsequent writes are dumped to the selected sink.
 *         If a session is already open, it will be closed and a new one started.
 *         The session duration is limited by `CONFIG_MEDIA_DUMP_DURATION_SEC`; after
 *         the timeout is reached, additional writes are not accepted.
 *
 * - SDCARD: write to `CONFIG_MEDIA_DUMP_SDCARD_FILENAME`
 * - UDP: send to `CONFIG_MEDIA_DUMP_UDP_ADDRESS` (format: IP:Port, e.g., "192.168.1.100:5000")
 *
 * @param[in]  filename  Optional filename for the dump file
 * @return
 *       - 0   Session opened successfully
 *       - -1  Failed to open (e.g., file/socket creation failure)
 */
int media_dump_open(const char *filename);

/**
 * @brief  Write media data to the dump sink
 *
 *         Effective only when a session is open and not expired.
 *
 * @param[in]  data  Pointer to the data buffer to write
 * @param[in]  size  Number of bytes in the buffer
 * @return
 *       - >0  Bytes actually written/sent (depends on sink)
 *       - 0   Maximum duration reached, this write is ignored
 *       - -1  Session not open, already expired, or parameters invalid
 */
int media_dump_write(const uint8_t *data, size_t size);

/**
 * @brief  Close the current media dump session and release resources
 *
 *         Calling multiple times is safe; if no session is open, it returns immediately.
 *
 * @return
 *       - 0  Always returns 0
 */
int media_dump_close(void);

/**
 * @brief  Feed data with auto open/close behavior
 *
 *         If no session is open, media_dump_open() is called automatically. After the
 *         write, if the session duration has been reached, the session is closed
 *         automatically. If the session is already expired, this function returns 0.
 *
 *         If want to call this function， can use `extern int media_dump_feed(const char *filename, const uint8_t *data, size_t size);` in the file.
 *
 * @param[in]  filename  Optional filename for the dump file
 * @param[in]  data      Pointer to the data buffer to write
 * @param[in]  size      Number of bytes in the buffer
 * @return
 *       - Same  return semantics as media_dump_write()
 *       - -1    Auto open failed
 */
int media_dump_feed(const char *filename, const uint8_t *data, size_t size);

#ifdef __cplusplus
}
#endif  /* __cplusplus */
