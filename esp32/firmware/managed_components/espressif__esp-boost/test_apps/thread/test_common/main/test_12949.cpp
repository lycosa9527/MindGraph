// Copyright (C) 2017 Vicente Botet
//
//  Distributed under the Boost Software License, Version 1.0. (See accompanying
//  file LICENSE_1_0.txt or copy at http://www.boost.org/LICENSE_1_0.txt)

#define BOOST_THREAD_VERSION 4

//#include <boost/thread/thread.hpp>
#include <boost/thread/condition_variable.hpp>

static void f()
{
    boost::this_thread::sleep_for(boost::chrono::milliseconds(10)); // **
}
static int test_main()
{

  return 0;
}

#include "common.hpp"

BOOST_AUTO_TEST_CASE(test_12949)
{
  common_init();
  std::thread([](){
    TEST_ASSERT(test_main() == 0);
  }).join();
}
