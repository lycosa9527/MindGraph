//=======================================================================
// Copyright 2001 Jeremy G. Siek, Andrew Lumsdaine, Lie-Quan Lee,
//
// Distributed under the Boost Software License, Version 1.0. (See
// accompanying file LICENSE_1_0.txt or copy at
// http://www.boost.org/LICENSE_1_0.txt)
//=======================================================================
// #include <boost/graph/leda_graph.hpp>
#include <iostream>
#undef string // LEDA macro!
static int test_main()
{
    // using namespace boost;
    // typedef leda::GRAPH< std::string, int > graph_t;
    // graph_t g;
    // g.new_node("Philoctetes");
    // g.new_node("Heracles");
    // g.new_node("Alcmena");
    // g.new_node("Eurystheus");
    // g.new_node("Amphitryon");
    // typedef property_map< graph_t, vertex_all_t >::type NodeMap;
    // auto node_name_map = get(vertex_all, g);
    // graph_traits< graph_t >::vertex_iterator vi, vi_end;
    // for (boost::tie(vi, vi_end) = vertices(g); vi != vi_end; ++vi)
    //     std::cout << node_name_map[*vi] << std::endl;
    return EXIT_SUCCESS;
}


#include "common.hpp"

BOOST_AUTO_TEST_CASE(leda-graph-eg)
{
    TEST_ASSERT(test_main() == 0);
    /* esp32: test fails to compile due to its requirement of the LEDA GraphBase */
    std::cout << std::endl;
    std::cout << "!!! THIS TEST IS SKIPPED DUE TO ITS REQUIREMENT OF THE LEDA GraphBase. !!!" << std::endl;
    std::cout << std::endl;
}
