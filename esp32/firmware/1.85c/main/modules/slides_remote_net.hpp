#pragma once

#include <string>

struct SlidesSnapshot {
    std::string state;
    std::string session_id;
    std::string title;
    std::string traversal;
    int slide_index = 0;
    int slide_count = 0;
    bool autoplay = false;
    bool can_prev = false;
    bool can_next = false;
};

bool slides_http_json(
    const std::string &token,
    const char *method,
    const std::string &path,
    const std::string &body,
    int &status,
    std::string &response
);
bool slides_parse_snapshot(const std::string &body, SlidesSnapshot &out);
bool slides_session_live(const SlidesSnapshot &snap);
bool slides_fetch_active(const std::string &token, SlidesSnapshot &out, int &status);
bool slides_post_command(const std::string &token, const std::string &json, int &status);
