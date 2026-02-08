// Copyright (C) 2001-2003
// William E. Kempf
//
//  Distributed under the Boost Software License, Version 1.0. (See accompanying
//  file LICENSE_1_0.txt or copy at http://www.boost.org/LICENSE_1_0.txt)

#include <iostream>
#include <vector>
#include <boost/utility.hpp>
#include <boost/thread/condition_variable.hpp>
#include <boost/thread/thread_only.hpp>
#include "../test/remove_error_code_unused_warning.hpp"

namespace {

class bounded_buffer : private boost::noncopyable
{
public:
    typedef boost::unique_lock<boost::mutex> lock;

    bounded_buffer(int n) : boost::noncopyable(), begin(0), end(0), buffered(0), circular_buf(n) { }

    void send (int m) {
        lock lk(monitor);
        while (buffered == circular_buf.size())
            buffer_not_full.wait(lk);
        circular_buf[end] = m;
        end = (end+1) % circular_buf.size();
        ++buffered;
        buffer_not_empty.notify_one();
    }
    int receive() {
        lock lk(monitor);
        while (buffered == 0)
            buffer_not_empty.wait(lk);
        int i = circular_buf[begin];
        begin = (begin+1) % circular_buf.size();
        --buffered;
        buffer_not_full.notify_one();
        return i;
    }

private:
    int begin, end;
    std::vector<int>::size_type buffered;
    std::vector<int> circular_buf;
    boost::condition_variable_any buffer_not_full, buffer_not_empty;
    boost::mutex monitor;
};

boost::mutex io_mutex;

/* esp32: avoid timeout */
#define COUNT   10000
#define N_PRINT 100

void sender(bounded_buffer &buf) {
    int n = 0;
    while (n < COUNT) {
        buf.send(n);
        if(!(n%N_PRINT))
        {
            boost::unique_lock<boost::mutex> io_lock(io_mutex);
            std::cout << "sent: " << n << std::endl;
        }
        ++n;
    }
    buf.send(-1);
}

void receiver(bounded_buffer &buf) {
    int n;
    do {
        n = buf.receive();
        if(!(n%N_PRINT))
        {
            boost::unique_lock<boost::mutex> io_lock(io_mutex);
            std::cout << "received: " << n << std::endl;
        }
    } while (n != -1); // -1 indicates end of buffer
    buf.send(-1);
}

static int test_main()
{
    bounded_buffer buf(2);

    boost::thread thrd1(&sender, boost::ref(buf));
    boost::thread thrd2(&receiver, boost::ref(buf));
    boost::thread thrd3(&receiver, boost::ref(buf));
    boost::thread thrd4(&receiver, boost::ref(buf));
    thrd1.join();
    thrd2.join();
    thrd3.join();
    thrd4.join();
    return 0;
}

} // namespace

#include "common.hpp"

BOOST_AUTO_TEST_CASE(condition)
{
    common_init();
    std::thread([&]() {
        TEST_ASSERT(test_main() == 0);
    }).join();
}
