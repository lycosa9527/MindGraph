//=======================================================================
// Copyright 2001 Jeremy G. Siek, Andrew Lumsdaine, Lie-Quan Lee,
//
// Distributed under the Boost Software License, Version 1.0. (See
// accompanying file LICENSE_1_0.txt or copy at
// http://www.boost.org/LICENSE_1_0.txt)
//=======================================================================
#include <boost/config.hpp>
#include <fstream>
#include <boost/graph/adjacency_list.hpp>
#include "common_components.hpp"
#include "embedded_files_lut.hpp"

using namespace boost;

template < typename Graph > void read_graph_file(std::istream& in, Graph& g)
{
    typedef typename graph_traits< Graph >::vertex_descriptor Vertex;
    typedef typename graph_traits< Graph >::vertices_size_type size_type;
    size_type n_vertices;
    in >> n_vertices; // read in number of vertices
    std::vector< Vertex > vertex_set(n_vertices);
    for (size_type i = 0; i < n_vertices; ++i)
        vertex_set[i] = add_vertex(g);

    size_type u, v;
    while (in >> u)
        if (in >> v)
            add_edge(vertex_set[u], vertex_set[v], g);
        else
            break;
}

static int test_main(int argc, const char** argv)
{
    typedef adjacency_list< listS, // Store out-edges of each vertex in a
                                   // std::list
        vecS, // Store vertex set in a std::vector
        directedS // The graph is directed
        >
        graph_type;

    graph_type g; // use default constructor to create empty graph
    // std::ifstream file_in(argc >= 2 ? argv[1] : "makefile-dependencies.dat");
    const char* file_name
        = argc >= 2 ? argv[1] : "makefile-dependencies.dat";
    auto file_in_ptr = open_input_stream(embedded_files, file_name);
    std::istream& file_in = *file_in_ptr;
    read_graph_file(file_in, g);

    assert(num_vertices(g) == 15);
    assert(num_edges(g) == 19);
    return 0;
}


#include "common.hpp"

BOOST_AUTO_TEST_CASE(default-constructor2)
{
    TEST_ASSERT(test_main(0, nullptr) == 0);
}
