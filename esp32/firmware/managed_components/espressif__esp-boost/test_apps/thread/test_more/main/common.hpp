#pragma once

#include <thread>
#include "boost/thread.hpp"
#include "common_components.hpp"

#undef BOOST_AUTO_TEST_CASE
#define BOOST_AUTO_TEST_CASE(type, name) TEST_CASE("thread : " #type " : " #name, "[thread][test_more][" #type "][" #name "]")

extern unsigned throw_one;

void common_init();
