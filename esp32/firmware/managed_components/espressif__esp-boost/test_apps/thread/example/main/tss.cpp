// Copyright (C) 2001-2003
// William E. Kempf
//
//  Distributed under the Boost Software License, Version 1.0. (See accompanying
//  file LICENSE_1_0.txt or copy at http://www.boost.org/LICENSE_1_0.txt)

#include <boost/thread/thread.hpp>
#include <boost/thread/tss.hpp>
#include <cassert>

namespace {

boost::thread_specific_ptr<int> value;

void increment()
{
    int* p = value.get();
    ++*p;
}

void thread_proc()
{
    value.reset(new int(0)); // initialize the thread's storage
    for (int i=0; i<10; ++i)
    {
        increment();
        int* p = value.get();
        assert(*p == i+1);
        (void)(p);
    }
}

static int test_main()
{
    boost::thread_group threads;
    for (int i=0; i<5; ++i)
        threads.create_thread(&thread_proc);
    threads.join_all();
    return 0;
}

} // namespace

#include "common.hpp"

BOOST_AUTO_TEST_CASE(tss)
{
    common_init();
    std::thread([&]() {
        TEST_ASSERT(test_main() == 0);
    }).join();
}
