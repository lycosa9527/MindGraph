// Copyright (C) 2014 Vicente Botet
//
//  Distributed under the Boost Software License, Version 1.0. (See accompanying
//  file LICENSE_1_0.txt or copy at http://www.boost.org/LICENSE_1_0.txt)

#define BOOST_THREAD_VERSION 4

#define TEST_COUNT 100

#include <iostream>

#define BOOST_THREAD_PROVIDES_FUTURE
#define BOOST_THREAD_PROVIDES_EXECUTORS
#define BOOST_THREAD_PROVIDES_FUTURE_CONTINUATION

#if __cplusplus >= 201103L
#include <boost/thread/executors/loop_executor.hpp>
#include <boost/thread/executors/serial_executor.hpp>
#endif
#include <boost/thread/thread.hpp>
#include <boost/atomic.hpp>

#include "freertos/FreeRTOS.h"
#include "freertos/task.h"

using namespace std;

static int test_main()
{
#if __cplusplus >= 201103L
   static std::size_t const nWorks = TEST_COUNT;
   boost::atomic<unsigned> execCount(0u);
   boost::loop_executor ex;

   boost::thread t([&ex]()
   {
      ex.loop();
   });

   {
     boost::serial_executor serial(ex);

      for (size_t i = 0; i < nWorks; i++)
         serial.submit([i, &execCount] {
             std::cout << i << ".";
             ++execCount;
         });

      serial.close();
   }
   unsigned const cnt = execCount.load();
   if (cnt != nWorks) {
      // Since the serial_executor is closed, all work should have been done,
      // even though the loop_executor ex is not.
      std::cerr << "Only " << cnt << " of " << nWorks << " works executed!\n";
      return 1;
   }

   if (ex.try_executing_one()) {
      std::cerr
         << "loop_executor::try_executing_one suceeded on closed executor!\n";
      return 1;
   }

   ex.close();

   t.join();
   std::cout << "end\n" << std::endl;
#endif
   return 0;
}

#include "common.hpp"

BOOST_AUTO_TEST_CASE(test_11611)
{
   common_init();
   common_set_pthread_config("pthread", -1, 10 * 1024, 1, true);
   std::thread([]() {
      TEST_ASSERT(test_main() == 0);
   }).join();
   common_reset_pthread_config();
}
