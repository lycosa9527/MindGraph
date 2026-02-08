// Copyright (C) 2012 Vicente Botet
//
//  Distributed under the Boost Software License, Version 1.0. (See accompanying
//  file LICENSE_1_0.txt or copy at http://www.boost.org/LICENSE_1_0.txt)

#define BOOST_THREAD_VERSION 4

#include <boost/thread/mutex.hpp>
#include <boost/thread/lock_traits.hpp>
#include <boost/thread/shared_mutex.hpp>
#include <boost/thread/strict_lock.hpp>
#include <boost/thread/lock_types.hpp>
#include <iostream>


BOOST_STATIC_ASSERT(boost::is_strict_lock<boost::strict_lock<boost::mutex> >::value);
BOOST_CONCEPT_ASSERT(( boost::BasicLockable<boost::mutex> ));
BOOST_CONCEPT_ASSERT(( boost::StrictLock<boost::strict_lock<boost::mutex> > ));

namespace {

static int test_main()
{
  {
    boost::mutex mtx;
    boost::strict_lock<boost::mutex> lk(mtx);
    std::cout << __FILE__ << std::endl;
  }
  {
    boost::timed_mutex mtx;
    boost::unique_lock<boost::timed_mutex> lk(mtx);
    boost::nested_strict_lock<boost::unique_lock<boost::timed_mutex> > nlk(lk);
    std::cout << __FILE__ << std::endl;
  }
  {
    boost::mutex mtx;
    boost::unique_lock<boost::mutex> lk(mtx, boost::defer_lock);
    boost::nested_strict_lock<boost::unique_lock<boost::mutex> > nlk(lk);
    std::cout << __FILE__ << std::endl;
  }
  return 0;
}

} // namespace

#include "common.hpp"

BOOST_AUTO_TEST_CASE(strict_lock)
{
    common_init();
    std::thread([&]() {
        TEST_ASSERT(test_main() == 0);
    }).join();
}
