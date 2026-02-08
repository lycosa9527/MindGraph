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

// <boost/thread/thread.hpp>

// class thread

// template <class Clousure> thread(Clousure f);

#include <new>
#include <cstdlib>
#include <cassert>
#include <boost/thread/thread_only.hpp>
#include <boost/detail/lightweight_test.hpp>

#include "common.hpp"

namespace {

#if ! defined BOOST_NO_CXX11_LAMBDAS

static bool f_run = false;

static int test_main()
{
  {
    f_run = false;
    boost::thread t( []() { f_run = true; } );
    t.join();
    BOOST_TEST(f_run == true);
  }
#if !defined(BOOST_MSVC) && !defined(__MINGW32__)
  {
    f_run = false;
    try
    {
      throw_one = 0;
      boost::thread t( []() { f_run = true; } );
      BOOST_TEST(false);
    }
    catch (...)
    {
      throw_one = 0xFFFF;
      BOOST_TEST(!f_run);
    }
  }
#endif

  return boost::report_errors();
}

#else
static int test_main()
{
  return 0;
}
#endif

}

#include "common.hpp"

BOOST_AUTO_TEST_CASE(threads/thread/constr, lambda_pass)
{
  common_init();
  std::thread([&]() {
    TEST_ASSERT(test_main() == 0);
  }).join();
}
