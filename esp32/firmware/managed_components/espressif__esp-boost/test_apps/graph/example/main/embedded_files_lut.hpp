#pragma once

#include <unordered_map>
#include <string>
#include <common_components.hpp>

extern const uint8_t _binary_makefile_dependencies_dat_start[];
extern const uint8_t _binary_makefile_dependencies_dat_end[];
extern const uint8_t _binary_makefile_target_names_dat_start[];
extern const uint8_t _binary_makefile_target_names_dat_end[];
// extern const uint8_t _binary_scc_dot_start[];
// extern const uint8_t _binary_scc_dot_end[];
extern const uint8_t _binary_data3_txt_start[];
extern const uint8_t _binary_data3_txt_end[];
extern const uint8_t _binary_max_flow_dat_start[];
extern const uint8_t _binary_max_flow_dat_end[];
extern const uint8_t _binary_target_compile_costs_dat_start[];
extern const uint8_t _binary_target_compile_costs_dat_end[];
extern const uint8_t _binary_ospf_graph_dot_start[];
extern const uint8_t _binary_ospf_graph_dot_end[];
extern const uint8_t _binary_kevin_bacon_dat_start[];
extern const uint8_t _binary_kevin_bacon_dat_end[];
extern const uint8_t _binary_kevin_bacon2_dat_start[];
extern const uint8_t _binary_kevin_bacon2_dat_end[];
extern const uint8_t _binary_graphviz_example_dot_start[];
extern const uint8_t _binary_graphviz_example_dot_end[];
extern const uint8_t _binary_edge_iterator_constructor_dat_start[];
extern const uint8_t _binary_edge_iterator_constructor_dat_end[];
extern const uint8_t _binary_boost_web_dat_start[];
extern const uint8_t _binary_boost_web_dat_end[];
extern const uint8_t _binary_bcsstk01_rsa_start[];
extern const uint8_t _binary_bcsstk01_rsa_end[];
extern const uint8_t _binary_bcsstk01_start[];
extern const uint8_t _binary_bcsstk01_end[];

static const std::unordered_map<std::string, EmbeddedFile> embedded_files = {
    { "makefile-dependencies.dat",
        { _binary_makefile_dependencies_dat_start,
          _binary_makefile_dependencies_dat_end } },

    { "makefile-target-names.dat",
        { _binary_makefile_target_names_dat_start,
          _binary_makefile_target_names_dat_end } },
    
    // { "scc.dot",
    //     { _binary_scc_dot_start,
    //       _binary_scc_dot_end } },

    { "data3.txt",
        { _binary_data3_txt_start,
          _binary_data3_txt_end } },
    
    { "max_flow.dat",
        { _binary_max_flow_dat_start,
          _binary_max_flow_dat_end } },
    
    { "target-compile-costs.dat",
        { _binary_target_compile_costs_dat_start,
          _binary_target_compile_costs_dat_end } },
    
    { "figs/ospf-graph.dot",
        { _binary_ospf_graph_dot_start,
          _binary_ospf_graph_dot_end } },
    
    { "kevin-bacon.dat",
        { _binary_kevin_bacon_dat_start,
          _binary_kevin_bacon_dat_end } },

    { "kevin-bacon2.dat",
        { _binary_kevin_bacon2_dat_start,
          _binary_kevin_bacon2_dat_end } },
    
    { "graphviz_example.dot",
        { _binary_graphviz_example_dot_start,
          _binary_graphviz_example_dot_end } },
    
    { "edge_iterator_constructor.dat",
        { _binary_edge_iterator_constructor_dat_start,
          _binary_edge_iterator_constructor_dat_end } },
    
    { "boost_web.dat",
        { _binary_boost_web_dat_start,
          _binary_boost_web_dat_end } },
    
    { "bcsstk01.rsa",
        { _binary_bcsstk01_rsa_start,
          _binary_bcsstk01_rsa_end } },

    { "bcsstk01",
        { _binary_bcsstk01_start,
          _binary_bcsstk01_end } },
};
