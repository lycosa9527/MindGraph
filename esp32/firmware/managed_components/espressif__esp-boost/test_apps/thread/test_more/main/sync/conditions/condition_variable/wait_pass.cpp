//===----------------------------------------------------------------------===//
//
//                     The LLVM Compiler Infrastructure
//
// This file is dual licensed under the MIT and the University of Illinois Open
// Source Licenses. See LICENSE.TXT for details.
//
//===----------------------------------------------------------------------===//
// Copyright (C) 2011 Vicente J. Botet Escriba
//
//  Distributed under the Boost Software License, Version 1.0. (See accompanying
//  file LICENSE_1_0.txt or copy at http://www.boost.org/LICENSE_1_0.txt)

// <boost/thread/condition_variable>

// class condition_variable;

// void wait(unique_lock<mutex>& lock);


#include <boost/thread/condition_variable.hpp>
#include <boost/thread/mutex.hpp>
#include <boost/thread/thread.hpp>
#include <boost/detail/lightweight_test.hpp>
#include <cassert>
#include <iostream>

#if defined BOOST_THREAD_USES_CHRONO

static boost::condition_variable cv;
static boost::mutex mut;

static int test1 = 0;
static int test2 = 0;

static int runs = 0;

static void f()
{
  try {
    boost::unique_lock<boost::mutex> lk(mut);
    assert(test2 == 0);
    test1 = 1;
    cv.notify_one();
    while (test2 == 0) {
        cv.wait(lk);
    }
    assert(test2 != 0);
  } catch(...) {
    std::cout << "ERROR exception" << __LINE__ << std::endl;
    assert(false);
  }
}

static int test_main()
{
  try {
    boost::unique_lock<boost::mutex>lk(mut);
    boost::thread t(f);
    BOOST_TEST(test1 == 0);
    while (test1 == 0)
    {
        cv.wait(lk);
    }
    BOOST_TEST(test1 != 0);
    test2 = 1;
    lk.unlock();
    cv.notify_one();
    t.join();
  } catch(...) {
    BOOST_TEST(false);
    std::cout << "ERROR exception" << __LINE__ << std::endl;
  }
  return boost::report_errors();
}
#else
#error "Test not applicable: BOOST_THREAD_USES_CHRONO not defined for this platform as not supported"
#endif
#include "common.hpp"

BOOST_AUTO_TEST_CASE(sync/conditions/condition_variable, wait_pass)
{
    common_init();
    std::thread([&]() {
        TEST_ASSERT(test_main() == 0);
    }).join();
}
