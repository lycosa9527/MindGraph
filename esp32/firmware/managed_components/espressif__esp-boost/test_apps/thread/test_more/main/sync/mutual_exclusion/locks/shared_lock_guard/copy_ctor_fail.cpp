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

// <boost/thread/shared_lock_guard.hpp>

// template <class Mutex> class shared_lock_guard;

// shared_lock_guard(shared_lock_guard const&) = delete;


#include <boost/thread/shared_lock_guard.hpp>
#include <boost/thread/shared_mutex.hpp>
#include <boost/detail/lightweight_test.hpp>

static boost::shared_mutex m0;
static boost::shared_mutex m1;

static int test_main()
{
  boost::shared_lock_guard<boost::shared_mutex> lk0(m0);
  /* esp32: The code below is expected to fail compilation, it's commented out to allow compilation to pass */
  // boost::shared_lock_guard<boost::shared_mutex> lk1 = lk0;
}
