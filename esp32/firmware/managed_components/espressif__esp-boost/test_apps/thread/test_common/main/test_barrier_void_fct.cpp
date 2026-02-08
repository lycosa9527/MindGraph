// (C) Copyright 2013 Vicente J. Botet Escriba
//
//  Distributed under the Boost Software License, Version 1.0. (See accompanying
//  file LICENSE_1_0.txt or copy at http://www.boost.org/LICENSE_1_0.txt)

#define BOOST_THREAD_PROVIDES_INTERRUPTIONS

#include <boost/thread/detail/config.hpp>

#include <boost/thread/thread.hpp>
#include <boost/thread/barrier.hpp>

#include <boost/detail/lightweight_test.hpp>
#include <vector>

namespace {


// Shared variables for generation barrier test
long global_parameter;

void void_fct() {
  global_parameter++;
}

const int N_THREADS=3;
boost::barrier gen_barrier(N_THREADS, &void_fct);

static void barrier_thread()
{
    for (int i = 0; i < 5; ++i)
    {
        gen_barrier.count_down_and_wait();
    }
}

} // namespace

static void test_barrier()
{
    boost::thread_group g;
    global_parameter = 0;

    try
    {
        for (int i = 0; i < N_THREADS; ++i)
            g.create_thread(&barrier_thread);
        g.join_all();
    }
    catch(...)
    {
        BOOST_TEST(false);
        g.interrupt_all();
        g.join_all();
        //throw;
    }

    BOOST_TEST(global_parameter==5);

}

static int test_main()
{

    void test_barrier();
    return boost::report_errors();
}

#include "common.hpp"

BOOST_AUTO_TEST_CASE(test_barrier_void_fct)
{
  common_init();
  std::thread([](){
    TEST_ASSERT(test_main() == 0);
  }).join();
}
