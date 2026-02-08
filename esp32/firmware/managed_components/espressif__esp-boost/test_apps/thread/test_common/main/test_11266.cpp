// Copyright (C) 2015 Vicente Botet
//
//  Distributed under the Boost Software License, Version 1.0. (See accompanying
//  file LICENSE_1_0.txt or copy at http://www.boost.org/LICENSE_1_0.txt)

#define BOOST_THREAD_VERSION 4

#include <boost/thread/future.hpp>

void func(int) { }

static int test_main()
{
#if defined BOOST_THREAD_PROVIDES_SIGNATURE_PACKAGED_TASK && defined(BOOST_THREAD_PROVIDES_VARIADIC_THREAD)
  {
  boost::packaged_task<void(int)> task{func};
  }
  {
    boost::packaged_task<void(int)> task{func};

    task(0);
  }
  {
    boost::packaged_task<void(int)> task{func};
    int x = 0;
    task(x);
  }
#endif

  return 0;
}

#include "common.hpp"

BOOST_AUTO_TEST_CASE(test_11266)
{
  common_init();
  std::thread([](){
    TEST_ASSERT(test_main() == 0);
  }).join();
}
