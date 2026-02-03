cmake_minimum_required(VERSION 3.16)

# Set project name
set(PROJECT_NAME "mindgraph_esp32")

# Set target to ESP32-S3 BEFORE including project.cmake
set(IDF_TARGET esp32s3)

include($ENV{IDF_PATH}/tools/cmake/project.cmake)
project(${PROJECT_NAME})
