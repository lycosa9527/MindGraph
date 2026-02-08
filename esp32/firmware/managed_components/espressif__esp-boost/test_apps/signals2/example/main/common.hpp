#pragma once

#include <thread>
#include "boost/thread.hpp"
#include "common_components.hpp"

#undef BOOST_AUTO_TEST_CASE
#define BOOST_AUTO_TEST_CASE(name) TEST_CASE("signals2 : example : " #name, "[signals2][example][" #name "]")

void common_init();
