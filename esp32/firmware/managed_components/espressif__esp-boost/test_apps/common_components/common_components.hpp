#pragma once

#include <sstream>
#include <memory>
#include <unordered_map>
#include <string>
#include "freertos/FreeRTOS.h"
#include "freertos/task.h"
#include "unity.h"
#include "unity_test_runner.h"

#ifndef BOOST_CHECK
#define BOOST_CHECK(x) TEST_ASSERT(x)
#endif

#ifndef BOOST_CHECK_EQUAL
#define BOOST_CHECK_EQUAL(x, y) TEST_ASSERT_EQUAL(x, y)
#endif

#ifndef BOOST_REQUIRE
#define BOOST_REQUIRE(x) TEST_ASSERT(x)
#endif

void common_set_pthread_config(const char *name, int core_id, int stack, int prio, bool use_psram = false, bool inherit_cfg = false);
void common_reset_pthread_config();
void common_set_memory_leak_threshold(size_t threshold);
size_t common_get_memory_leak_threshold();

struct EmbeddedFile {
    const uint8_t* start;
    const uint8_t* end;
};
std::unique_ptr<std::istream> open_input_stream(const std::unordered_map<std::string, EmbeddedFile>& embedded_files, const char* path);
