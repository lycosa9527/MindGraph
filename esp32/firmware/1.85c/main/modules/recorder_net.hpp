#pragma once

#include <string>

std::string recorder_net_ws_url();
std::string recorder_net_default_title();
bool recorder_net_finish(
    const std::string &token,
    const std::string &transcript,
    const std::string &title,
    bool generate,
    const std::string &diagram_id,
    std::string &out_id,
    std::string &out_title
);
