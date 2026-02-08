// Copyright 2023 Peter Dimov
// Distributed under the Boost Software License, Version 1.0.
// https://www.boost.org/LICENSE_1_0.txt

#include <boost/thread/detail/string_trim.hpp>
#include <boost/core/lightweight_test.hpp>

static int test_main()
{
    using boost::thread_detail::string_trim;

    BOOST_TEST_EQ( string_trim( "" ), std::string( "" ) );
    BOOST_TEST_EQ( string_trim( " " ), std::string( "" ) );
    BOOST_TEST_EQ( string_trim( "  " ), std::string( "" ) );
    BOOST_TEST_EQ( string_trim( "   " ), std::string( "" ) );

    BOOST_TEST_EQ( string_trim( " \t\r\n \t\r\n" ), std::string( "" ) );

    BOOST_TEST_EQ( string_trim( "a" ), std::string( "a" ) );

    BOOST_TEST_EQ( string_trim( " a" ), std::string( "a" ) );
    BOOST_TEST_EQ( string_trim( "  a" ), std::string( "a" ) );
    BOOST_TEST_EQ( string_trim( "   a" ), std::string( "a" ) );

    BOOST_TEST_EQ( string_trim( "a " ), std::string( "a" ) );
    BOOST_TEST_EQ( string_trim( "a  " ), std::string( "a" ) );
    BOOST_TEST_EQ( string_trim( "a   " ), std::string( "a" ) );

    BOOST_TEST_EQ( string_trim( " a " ), std::string( "a" ) );
    BOOST_TEST_EQ( string_trim( "  a  " ), std::string( "a" ) );
    BOOST_TEST_EQ( string_trim( "   a   " ), std::string( "a" ) );

    BOOST_TEST_EQ( string_trim( "a b" ), std::string( "a b" ) );

    BOOST_TEST_EQ( string_trim( " a b" ), std::string( "a b" ) );
    BOOST_TEST_EQ( string_trim( "  a b" ), std::string( "a b" ) );
    BOOST_TEST_EQ( string_trim( "   a b" ), std::string( "a b" ) );

    BOOST_TEST_EQ( string_trim( "a b " ), std::string( "a b" ) );
    BOOST_TEST_EQ( string_trim( "a b  " ), std::string( "a b" ) );
    BOOST_TEST_EQ( string_trim( "a b   " ), std::string( "a b" ) );

    BOOST_TEST_EQ( string_trim( " a b " ), std::string( "a b" ) );
    BOOST_TEST_EQ( string_trim( "  a  b  " ), std::string( "a  b" ) );
    BOOST_TEST_EQ( string_trim( "   a   b   " ), std::string( "a   b" ) );

    return boost::report_errors();
}

#include "common.hpp"

BOOST_AUTO_TEST_CASE(detail, string_trim_test)
{
    common_init();
    std::thread([&]() {
        TEST_ASSERT(test_main() == 0);
    }).join();
}
