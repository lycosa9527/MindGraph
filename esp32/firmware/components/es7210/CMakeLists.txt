idf_component_register(
    SRCS "es7210_driver.cpp"
    INCLUDE_DIRS "." "../../main"
    PRIV_REQUIRES driver esp_driver_i2c esp_driver_i2s main
)
