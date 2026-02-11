cmake_minimum_required(VERSION 3.15)
project(trading_engine VERSION 1.0.0 LANGUAGES CXX)

# C++17 standard
set(CMAKE_CXX_STANDARD 17)
set(CMAKE_CXX_STANDARD_REQUIRED ON)

# Windows-specific settings
if(MSVC)
    add_compile_options(/W4 /O2 /EHsc)
    add_definitions(-D_USE_MATH_DEFINES)
endif()

# Find Python and pybind11
find_package(Python3 REQUIRED COMPONENTS Interpreter Development)
find_package(pybind11 CONFIG REQUIRED)

# Source files
set(SOURCES
    src/pattern_recognition.cpp
    src/order_book.cpp
    src/indicators.cpp
    src/position_sizer.cpp
    src/kalman_filter.cpp
)

# Header files
set(HEADERS
    include/pattern_recognition.hpp
    include/order_book.hpp
    include/indicators.hpp
    include/position_sizer.hpp
    include/kalman_filter.hpp
    include/common.hpp
)

# Create the Python module
pybind11_add_module(trading_engine
    ${SOURCES}
    bindings/python_bindings.cpp
)

target_include_directories(trading_engine PRIVATE 
    ${CMAKE_CURRENT_SOURCE_DIR}/include
)

# Install target
install(TARGETS trading_engine
    LIBRARY DESTINATION ${Python3_SITELIB}
)

# Build instructions message
message(STATUS "")
message(STATUS "=== Trading Engine Build Configuration ===")
message(STATUS "Python: ${Python3_EXECUTABLE}")
message(STATUS "Python Version: ${Python3_VERSION}")
message(STATUS "pybind11 Version: ${pybind11_VERSION}")
message(STATUS "Build Type: ${CMAKE_BUILD_TYPE}")
message(STATUS "")
message(STATUS "Build commands:")
message(STATUS "  mkdir build && cd build")
message(STATUS "  cmake .. -G \"Visual Studio 17 2022\" -A x64")
message(STATUS "  cmake --build . --config Release")
message(STATUS "")
