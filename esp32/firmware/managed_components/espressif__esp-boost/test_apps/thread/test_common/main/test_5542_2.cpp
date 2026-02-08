// Copyright (C) 2010 Vicente Botet
//
//  Distributed under the Boost Software License, Version 1.0. (See accompanying
//  file LICENSE_1_0.txt or copy at http://www.boost.org/LICENSE_1_0.txt)

#define BOOST_THREAD_VERSION 2

#include <boost/thread/thread_only.hpp>

void run_thread() {
        return;
}

static int test_main() {
        boost::thread t(&run_thread);
        /* esp32: wait for thread to finish to avoid memory leak */
        t.join();
        return 0;
}

#include "common.hpp"

BOOST_AUTO_TEST_CASE(test_5542_2)
{
        common_init();
    std::thread([&]() {
        TEST_ASSERT(test_main() == 0);
    }).join();
}
