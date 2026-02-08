//=======================================================================
// Copyright 2001 Jeremy G. Siek, Andrew Lumsdaine, Lie-Quan Lee,
//
// Distributed under the Boost Software License, Version 1.0. (See
// accompanying file LICENSE_1_0.txt or copy at
// http://www.boost.org/LICENSE_1_0.txt)
//=======================================================================

/*
   IMPORTANT:
   ~~~~~~~~~~

   This example appears to be broken and crashes at runtime, see
   https://github.com/boostorg/graph/issues/148

*/

#include <boost/config.hpp>
#include <iostream>
#include <fstream>
#include <string>
#include <boost/tuple/tuple.hpp>
#include <boost/graph/adjacency_list.hpp>
#include <boost/graph/visitors.hpp>
#include <boost/graph/breadth_first_search.hpp>
#include <map>
#include <boost/graph/adj_list_serialize.hpp>
#include <boost/archive/text_iarchive.hpp>
#include <boost/serialization/string.hpp>
#include "common_components.hpp"
#include "embedded_files_lut.hpp"

struct vertex_properties
{
    std::string name;

    template < class Archive >
    void serialize(Archive& ar, const unsigned int version)
    {
        ar& name;
    }
};

struct edge_properties
{
    std::string name;

    template < class Archive >
    void serialize(Archive& ar, const unsigned int version)
    {
        ar& name;
    }
};

using namespace boost;

typedef adjacency_list< vecS, vecS, undirectedS, vertex_properties,
    edge_properties >
    Graph;
typedef graph_traits< Graph >::vertex_descriptor Vertex;
typedef graph_traits< Graph >::edge_descriptor Edge;

class bacon_number_recorder : public default_bfs_visitor
{
public:
    bacon_number_recorder(int* dist) : d(dist) {}

    void tree_edge(Edge e, const Graph& g) const
    {
        auto u = source(e, g), v = target(e, g);
        d[v] = d[u] + 1;
    }

private:
    int* d;
};

static int test_main(int argc, const char** argv)
{
    // std::ifstream ifs(argc >= 2 ? argv[1] : "./kevin-bacon2.dat");
    const char* data_file_name
        = argc >= 2 ? argv[1] : "kevin-bacon2.dat";
    auto ifs_ptr = open_input_stream(embedded_files, data_file_name);
    std::istream& ifs = *ifs_ptr;
    if (!ifs)
    {
        std::cerr << "No ./kevin-bacon2.dat file" << std::endl;
        return EXIT_FAILURE;
    }
    // const char* embedded_graph_data = R"(22 serialization::archive 3 0 0 51 50 0 0 15 William Shatner 15 Denise Richards 11 Kevin Bacon 15 Patrick Stewart 12 Steve Martin 16 Gerard Depardieu 12 Clint Howard 10 Sean Astin 17 Theodore Hesburgh 12 Gerry Becker 11 Henry Fonda 13 Robert Wagner 11 Mark Hamill 11 Bill Paxton 13 Harrison Ford 11 Steve Altes 13 Alec Guinness 15 Theresa Russell 13 Carrie Fisher 14 Elisabeth Shue 12 Sean Connery 13 Peter Crombie 10 Dana Young 10 Bebe Drake 14 William Devane 11 A. Paliakov 16 Nikolai Brilling 14 Kathleen Byron 9 Tom Hanks 17 Zoya Barantsevich 13 Nikolai Panov 15 Zoia Karabanova 15 William Challee 11 P. Biryukov 16 Aleksandr Gromov 16 Yelena Maksimova 12 Lev Prygunov 13 Yelena Chaika 17 Viktor Tourjansky 14 Olga Baclanova 15 Angelo Rossitto 14 Christel Holch 12 Aage Schmidt 10 Valso Holm 13 Max von Sydow 10 Diane Lane 10 Val Kilmer 14 Marilyn Monroe 11 George Ives 14 Jacques Perrin 16 Vittorio Gassman 0 1 0 0 22 Loaded Weapon 1 (1993) 1 2 18 Wild Things (1998) 3 4 27 Prince of Egypt, The (1998) 4 2 16 Novocaine (2000) 5 6 23 Unhook the Stars (1996) 6 2 18 My Dog Skip (2000) 7 2 25 White Water Summer (1987) 8 9 11 Rudy (1993) 9 2 15 Sleepers (1996) 10 11 13 Midway (1976) 11 2 18 Wild Things (1998) 12 13 17 Slipstream (1989) 13 2 16 Apollo 13 (1995) 14 15 20 Random Hearts (1999) 15 2 17 Hollow Man (2000) 16 17 12 Kafka (1991) 17 2 18 Wild Things (1998) 18 19 15 Soapdish (1991) 19 2 17 Hollow Man (2000) 20 21 17 Rising Sun (1993) 21 2 18 My Dog Skip (2000) 22 23 23 Bersaglio mobile (1967) 23 24 33 Report to the Commissioner (1975) 25 26 14 Kutuzov (1944) 26 27 13 Otello (1955) 27 28 26 Saving Private Ryan (1998) 28 2 16 Apollo 13 (1995) 29 30 24 Slesar i kantzler (1923) 30 31 30 Zhenshchina s kinzhalom (1916) 31 32 26 Song to Remember, A (1945) 32 24 30 Irish Whiskey Rebellion (1972) 24 2 17 Hollow Man (2000) 33 34 20 Pikovaya dama (1910) 34 35 17 Tikhij Don (1930) 35 36 23 Bezottsovshchina (1976) 36 19 17 Saint, The (1997) 37 38 21 Ostrov zabenya (1917) 38 39 28 Zagrobnaya skitalitsa (1915) 39 40 13 Freaks (1932) 40 24 16 Dark, The (1979) 41 42 31 Hvide Slavehandel, Den (1910/I) 42 43 27 Begyndte ombord, Det (1937) 43 44 16 Spion 503 (1958) 44 45 18 Judge Dredd (1995) 45 2 18 My Dog Skip (2000) 46 19 17 Saint, The (1997) 47 48 14 Niagara (1953) 48 2 21 Stir of Echoes (1999) 49 50 30 Deserto dei tartari, Il (1976) 50 2 15 Sleepers (1996))";
    Graph g;

    try {
        // std::stringstream iss;
        // iss << embedded_graph_data;  // Copies to buffer
        // boost::archive::text_iarchive ia(iss);
        archive::text_iarchive ia(ifs);
        ia >> g;
    } catch (const std::exception& e) {
        std::cerr << "Deserialization failed: " << e.what() << std::endl;
    }

    std::vector< int > bacon_number(num_vertices(g));

    // Get the vertex for Kevin Bacon
    Vertex src;
    graph_traits< Graph >::vertex_iterator i, end;
    for (boost::tie(i, end) = vertices(g); i != end; ++i)
        if (g[*i].name == "Kevin Bacon")
            src = *i;

    // Set Kevin's number to zero
    bacon_number[src] = 0;

    // Perform a breadth first search to compute everyone' Bacon number.
    breadth_first_search(
        g, src, visitor(bacon_number_recorder(&bacon_number[0])));

    for (boost::tie(i, end) = vertices(g); i != end; ++i)
        std::cout << g[*i].name << " has a Bacon number of " << bacon_number[*i]
                  << std::endl;

    return 0;
}


#include "common.hpp"

BOOST_AUTO_TEST_CASE(kevin-bacon2)
{
    TEST_ASSERT(test_main(0, nullptr) == 0);
    // deserialization failure
    /* esp32: test failed due to memory leak */
}
