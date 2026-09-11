#pragma once

#include <string>
#include <vector>

#include "boost/json.hpp"

#include "training_ui.hpp"

struct TrainingSnapshot {
    std::string state;
    std::string session_id;
    std::string course_id;
    std::string instructor_name;
    int org_id = 0;
    int step_index = 0;
    int step_count = 0;
    int mark_step = 1;
    int mark_steps = 1;
    bool pull_users = true;
};

bool training_json_string(const boost::json::object &obj, const char *key, std::string &out);
int training_json_int(const boost::json::object &obj, const char *key, int fallback);
bool training_json_bool(const boost::json::object &obj, const char *key, bool fallback);
std::string training_detail_code(const std::string &body);
bool training_parse_snapshot(const std::string &body, TrainingSnapshot &out);
bool training_session_active(const TrainingSnapshot &snap);
bool training_can_steer(const TrainingSnapshot &snap, int delta);
bool training_http_json(
    const std::string &token,
    const char *method,
    const std::string &path,
    const std::string &body,
    int &status,
    std::string &response
);
bool training_load_orgs(const std::string &token, std::vector<TrainingOrgItem> &orgs, int &status);
bool training_load_courses(const std::string &token, std::vector<TrainingCourseItem> &courses, int &status);
bool training_fetch_ready(const std::string &token, int org_id, int &teacher_total);
bool training_fetch_active(const std::string &token, int org_id, TrainingSnapshot &out, int &status);
std::string training_session_url(const TrainingSnapshot &snap, const char *tail);
