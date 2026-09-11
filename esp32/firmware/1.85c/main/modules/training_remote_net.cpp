#include "training_remote_net.hpp"

#include "kitty_net.hpp"

namespace {

constexpr size_t k_http_cap = 48 * 1024;

} // namespace

bool training_json_string(const boost::json::object &obj, const char *key, std::string &out)
{
    const auto *field = obj.if_contains(key);
    if (field == nullptr || field->is_null() || !field->is_string()) {
        return false;
    }
    out = std::string(field->as_string().c_str());
    return !out.empty();
}

int training_json_int(const boost::json::object &obj, const char *key, int fallback)
{
    const auto *field = obj.if_contains(key);
    if (field == nullptr || field->is_null()) {
        return fallback;
    }
    if (field->is_int64()) {
        return static_cast<int>(field->as_int64());
    }
    if (field->is_uint64()) {
        return static_cast<int>(field->as_uint64());
    }
    if (field->is_double()) {
        return static_cast<int>(field->as_double());
    }
    return fallback;
}

bool training_json_bool(const boost::json::object &obj, const char *key, bool fallback)
{
    const auto *field = obj.if_contains(key);
    if (field == nullptr || field->is_null() || !field->is_bool()) {
        return fallback;
    }
    return field->as_bool();
}

std::string training_detail_code(const std::string &body)
{
    boost::system::error_code err;
    const auto root = boost::json::parse(body, err);
    if (err || !root.is_object()) {
        return "";
    }
    const auto *detail = root.as_object().if_contains("detail");
    if (detail == nullptr) {
        return "";
    }
    if (detail->is_object()) {
        std::string code;
        training_json_string(detail->as_object(), "code", code);
        return code;
    }
    if (detail->is_string()) {
        return std::string(detail->as_string().c_str());
    }
    return "";
}

bool training_parse_snapshot(const std::string &body, TrainingSnapshot &out)
{
    boost::system::error_code err;
    const auto root = boost::json::parse(body, err);
    if (err || !root.is_object()) {
        return false;
    }
    const auto &obj = root.as_object();
    out = TrainingSnapshot{};
    training_json_string(obj, "state", out.state);
    training_json_string(obj, "session_id", out.session_id);
    training_json_string(obj, "course_id", out.course_id);
    training_json_string(obj, "instructor_name", out.instructor_name);
    out.org_id = training_json_int(obj, "org_id", 0);
    out.step_index = training_json_int(obj, "step_index", 0);
    out.step_count = training_json_int(obj, "step_count", 0);
    out.pull_users = training_json_bool(obj, "pull_users", true);
    const auto *step = obj.if_contains("step");
    if (step != nullptr && step->is_object()) {
        out.mark_step = training_json_int(step->as_object(), "mark_step", 1);
        out.mark_steps = training_json_int(step->as_object(), "mark_steps", 1);
    }
    if (out.mark_step < 1) {
        out.mark_step = 1;
    }
    if (out.mark_steps < 1) {
        out.mark_steps = 1;
    }
    return true;
}

bool training_session_active(const TrainingSnapshot &snap)
{
    return (snap.state == "live" || snap.state == "paused") && !snap.session_id.empty();
}

bool training_can_steer(const TrainingSnapshot &snap, int delta)
{
    if (delta == 0 || snap.course_id.empty()) {
        return false;
    }
    if (delta > 0) {
        return snap.mark_step < snap.mark_steps
            || (snap.step_count > 0 && snap.step_index < snap.step_count - 1);
    }
    return snap.mark_step > 1 || snap.step_index > 0;
}

bool training_http_json(
    const std::string &token,
    const char *method,
    const std::string &path,
    const std::string &body,
    int &status,
    std::string &response
)
{
    return kitty_net_http_json(method, path, body, token, status, response, k_http_cap);
}

bool training_load_orgs(const std::string &token, std::vector<TrainingOrgItem> &orgs, int &status)
{
    std::string body;
    if (!training_http_json(token, "GET", "/api/training/orgs?limit=20", "", status, body)) {
        return false;
    }
    if (status != 200) {
        return false;
    }
    boost::system::error_code err;
    const auto root = boost::json::parse(body, err);
    if (err || !root.is_object()) {
        return false;
    }
    const auto *items = root.as_object().if_contains("items");
    if (items == nullptr || !items->is_array()) {
        return false;
    }
    orgs.clear();
    for (const auto &row : items->as_array()) {
        if (!row.is_object()) {
            continue;
        }
        TrainingOrgItem item;
        item.id = training_json_int(row.as_object(), "id", 0);
        training_json_string(row.as_object(), "name", item.name);
        if (item.id > 0 && !item.name.empty()) {
            orgs.push_back(item);
        }
    }
    return true;
}

bool training_load_courses(const std::string &token, std::vector<TrainingCourseItem> &courses, int &status)
{
    std::string body;
    if (!training_http_json(token, "GET", "/api/training/courses", "", status, body)) {
        return false;
    }
    if (status != 200) {
        return false;
    }
    boost::system::error_code err;
    const auto root = boost::json::parse(body, err);
    if (err || !root.is_object()) {
        return false;
    }
    const auto *items = root.as_object().if_contains("items");
    if (items == nullptr || !items->is_array()) {
        return false;
    }
    courses.clear();
    for (const auto &row : items->as_array()) {
        if (!row.is_object()) {
            continue;
        }
        TrainingCourseItem item;
        training_json_string(row.as_object(), "id", item.id);
        training_json_string(row.as_object(), "title", item.title);
        if (item.id.empty()) {
            continue;
        }
        if (item.title.empty()) {
            item.title = "未命名课程";
        }
        courses.push_back(item);
    }
    return true;
}

bool training_fetch_ready(const std::string &token, int org_id, int &teacher_total)
{
    int status = 0;
    std::string body;
    const std::string path = "/api/training/orgs/" + std::to_string(org_id) + "/ready";
    if (!training_http_json(token, "GET", path, "", status, body) || status != 200) {
        return false;
    }
    boost::system::error_code err;
    const auto root = boost::json::parse(body, err);
    if (err || !root.is_object()) {
        return false;
    }
    teacher_total = training_json_int(root.as_object(), "teacher_total", 0);
    return true;
}

bool training_fetch_active(const std::string &token, int org_id, TrainingSnapshot &out, int &status)
{
    std::string body;
    std::string path = "/api/training/sessions/active";
    if (org_id > 0) {
        path += "?org_id=" + std::to_string(org_id);
    }
    if (!training_http_json(token, "GET", path, "", status, body)) {
        return false;
    }
    if (status != 200) {
        return false;
    }
    return training_parse_snapshot(body, out);
}

std::string training_session_url(const TrainingSnapshot &snap, const char *tail)
{
    return "/api/training/sessions/" + snap.session_id + tail + "?org_id=" + std::to_string(snap.org_id);
}
