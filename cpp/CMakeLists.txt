# C++ 版跟踪器（E 块）。在 cpp 目录里：
#   cmake -S . -B build                      生成工程（第一次会从 GitHub 下载 googletest）
#   cmake --build build --config Release     编译
#   .\build\Release\test_kalman.exe          跑测试
cmake_minimum_required(VERSION 3.16)
project(tracking_cpp LANGUAGES CXX)

set(CMAKE_CXX_STANDARD 17)
set(CMAKE_CXX_STANDARD_REQUIRED ON)

# 源文件里有中文注释：告诉 MSVC 按 UTF-8 读，不然中文 Windows 会按 GBK 读坏
if(MSVC)
  add_compile_options(/utf-8)
endif()

# 第 0 步：确认编译器能用
add_executable(hello hello.cpp)

# 跟踪器本体：做成一个库（library），测试和以后的 Python 绑定都用它
add_library(tracking src/kalman.cpp)
target_include_directories(tracking PUBLIC include)

# 单元测试：googletest（C++ 里最常用的测试框架，相当于 Python 的 pytest）
if(POLICY CMP0135)
  cmake_policy(SET CMP0135 NEW)
endif()
include(FetchContent)
FetchContent_Declare(googletest
  URL https://github.com/google/googletest/archive/refs/tags/v1.15.2.zip)
set(gtest_force_shared_crt ON CACHE BOOL "" FORCE)   # Windows：gtest 和我们的程序用同一种运行库
FetchContent_MakeAvailable(googletest)

enable_testing()
add_executable(test_kalman tests/test_kalman.cpp)
target_link_libraries(test_kalman tracking GTest::gtest_main)
include(GoogleTest)
gtest_discover_tests(test_kalman)
