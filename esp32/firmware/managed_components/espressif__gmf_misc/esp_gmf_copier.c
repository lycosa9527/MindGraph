/*
 * SPDX-FileCopyrightText: 2025 Espressif Systems (Shanghai) CO., LTD
 * SPDX-License-Identifier: LicenseRef-Espressif-Modified-MIT
 *
 * See LICENSE file for details.
 */

#include <string.h>
#include "esp_log.h"
#include "esp_gmf_oal_mem.h"
#include "esp_gmf_element.h"
#include "esp_gmf_err.h"
#include "esp_gmf_copier.h"

/**
 * @brief Copier context in GMF
 */
typedef struct esp_gmf_copier {
    struct esp_gmf_element parent;  /*!< The GMF copier handle */
} esp_gmf_copier_t;

static const char *TAG = "ESP_GMF_COPIER";

static esp_gmf_err_t esp_gmf_copier_new(void *cfg, esp_gmf_obj_handle_t *handle)
{
    return esp_gmf_copier_init(cfg, handle);
}

static esp_gmf_job_err_t esp_gmf_copier_open(esp_gmf_element_handle_t self, void *para)
{
    ESP_LOGD(TAG, "%s", __func__);
    return ESP_GMF_ERR_OK;
}

static esp_gmf_job_err_t esp_gmf_copier_process(esp_gmf_element_handle_t self, void *para)
{
    esp_gmf_element_handle_t hd = (esp_gmf_element_handle_t)self;
    esp_gmf_port_t *in = ESP_GMF_ELEMENT_GET(hd)->in;
    esp_gmf_port_t *out = ESP_GMF_ELEMENT_GET(hd)->out;
    esp_gmf_payload_t *in_load = NULL;
    esp_gmf_payload_t *out_load = NULL;
    esp_gmf_err_io_t out_len = ESP_GMF_IO_OK;
    int idx = 0;
    esp_gmf_err_io_t load_ret = esp_gmf_port_acquire_in(in, &in_load, in->data_length, ESP_GMF_MAX_DELAY);
    ESP_GMF_PORT_ACQUIRE_IN_CHECK(TAG, load_ret, out_len, { goto __copy_release;});
    int out_data_length = in_load->valid_size > 0 ? in_load->valid_size : in_load->buf_length;
    while (out) {
        out_load = NULL;
        if (out != ESP_GMF_ELEMENT_GET(hd)->out) {
            load_ret = esp_gmf_port_acquire_out(out, &out_load, out_data_length, 0);
            ESP_GMF_PORT_ACQUIRE_OUT_CHECK(TAG, load_ret, out_len, { goto __copy_release;});
            esp_gmf_payload_copy_data(in_load, out_load);
        } else {
            out_load = in_load;
            load_ret = esp_gmf_port_acquire_out(out, &out_load, out_data_length, 0);
            ESP_GMF_PORT_ACQUIRE_OUT_CHECK(TAG, load_ret, out_len, { goto __copy_release;});
            out_load->is_done = in_load->is_done;
            out_load->valid_size = in_load->valid_size;
        }
        load_ret = esp_gmf_port_release_out(out, out_load, out->wait_ticks);
        if (load_ret < ESP_GMF_IO_OK) {
            if (load_ret == ESP_GMF_IO_FAIL) {
                ESP_LOGE(TAG, "Failed to release out, idx: %d, ret: %d.", idx, load_ret);
                out_len = load_ret;
                goto __copy_release;
            } else {
                ESP_LOGW(TAG, "Something error on release out, idx: %d, ret: %d.", idx, load_ret);
            }
        }
        ESP_LOGV(TAG, "OUT: %p, rd: %s, I: %p, b: %p, sz: %d, O: %p, b: %p, sz: %d, done: %d, t: %d", out, OBJ_GET_TAG(out->reader),
                 in_load, in_load->buf, in_load->valid_size, out_load,
                 out_load != NULL ? out_load->buf : NULL,
                 out_load != NULL ? out_load->valid_size : -1,
                 out_load != NULL ? out_load->is_done : -1,
                 out->wait_ticks);
        out = out->next;
        idx++;
    }
    out_len = in_load->valid_size;
    if (in_load->is_done) {
        out_len = ESP_GMF_JOB_ERR_DONE;
    }
__copy_release:
    if (in_load != NULL) {
        load_ret = esp_gmf_port_release_in(in, in_load, 0);
        if ((load_ret < ESP_GMF_IO_OK) && (load_ret != ESP_GMF_IO_ABORT)) {
            ESP_LOGE(TAG, "Payload release error, ret:%d, line %d ", load_ret, __LINE__);
            out_len = ESP_GMF_JOB_ERR_FAIL;
        }
    }
    return out_len;
}

static esp_gmf_job_err_t esp_gmf_copier_close(esp_gmf_element_handle_t self, void *para)
{
    ESP_LOGD(TAG, "%s", __func__);
    return ESP_GMF_ERR_OK;
}

static esp_gmf_err_t esp_gmf_copier_destroy(esp_gmf_element_handle_t self)
{
    ESP_LOGD(TAG, "Destroyed");
    void *cfg = OBJ_GET_CFG(self);
    if (cfg) {
        esp_gmf_oal_free(cfg);
    }
    esp_gmf_element_deinit(self);
    esp_gmf_oal_free(self);
    return ESP_GMF_ERR_OK;
}

esp_gmf_err_t esp_gmf_copier_init(esp_gmf_copier_cfg_t *config, esp_gmf_obj_handle_t *handle)
{
    ESP_GMF_NULL_CHECK(TAG, handle, {return ESP_GMF_ERR_INVALID_ARG;});
    *handle = NULL;
    esp_gmf_copier_t *copier = esp_gmf_oal_calloc(1, sizeof(esp_gmf_copier_t));
    ESP_GMF_MEM_VERIFY(TAG, copier, {return ESP_GMF_ERR_MEMORY_LACK;}, "copier", sizeof(esp_gmf_copier_t));
    esp_gmf_obj_t *obj = (esp_gmf_obj_t *)copier;
    obj->new_obj = esp_gmf_copier_new;
    obj->del_obj = esp_gmf_copier_destroy;
    esp_gmf_err_t ret = ESP_GMF_ERR_OK;
    if (config) {
        esp_gmf_copier_cfg_t *cfg = esp_gmf_oal_calloc(1, sizeof(*config));
        ESP_GMF_MEM_VERIFY(TAG, cfg, {ret = ESP_GMF_ERR_MEMORY_LACK; goto _copier_init_fail;}, "copier configuration", sizeof(*config));
        memcpy(cfg, config, sizeof(*config));
        esp_gmf_obj_set_config(obj, cfg, sizeof(*config));
    }
    ret = esp_gmf_obj_set_tag(obj, "copier");
    ESP_GMF_RET_ON_NOT_OK(TAG, ret, goto _copier_init_fail, "Failed set OBJ tag");
    ESP_GMF_ELEMENT_GET(copier)->ops.open = esp_gmf_copier_open;
    ESP_GMF_ELEMENT_GET(copier)->ops.process = esp_gmf_copier_process;
    ESP_GMF_ELEMENT_GET(copier)->ops.close = esp_gmf_copier_close;
    esp_gmf_element_cfg_t el_cfg = {0};
    ESP_GMF_ELEMENT_IN_PORT_ATTR_SET(el_cfg.in_attr, ESP_GMF_EL_PORT_CAP_SINGLE, 0, 0,
                            ESP_GMF_PORT_TYPE_BLOCK | ESP_GMF_PORT_TYPE_BYTE, ESP_GMF_ELEMENT_PORT_DATA_SIZE_DEFAULT);
    ESP_GMF_ELEMENT_OUT_PORT_ATTR_SET(el_cfg.out_attr, ESP_GMF_EL_PORT_CAP_MULTI, 0, 0,
                                ESP_GMF_PORT_TYPE_BLOCK | ESP_GMF_PORT_TYPE_BYTE, ESP_GMF_ELEMENT_PORT_DATA_SIZE_DEFAULT);
    el_cfg.dependency = false;
    ret = esp_gmf_element_init(copier, &el_cfg);
    ESP_GMF_RET_ON_NOT_OK(TAG, ret, goto _copier_init_fail, "Failed init copier");
    *handle = obj;
    return ESP_GMF_ERR_OK;
_copier_init_fail:
    esp_gmf_obj_delete(obj);
    return ret;
}
