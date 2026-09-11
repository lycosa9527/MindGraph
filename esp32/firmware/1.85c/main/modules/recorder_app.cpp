#include <memory>
#include <string>

#include "brookesia/system_core/app/iapp.hpp"
#include "private/utils.hpp"

#include "recorder_agent.hpp"
#include "recorder_ui.hpp"

namespace mindgraph::recorder {
namespace {

constexpr const char *k_app_id = "com.mindgraph.recorder";
constexpr const char *k_gui_root = "res/root.json";
constexpr const char *k_flow_id = "main";

class RecorderApp final : public esp_brookesia::system::core::IApp {
public:
    esp_brookesia::system::core::AppManifest get_manifest() const override
    {
        return {
            .id = k_app_id,
            .name = "Voice Notes",
            .localized_names = {
                {"en", "Voice Notes"},
                {"zh_CN", "语音笔记"},
            },
            .version = "0.1.0",
            .kind = esp_brookesia::system::core::AppKind::Native,
            .visible = true,
            .preload_dom = false,
            .icon_id = "launcher_icon",
            .supported_systems = {},
            .icon_path = "res/images/index.json",
            .runtime_type = esp_brookesia::runtime::BackendType::Unknown,
            .app_path = {},
            .entry = {},
            .resource_dir = k_app_id,
            .arguments = {},
        };
    }

    esp_brookesia::system::core::AppGuiDescriptor get_gui_descriptor() const override
    {
        return {
            .root_kind = esp_brookesia::system::core::GuiRootKind::File,
            .root = k_gui_root,
            .resources = {},
            .screen_flows = {
                {
                    .screen_flow = k_flow_id,
                    .layer = esp_brookesia::system::core::GuiAppLayer::AppDefault,
                },
            },
        };
    }

    std::expected<void, std::string> on_start(esp_brookesia::system::core::AppContext &context) override
    {
        (void)context;
        recorder_ui_start();
        recorder_ui_show();
        recorder_agent_start();
        BROOKESIA_LOGI("Recorder app started");
        return {};
    }

    std::expected<void, std::string> on_resume(esp_brookesia::system::core::AppContext &context) override
    {
        return on_start(context);
    }

    std::expected<void, std::string> on_pause(esp_brookesia::system::core::AppContext &context) override
    {
        (void)context;
        recorder_ui_hide();
        recorder_agent_stop();
        BROOKESIA_LOGI("Recorder app paused");
        return {};
    }

    std::expected<void, std::string> on_stop(esp_brookesia::system::core::AppContext &context) override
    {
        (void)context;
        recorder_ui_hide();
        recorder_agent_stop();
        BROOKESIA_LOGI("Recorder app stopped");
        return {};
    }
};

class RecorderAppProvider final : public esp_brookesia::system::core::IAppProvider {
public:
    esp_brookesia::system::core::AppManifest get_manifest() const override
    {
        return RecorderApp().get_manifest();
    }

    std::shared_ptr<esp_brookesia::system::core::IApp> create_app() override
    {
        return std::make_shared<RecorderApp>();
    }
};

BROOKESIA_SYSTEM_CORE_APP_PROVIDER_REGISTER_WITH_SYMBOL(
    RecorderAppProvider,
    "com.mindgraph.recorder",
    recorder_app_provider_symbol
);

} // namespace
} // namespace mindgraph::recorder
