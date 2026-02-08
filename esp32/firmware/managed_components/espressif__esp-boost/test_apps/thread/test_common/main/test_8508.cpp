// Copyright (C) 2013 Vicente Botet
//
//  Distributed under the Boost Software License, Version 1.0. (See accompanying
//  file LICENSE_1_0.txt or copy at http://www.boost.org/LICENSE_1_0.txt)

//#define BOOST_THREAD_VERSION 2

#include <boost/thread/thread.hpp>

void thread_main()
{
}

static int test_main(void)
{
        boost::thread t(thread_main);
        t.join();
        return 0;
}

#include "common.hpp"

BOOST_AUTO_TEST_CASE(test_8508)
{
  common_init();
  std::thread([](){
    TEST_ASSERT(test_main() == 0);
  }).join();
}
