// Copyright (C) 2010 Vicente Botet
//
//  Distributed under the Boost Software License, Version 1.0. (See accompanying
//  file LICENSE_1_0.txt or copy at http://www.boost.org/LICENSE_1_0.txt)

#define BOOST_THREAD_VERSION 2

#include <boost/thread/thread_only.hpp>
#include <boost/thread/future.hpp>

static int calculate_the_answer_to_life_the_universe_and_everything()
{
    return 42;
}

static int test_main() {
boost::packaged_task<int> pt(calculate_the_answer_to_life_the_universe_and_everything);

//boost::unique_future<int> fi = BOOST_THREAD_MAKE_RV_REF(pt.get_future());
boost::unique_future<int> fi((BOOST_THREAD_MAKE_RV_REF(pt.get_future())));

boost::thread task(boost::move(pt)); // launch task on a thread

fi.wait(); // wait for it to finish

//assert(fi.is_ready());
//assert(fi.has_value());
//assert(!fi.has_exception());
//assert(fi.get_state()==boost::future_state::ready);
//assert(fi.get()==42);

    return 0;
}

#include "common.hpp"

BOOST_AUTO_TEST_CASE(test_4521)
{
    common_init();
    std::thread([&]() {
        TEST_ASSERT(test_main() == 0);
    }).join();
}
