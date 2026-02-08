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

// template <class F, class ...Args> thread(F f, Args... args);

#include <new>
#include <cstdlib>
#include <cassert>
#include <boost/thread/thread_only.hpp>
#include <boost/detail/lightweight_test.hpp>

#include "common.hpp"

namespace {

static bool f_run = false;

static void f()
{
  f_run = true;
}

class G
{
  int alive_;
public:
  static int n_alive;
  static bool op_run;

  G() :
    alive_(1)
  {
    ++n_alive;
  }
  G(const G& g) :
    alive_(g.alive_)
  {
    ++n_alive;
  }
  ~G()
  {
    alive_ = 0;
    --n_alive;
  }

  void operator()()
  {
    BOOST_TEST(alive_ == 1);
    //BOOST_TEST(n_alive >= 1);
    op_run = true;
  }

};

int G::n_alive = 0;
bool G::op_run = false;


static int test_main()
{
  {
    boost::thread t(f);
    t.join();
    BOOST_TEST(f_run == true);
  }
  f_run = false;
#if !defined(BOOST_MSVC) && !defined(__MINGW32__)
  {
    try
    {
      throw_one = 0;
      boost::thread t(f);
      BOOST_TEST(false);
    }
    catch (...)
    {
      throw_one = 0xFFFF;
      BOOST_TEST(!f_run);
    }
  }
#endif
  {
    BOOST_TEST(G::n_alive == 0);
    BOOST_TEST(!G::op_run);
    boost::thread t( (G()));
    t.join();
    BOOST_TEST(G::n_alive == 0);
    BOOST_TEST(G::op_run);
  }
#if !defined(BOOST_MSVC) && !defined(__MINGW32__)
  G::op_run = false;
  {
    try
    {
      throw_one = 0;
      BOOST_TEST(G::n_alive == 0);
      BOOST_TEST(!G::op_run);
      boost::thread t( (G()));
      BOOST_TEST(false);
    }
    catch (...)
    {
      throw_one = 0xFFFF;
      BOOST_TEST(G::n_alive == 0);
      std::cout << __FILE__ << ":" << __LINE__ <<" " << G::n_alive << std::endl;
      BOOST_TEST(!G::op_run);
    }
  }
#endif

  return boost::report_errors();
}

}

#include "common.hpp"

BOOST_AUTO_TEST_CASE(threads/thread/constr, F_pass)
{
  common_init();
  std::thread([&]() {
    TEST_ASSERT(test_main() == 0);
  }).join();
}
