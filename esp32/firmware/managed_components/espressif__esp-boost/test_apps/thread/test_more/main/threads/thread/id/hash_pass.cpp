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

// <functional>

// template <class T>
// struct hash
//     : public unary_function<T, size_t>
// {
//     size_t operator()(T val) const;
// };


#include <boost/thread/thread_only.hpp>
#include <boost/detail/lightweight_test.hpp>

static int test_main()
{
  {
    boost::thread::id id1;
    boost::thread::id id2 = boost::this_thread::get_id();
    typedef boost::hash<boost::thread::id> H;
    H h;
    BOOST_TEST(h(id1) != h(id2));
  }
  return boost::report_errors();
}

#include "common.hpp"

BOOST_AUTO_TEST_CASE(threads/thread/id, hash_pass)
{
  common_init();
  std::thread([&]() {
    TEST_ASSERT(test_main() == 0);
  }).join();
}
