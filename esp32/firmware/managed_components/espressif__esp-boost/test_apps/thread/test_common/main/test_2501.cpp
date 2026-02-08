// Copyright (C) 2010 Vicente Botet
//
//  Distributed under the Boost Software License, Version 1.0. (See accompanying
//  file LICENSE_1_0.txt or copy at http://www.boost.org/LICENSE_1_0.txt)

#include <boost/thread/shared_mutex.hpp>
#include <boost/thread/locks.hpp>

static int test_main() {

    boost::shared_mutex mtx; boost::upgrade_lock<boost::shared_mutex> lk(mtx);

    boost::upgrade_to_unique_lock<boost::shared_mutex> lk2(lk);

    return 0;
}

#include "common.hpp"

BOOST_AUTO_TEST_CASE(test_2501)
{
    common_init();
    std::thread([&]() {
        TEST_ASSERT(test_main() == 0);
    }).join();
}
