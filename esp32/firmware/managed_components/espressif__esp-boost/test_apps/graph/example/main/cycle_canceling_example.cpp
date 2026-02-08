//=======================================================================
// Copyright 2013 University of Warsaw.
// Authors: Piotr Wygocki
//
// Distributed under the Boost Software License, Version 1.0. (See
// accompanying file LICENSE_1_0.txt or copy at
// http://www.boost.org/LICENSE_1_0.txt)
//=======================================================================

#include <boost/graph/cycle_canceling.hpp>
#include <boost/graph/edmonds_karp_max_flow.hpp>

#include "min_cost_max_flow_utils.hpp"

static int test_main()
{
    boost::SampleGraph::vertex_descriptor s, t;
    boost::SampleGraph::Graph g;
    boost::SampleGraph::getSampleGraph(g, s, t);

    boost::edmonds_karp_max_flow(g, s, t);
    boost::cycle_canceling(g);

    auto cost = boost::find_flow_cost(g);
    assert(cost == 29);
    return 0;
}

#include "common.hpp"

BOOST_AUTO_TEST_CASE(cycle_cancelling_example)
{
  TEST_ASSERT(test_main() == 0);
}
