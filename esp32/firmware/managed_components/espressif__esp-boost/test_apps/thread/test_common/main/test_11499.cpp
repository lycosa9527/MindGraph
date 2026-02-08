// Copyright (C) 2014 Vicente Botet
//
//  Distributed under the Boost Software License, Version 1.0. (See accompanying
//  file LICENSE_1_0.txt or copy at http://www.boost.org/LICENSE_1_0.txt)

#define BOOST_THREAD_VERSION 4

#define TEST_COUNT 4

#include <boost/thread/shared_mutex.hpp>
#include <iostream>
#include <thread>
#include <mutex>
#include <shared_mutex>
#include <atomic>
#include <vector>

using MutexT = boost::shared_mutex;
using ReaderLockT = std::lock_guard<MutexT>;
using WriterLockT = std::shared_lock<MutexT>;

MutexT gMutex;
std::atomic<bool> running(true);


void myread()
{
   std::cout << "thread " << std::this_thread::get_id() << " created" << std::endl;
  long reads = 0;
   while (running && reads < 100000)
   {
      ReaderLockT lock(gMutex);
      std::this_thread::yield();
      ++reads;
   }
   std::cout << "thread " << std::this_thread::get_id() << " finished" << std::endl;
}

static int test_main()
{
   using namespace std;

   vector<thread> threads;
   for (int i = 0; i < TEST_COUNT; ++i)
   {
      threads.emplace_back(thread(myread));
   }

//   string str;
//
//   getline(std::cin, str);
   running = false;

   for (auto& thread : threads)
   {
      thread.join();
   }

   return 0;
}

#include "common.hpp"

BOOST_AUTO_TEST_CASE(test_11499)
{
  common_init();
  std::thread([](){
    TEST_ASSERT(test_main() == 0);
  }).join();
}
