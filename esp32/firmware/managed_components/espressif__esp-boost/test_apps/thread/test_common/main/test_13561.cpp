// Copyright (C) 2018 Vicente Botet
//
//  Distributed under the Boost Software License, Version 1.0. (See accompanying
//  file LICENSE_1_0.txt or copy at http://www.boost.org/LICENSE_1_0.txt)

#define BOOST_THREAD_VERSION 4

#include <boost/thread/detail/nullary_function.hpp>
// #include <boost/system/detail/error_code.ipp>

static int test_main(int argc, char* argv[])
{
    boost::detail::nullary_function<void ()> f1;
    auto f2 = f1;

    return 0;
}

#include "common.hpp"

BOOST_AUTO_TEST_CASE(test_13561)
{
      common_init();
    std::thread([]() {
        TEST_ASSERT(test_main(0, nullptr) == 0);
    }).join();
}

