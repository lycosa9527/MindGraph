/*
 * SPDX-FileCopyrightText: 2025 Espressif Systems (Shanghai) CO., LTD
 * SPDX-License-Identifier: LicenseRef-Espressif-Modified-MIT
 *
 * See LICENSE file for details.
 */

#include "esp_gmf_err.h"
#include "esp_gmf_pool.h"
#include "esp_gmf_copier.h"

static const char *TAG = "GMF_SETUP_MISC";

#ifdef CONFIG_GMF_MISC_INIT_COPIER
static esp_gmf_err_t gmf_loader_setup_default_copier(esp_gmf_pool_handle_t pool)
{
    ESP_GMF_NULL_CHECK(TAG, pool, return ESP_GMF_ERR_INVALID_ARG);

    esp_gmf_err_t ret = ESP_GMF_ERR_OK;
    esp_gmf_obj_handle_t hd = NULL;
    esp_gmf_copier_cfg_t copier_cfg = {
        .copy_num = 1,  // Default copy number
    };
    ret = esp_gmf_copier_init(&copier_cfg, &hd);
    ESP_GMF_RET_ON_ERROR(TAG, ret, return ret, "Failed to init copier");
    ret = esp_gmf_pool_register_element(pool, hd, NULL);
    ESP_GMF_RET_ON_ERROR(TAG, ret, {esp_gmf_element_deinit(hd); return ret;}, "Failed to register copier");
    return ret;
}
#endif  /* CONFIG_GMF_MISC_INIT_COPIER */

esp_gmf_err_t gmf_loader_setup_misc_default(esp_gmf_pool_handle_t pool)
{
    ESP_GMF_NULL_CHECK(TAG, pool, return ESP_GMF_ERR_INVALID_ARG);
    esp_gmf_err_t ret = ESP_GMF_ERR_OK;

#ifdef CONFIG_GMF_MISC_INIT_COPIER
    ret = gmf_loader_setup_default_copier(pool);
    ESP_GMF_RET_ON_ERROR(TAG, ret, return ret, "Failed to register copier");
#endif  /* CONFIG_GMF_MISC_INIT_COPIER */

    return ret;
}

esp_gmf_err_t gmf_loader_teardown_misc_default(esp_gmf_pool_handle_t pool)
{
    ESP_GMF_NULL_CHECK(TAG, pool, return ESP_GMF_ERR_INVALID_ARG);
    return ESP_GMF_ERR_OK;
}
