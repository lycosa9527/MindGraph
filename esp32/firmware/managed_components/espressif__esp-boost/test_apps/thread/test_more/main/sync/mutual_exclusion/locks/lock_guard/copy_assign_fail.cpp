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

// <boost/thread/locks.hpp>

// template <class Mutex> class lock_guard;

// lock_guard& operator=(lock_guard const&) = delete;

#include <boost/thread/lock_guard.hpp>
#include <boost/thread/mutex.hpp>
#include <boost/detail/lightweight_test.hpp>

static boost::mutex m0;
static boost::mutex m1;

static int test_main()
{
  boost::lock_guard<boost::mutex> lk0(m0);
  boost::lock_guard<boost::mutex> lk1(m1);
  /* esp32: The code below is expected to fail compilation, it's commented out to allow compilation to pass */
  // lk1 = lk0;

}
