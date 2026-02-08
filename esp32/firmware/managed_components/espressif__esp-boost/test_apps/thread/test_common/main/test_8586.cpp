// Copyright (C) 2013 Vicente Botet
//
//  Distributed under the Boost Software License, Version 1.0. (See accompanying
//  file LICENSE_1_0.txt or copy at http://www.boost.org/LICENSE_1_0.txt)

#include <boost/thread/thread.hpp>
#include <iostream>

void hello_world()
{
    std::cout << "Hello from thread!" << std::endl;
}

static int test_main()
{
    boost::thread my_thread(&hello_world);
    my_thread.join();
    return 0;
}

#include "common.hpp"

BOOST_AUTO_TEST_CASE(test_8586)
{
  common_init();
  std::thread([](){
    TEST_ASSERT(test_main() == 0);
  }).join();
}
