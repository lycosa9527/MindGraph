/*
 * SPDX-FileCopyrightText: 2025 Espressif Systems (Shanghai) CO., LTD
 * SPDX-License-Identifier: LicenseRef-Espressif-Modified-MIT
 *
 * See LICENSE file for details.
 */
#ifndef _GZIP_MINIZ_H_
#define _GZIP_MINIZ_H_

#ifdef __cplusplus
extern "C" {
#endif

/**
 * @brief Configuration for gzip using miniz library
 */
typedef struct {
    int   (*read_cb)(uint8_t *data, int size, void *ctx);  /*!< Read callback return size being read */
    int   chunk_size;                                      /*!< Chunk size default 32 if set to 0 */
    void  *ctx;                                            /*!< Read context */
} gzip_miniz_cfg_t;

/**
 * @brief Handle for gzip
 */
typedef void *gzip_miniz_handle_t;

/**
 * @brief         Initialize for gzip using miniz
 * @param         cfg: Configuration for gzip using miniz
 * @return        NULL: Input parameter wrong or no memory
 *                Others: Handle for gzip inflate operation
 */
gzip_miniz_handle_t gzip_miniz_init(gzip_miniz_cfg_t *cfg);

/**
 * @brief         Inflate and read data
 * @param         out: Data to read after inflated
 * @param         out_size: Data size to read
 * @return        >= 0: Data size being read
 *                -1: Wrong input parameter or wrong data
 *                -2: Inflate error by miniz
 */
int gzip_miniz_read(gzip_miniz_handle_t zip, uint8_t *out, int out_size);

/**
 * @brief         Deinitialize gzip using miniz
 * @param         zip: Handle for gzip
 * @return        0: On success
 *                -1: Input parameter wrong
 */
int gzip_miniz_deinit(gzip_miniz_handle_t zip);

/**
 * @brief         Zip data into gzip format
 * @param         in: Data to be zipped
 * @param         in_size: Data size to be zipped
 * @param         in_size: Data size to be zipped
 * @param         out: Store output gzip format data
 * @param         out_size: Zipped data size
 * @return        >= 0: On success
 *                -1: Fail to init gzip deflate
 *                -2: Fail to deflate
 */
int gzip_miniz_zip(const uint8_t* in, size_t in_size, uint8_t *out, int out_size);

#ifdef __cplusplus
}
#endif

#endif
