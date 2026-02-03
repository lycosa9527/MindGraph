idf_component_register(
    SRCS "PCF85063.cpp"
    INCLUDE_DIRS "." "../../main"
    PRIV_REQUIRES driver esp_driver_i2c main
)
