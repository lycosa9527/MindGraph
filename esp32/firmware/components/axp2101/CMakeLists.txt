idf_component_register(
    SRCS "AXP2101.cpp" "i2c_bus_manager.cpp"
    INCLUDE_DIRS "." "../../main"
    PRIV_REQUIRES driver esp_driver_i2c main
)
