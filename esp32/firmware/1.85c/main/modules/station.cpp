#include "sdkconfig.h"

#include <string>
#include <string_view>

#include "boost/chrono.hpp"
#include "boost/json/array.hpp"
#include "boost/thread.hpp"
#include "brookesia/lib_utils/describe_helpers.hpp"
#include "brookesia/lib_utils/thread_config.hpp"
#include "brookesia/service_helper/network/sntp.hpp"
#include "brookesia/service_helper/network/wifi.hpp"
#include "brookesia/service_helper/system/storage.hpp"
#include "brookesia/service_manager/helper/base.hpp"
#include "brookesia/service_manager/service/manager.hpp"
#include "private/utils.hpp"
#include "station.hpp"

using namespace esp_brookesia;
using WifiHelper = service::helper::Wifi;
using SNTPHelper = service::helper::SNTP;
using StorageHelper = service::helper::Storage;

namespace {

constexpr uint32_t STATION_TIMEOUT_MS = 8000;
constexpr uint32_t STATION_JOIN_POLL_MS = 250;
constexpr uint32_t STATION_JOIN_ATTEMPTS = 40;
constexpr uint32_t STATION_HOLD_POLL_MS = 50;
constexpr uint32_t STATION_HOLD_ATTEMPTS = 40;

service::ServiceBinding g_storage_binding;
service::ServiceBinding g_wifi_binding;
service::ServiceBinding g_sntp_binding;

#if defined(CONFIG_MINDGRAPH_STA_SSID)
constexpr const char *kStationSsid = CONFIG_MINDGRAPH_STA_SSID;
#else
constexpr const char *kStationSsid = "";
#endif
#if defined(CONFIG_MINDGRAPH_STA_PASSWORD)
constexpr const char *kStationPassword = CONFIG_MINDGRAPH_STA_PASSWORD;
#else
constexpr const char *kStationPassword = "";
#endif
#if defined(CONFIG_MINDGRAPH_STA_TIMEZONE)
constexpr const char *kStationTimezone = CONFIG_MINDGRAPH_STA_TIMEZONE;
#else
constexpr const char *kStationTimezone = "CST-8";
#endif

bool hold_service(service::ServiceBinding &slot, const char *name)
{
    if (slot.get_service() == nullptr) {
        slot = service::ServiceManager::get_instance().bind(name);
    }
    if (slot.get_service() == nullptr) {
        BROOKESIA_LOGW("Failed to bind service '%1%' for boot station", name);
        return false;
    }
    for (uint32_t attempt = 0; attempt < STATION_HOLD_ATTEMPTS; ++attempt) {
        if (slot.is_valid()) {
            return true;
        }
        boost::this_thread::sleep_for(boost::chrono::milliseconds(STATION_HOLD_POLL_MS));
    }
    BROOKESIA_LOGW("Service '%1%' is not running after bind", name);
    return false;
}

bool seed_wifi_preference()
{
    if (!StorageHelper::is_available()) {
        BROOKESIA_LOGW("Storage service is not available, skip Wi-Fi preference seed");
        return true;
    }
    if (!hold_service(g_storage_binding, StorageHelper::get_name().data())) {
        BROOKESIA_LOGW("Failed to hold Storage for Wi-Fi preference seed");
        return true;
    }

    auto nspace = StorageHelper::make_kv_namespace({"app.settings"}, ".", STATION_TIMEOUT_MS);
    if (!nspace) {
        BROOKESIA_LOGW("Failed to make Settings namespace for Wi-Fi preference: %1%", nspace.error());
        return true;
    }
    auto key = StorageHelper::make_kv_key({"WifiEnabled"}, ".", STATION_TIMEOUT_MS);
    if (!key) {
        BROOKESIA_LOGW("Failed to make Settings key for Wi-Fi preference: %1%", key.error());
        return true;
    }

    auto save = StorageHelper::save_key_value(nspace->name, key->name, true, STATION_TIMEOUT_MS);
    if (!save) {
        BROOKESIA_LOGW("Failed to seed Wi-Fi enabled preference: %1%", save.error());
        return true;
    }

    BROOKESIA_LOGI("Boot Wi-Fi preference seeded on");
    return true;
}

bool trigger_wifi_action(WifiHelper::GeneralAction action, const char *ssid)
{
    const auto timeout = service::helper::Timeout(STATION_TIMEOUT_MS);
    auto result = WifiHelper::call_function_sync<void>(
                      WifiHelper::FunctionId::TriggerGeneralAction,
                      std::string(BROOKESIA_DESCRIBE_TO_STR(action)),
                      timeout
                  );
    if (!result) {
        BROOKESIA_LOGW(
            "Failed to trigger Wi-Fi %1% for boot AP '%2%': %3%",
            BROOKESIA_DESCRIBE_TO_STR(action),
            ssid,
            result.error()
        );
        return false;
    }
    return true;
}

bool wifi_state_can_join(std::string_view state)
{
    return state == BROOKESIA_DESCRIBE_TO_STR(WifiHelper::GeneralState::Started)
           || state == BROOKESIA_DESCRIBE_TO_STR(WifiHelper::GeneralState::Connecting)
           || state == BROOKESIA_DESCRIBE_TO_STR(WifiHelper::GeneralState::Connected);
}

std::string read_wifi_state()
{
    const auto timeout = service::helper::Timeout(STATION_TIMEOUT_MS);
    auto state = WifiHelper::call_function_sync<std::string>(
                     WifiHelper::FunctionId::GetGeneralState,
                     timeout
                 );
    if (!state) {
        BROOKESIA_LOGW("Failed to read Wi-Fi state for boot join: %1%", state.error());
        return {};
    }
    return *state;
}

void join_seeded_ap()
{
    if (!WifiHelper::is_available() || !hold_service(g_wifi_binding, WifiHelper::get_name().data())) {
        BROOKESIA_LOGW("Wi-Fi service unavailable for delayed boot join");
        return;
    }

    for (uint32_t attempt = 0; attempt < STATION_JOIN_ATTEMPTS; ++attempt) {
        const auto state = read_wifi_state();
        if (state == BROOKESIA_DESCRIBE_TO_STR(WifiHelper::GeneralState::Connected)) {
            BROOKESIA_LOGI("Boot Wi-Fi already connected to AP '%1%'", kStationSsid);
            return;
        }
        if (wifi_state_can_join(state)) {
            if (state == BROOKESIA_DESCRIBE_TO_STR(WifiHelper::GeneralState::Connecting)) {
                BROOKESIA_LOGI("Boot Wi-Fi is already joining AP '%1%'", kStationSsid);
                return;
            }
            if (!trigger_wifi_action(WifiHelper::GeneralAction::Connect, kStationSsid)) {
                return;
            }
            BROOKESIA_LOGI("Boot Wi-Fi connect issued for AP '%1%' after state(%2%)", kStationSsid, state);
            return;
        }
        boost::this_thread::sleep_for(boost::chrono::milliseconds(STATION_JOIN_POLL_MS));
    }

    BROOKESIA_LOGW("Boot Wi-Fi did not reach Started before join timeout for AP '%1%'", kStationSsid);
}

void start_join_seeded_ap_task()
{
    BROOKESIA_THREAD_CONFIG_GUARD({
        .name = "mg_sta_join",
        .stack_size = 12 * 1024,
    });
    boost::thread(join_seeded_ap).detach();
}

bool seed_wifi()
{
    if (kStationSsid[0] == '\0') {
        BROOKESIA_LOGI("Lab station SSID is empty, skip boot Wi-Fi seed");
        return true;
    }
    if (!WifiHelper::is_available()) {
        BROOKESIA_LOGW("Wi-Fi service is not available, skip boot station seed");
        return true;
    }
    if (!hold_service(g_wifi_binding, WifiHelper::get_name().data())) {
        BROOKESIA_LOGW("Failed to hold Wi-Fi service for boot station seed");
        return true;
    }

    const auto timeout = service::helper::Timeout(STATION_TIMEOUT_MS);
    auto set_ap = WifiHelper::call_function_sync<void>(
                      WifiHelper::FunctionId::SetConnectAp,
                      std::string(kStationSsid),
                      std::string(kStationPassword),
                      timeout
                  );
    if (!set_ap) {
        BROOKESIA_LOGW("Failed to seed boot AP '%1%': %2%", kStationSsid, set_ap.error());
        return true;
    }

    if (!trigger_wifi_action(WifiHelper::GeneralAction::Start, kStationSsid)) {
        return true;
    }

    start_join_seeded_ap_task();
    BROOKESIA_LOGI(
        "Boot Wi-Fi seed started for AP '%1%' password_len(%2%)",
        kStationSsid,
        std::char_traits<char>::length(kStationPassword)
    );
    return true;
}

bool seed_clock()
{
    if (!SNTPHelper::is_available()) {
        BROOKESIA_LOGW("SNTP service is not available, skip boot clock seed");
        return true;
    }
    if (!hold_service(g_sntp_binding, SNTPHelper::get_name().data())) {
        BROOKESIA_LOGW("Failed to hold SNTP service for boot clock seed");
        return true;
    }

    const auto timeout = service::helper::Timeout(STATION_TIMEOUT_MS);
    auto timezone = SNTPHelper::call_function_sync<void>(
                        SNTPHelper::FunctionId::SetTimezone,
                        std::string(kStationTimezone),
                        timeout
                    );
    if (!timezone) {
        BROOKESIA_LOGW("Failed to set boot timezone '%1%': %2%", kStationTimezone, timezone.error());
    }

    boost::json::array servers;
    servers.emplace_back("ntp.aliyun.com");
    servers.emplace_back("cn.pool.ntp.org");
    servers.emplace_back("pool.ntp.org");
    auto set_servers = SNTPHelper::call_function_sync<void>(
                           SNTPHelper::FunctionId::SetServers,
                           servers,
                           timeout
                       );
    if (!set_servers) {
        BROOKESIA_LOGW("Failed to set boot NTP servers: %1%", set_servers.error());
    }

    auto start = SNTPHelper::call_function_sync<void>(SNTPHelper::FunctionId::Start, timeout);
    if (!start) {
        BROOKESIA_LOGW("Failed to start SNTP after boot seed: %1%", start.error());
        return true;
    }

    BROOKESIA_LOGI("Boot clock seed timezone(%1%)", kStationTimezone);
    return true;
}

} // namespace

bool start_lab_station()
{
    BROOKESIA_CHECK_FALSE_RETURN(seed_wifi_preference(), false, "Failed to seed Wi-Fi preference");
    BROOKESIA_CHECK_FALSE_RETURN(seed_wifi(), false, "Failed to seed boot Wi-Fi");
    BROOKESIA_CHECK_FALSE_RETURN(seed_clock(), false, "Failed to seed boot clock");
    return true;
}
