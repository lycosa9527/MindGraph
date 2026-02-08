// Copyright (C) 2001-2003
// William E. Kempf
//
//  Distributed under the Boost Software License, Version 1.0. (See accompanying
//  file LICENSE_1_0.txt or copy at http://www.boost.org/LICENSE_1_0.txt)

#include <boost/thread/mutex.hpp>
#include <boost/thread/thread.hpp>
#include <iostream>

boost::mutex io_mutex; // The iostreams are not guaranteed to be thread-safe!

namespace {

class counter
{
public:
    counter() : count(0) { }

    int increment() {
        boost::unique_lock<boost::mutex> scoped_lock(mutex);
        return ++count;
    }

private:
    boost::mutex mutex;
    int count;
};

counter c;

void change_count()
{
    int i = c.increment();
    boost::unique_lock<boost::mutex> scoped_lock(io_mutex);
    std::cout << "count == " << i << std::endl;
}

static int test_main()
{
    const int num_threads = 4;
    boost::thread_group thrds;
    for (int i=0; i < num_threads; ++i)
        thrds.create_thread(&change_count);

    thrds.join_all();

    return 0;
}

} // namespace

#include "common.hpp"

BOOST_AUTO_TEST_CASE(mutex)
{
    common_init();
    std::thread([&]() {
        TEST_ASSERT(test_main() == 0);
    }).join();
}
