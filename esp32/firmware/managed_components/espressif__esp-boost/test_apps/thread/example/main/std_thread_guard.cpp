// (C) Copyright 2009-2012 Anthony Williams
// (C) Copyright 2012 Vicente Botet
//
//  Distributed under the Boost Software License, Version 1.0. (See accompanying
//  file LICENSE_1_0.txt or copy at http://www.boost.org/LICENSE_1_0.txt)

#if __cplusplus < 201103L
static int test_main()
{
  return 0;
}
#else
#include <iostream>
#include <string>
#include <boost/thread/thread_only.hpp>
#include <boost/thread/thread_guard.hpp>
#include <thread>

namespace {

void do_something(int& i)
{
    ++i;
}

struct func
{
    int& i;

    func(int& i_):i(i_){}

    void operator()()
    {
        for(unsigned j=0;j<1000000;++j)
        {
            do_something(i);
        }
    }

private:
    func& operator=(func const&);

};

void do_something_in_current_thread()
{}

using thread_guard = boost::thread_guard<boost::join_if_joinable, std::thread>;


void f()
{
    int some_local_state;
    func my_func(some_local_state);
    std::thread t(my_func);
    thread_guard g(t);

    do_something_in_current_thread();
}

static int test_main()
{
    f();
    return 0;
}


#endif

} // namespace

#include "common.hpp"

BOOST_AUTO_TEST_CASE(std_thread_guard)
{
    common_init();
    std::thread([&]() {
        TEST_ASSERT(test_main() == 0);
    }).join();
}
