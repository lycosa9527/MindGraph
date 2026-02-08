// Copyright (C) 2008 Anthony Williams
//
//  Distributed under the Boost Software License, Version 1.0. (See accompanying
//  file LICENSE_1_0.txt or copy at http://www.boost.org/LICENSE_1_0.txt)
#include <boost/thread/thread.hpp>

#pragma GCC diagnostic push
#pragma GCC diagnostic ignored "-Wunused-function"

static void do_nothing()
{}

#pragma GCC diagnostic pop

static void test()
{
    // boost::thread t1(do_nothing);
    // boost::thread t2;
    // t2=t1;
}
