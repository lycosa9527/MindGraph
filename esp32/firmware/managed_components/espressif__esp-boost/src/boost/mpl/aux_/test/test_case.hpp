
#ifndef BOOST_MPL_AUX_TEST_TEST_CASE_HPP_INCLUDED
#define BOOST_MPL_AUX_TEST_TEST_CASE_HPP_INCLUDED

// Copyright Aleksey Gurtovoy 2002-2004
//
// Distributed under the Boost Software License, Version 1.0.
// (See accompanying file LICENSE_1_0.txt or copy at
// http://www.boost.org/LICENSE_1_0.txt)
//
// See http://www.boost.org/libs/mpl for documentation.

// $Id$
// $Date$
// $Revision$

#include <boost/preprocessor/cat.hpp>

#ifdef ESP_PLATFORM
#include "unity.h"
#include "unity_test_utils.h"

#undef TO_STR
#define __TO_STR(x) # x
#define TO_STR(x) __TO_STR(x)
#define MPL_TEST_CASE() TEST_CASE("mpl: " __FILE__ ":"  TO_STR(__LINE__), "[mpl][" __FILE__ ":" TO_STR(__LINE__) "]")
#else
#define MPL_TEST_CASE() void BOOST_PP_CAT(test,__LINE__)()
#endif // ESP_PLATFORM


#endif // BOOST_MPL_AUX_TEST_TEST_CASE_HPP_INCLUDED
