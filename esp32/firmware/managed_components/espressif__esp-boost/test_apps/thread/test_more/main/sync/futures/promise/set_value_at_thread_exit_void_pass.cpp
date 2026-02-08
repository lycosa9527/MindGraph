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

// <boost/thread/future.hpp>

// class promise<R>

// void promise<void>::set_value_at_thread_exit();

#define BOOST_THREAD_VERSION 4

#include <boost/thread/future.hpp>
#include <boost/detail/lightweight_test.hpp>

static void func(boost::promise<void> *p, int &i)
{
  p->set_value_at_thread_exit();
  i = 1;
}

//void func2_mv(BOOST_THREAD_RV_REF(boost::promise<void>) p2)
static void func2_mv(boost::promise<void> p2, int &i)
{
  p2.set_value_at_thread_exit();
  i = 2;
}

static void func2(boost::promise<void> *p2, int &i)
{
  p2->set_value_at_thread_exit();
  i = 2;
}
static int test_main()
{
  int i = 0;
  boost::promise<void> p;

  try
  {
    boost::future<void> f = p.get_future();
    boost::thread(func, &p, boost::ref(i)).detach();
    f.get();
    BOOST_TEST(i == 1);

  }
  catch(std::exception& )
  {
    BOOST_TEST(false);
  }
  catch(...)
  {
    BOOST_TEST(false);
  }

  try
  {
    boost::promise<void> p2;
    boost::future<void> f = p2.get_future();
    p = boost::move(p2);
    boost::thread(func, &p, boost::ref(i)).detach();
    f.get();
    BOOST_TEST(i == 1);

  }
  catch(std::exception& ex)
  {
    std::cout << __FILE__ << ":" << __LINE__ << " " << ex.what() << std::endl;
    BOOST_TEST(false);
  }
  catch(...)
  {
    BOOST_TEST(false);
  }

  try
  {
    boost::promise<void> p2;
    boost::future<void> f = p2.get_future();
#if defined BOOST_THREAD_PROVIDES_VARIADIC_THREAD
    boost::thread(func2_mv, boost::move(p2), boost::ref(i)).detach();
#else
    boost::thread(func2, &p2, boost::ref(i)).detach();
#endif
    f.wait();
    f.get();
    BOOST_TEST(i == 2);
  }
  catch(std::exception& ex)
  {
    std::cout << __FILE__ << ":" << __LINE__ << " " << ex.what() << std::endl;
    BOOST_TEST(false);
  }
  catch(...)
  {
    BOOST_TEST(false);
  }
  return boost::report_errors();
}

#include "common.hpp"

BOOST_AUTO_TEST_CASE(sync/futures/promise, set_value_at_thread_exit_void_pass)
{
    common_init();
    std::thread([&]() {
        TEST_ASSERT(test_main() == 0);
    }).join();
}
