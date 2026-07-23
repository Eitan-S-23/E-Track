# 任务：修改 keil_uvprojx2cmake.py，使生成的 CMakeLists.txt 消除绝对路径（支持 CI），且不影响现有 VSCode 任务构建

## 背景

`keil_uvprojx2cmake.py` 从 `D:\github\my\E-Track\MDK-ARM_F435\proj.uvprojx` 生成
`D:\github\my\E-Track\MDK-ARM_F435\cmake-generated\CMakeLists.txt`（及 `cmake/` 目录辅助文件）。
E-Track 仓库即将启用 GitHub Actions 云端编译：runner 每次全新 checkout 到随机路径
（ubuntu 为 `/home/runner/work/...`），生成物中的本机绝对路径会导致 CI 构建全部失败。

已在 E-Track 仓库实测验证过一版手工移植（configure 通过、可编译），完整参考件在：
`D:\github\my\E-Track\.claude\CMakeLists-portable-reference.txt`
（与当前脚本原始输出 `MDK-ARM_F435\cmake-generated\CMakeLists.txt` 逐行 diff 即可看到全部期望改动）。
你的任务是把这些改动落实到**脚本的生成逻辑**里，而不是手改生成物。

## 硬性约束：不得破坏现有 VSCode 任务

`D:\github\my\E-Track\.vscode\tasks.json` 依赖以下事实，全部不能变：
- 源目录：`MDK-ARM_F435/cmake-generated`；构建目录：其下 `build-gcc`（Debug）与 `build-gcc-release`（Release），Ninja 生成器。
- 目标名：`X_Track`、`X_Track_artifacts`、`clean`。
- 产物名：`X-Track.elf` / `X-Track.hex` / `X-Track.bin`（在构建目录根）。
- `build-gcc/compile_commands.json` 会被任务复制到仓库根 `compile_commands.json`，生成逻辑中的
  `CMAKE_EXPORT_COMPILE_COMMANDS` 与相关 copy 逻辑必须保留。
- 本地 Windows（工具链在 `D:/singlechip/gcc+gdb+openocd/tools/arm-gnu-toolchain-13.3.rel1-ming`，
  经 PATH 或 toolchain 文件发现）构建行为与产物必须与现状一致。

## 需要修改的五类生成逻辑

### 1) 项目源文件与 include 路径（46 处）：绝对 → `${CMAKE_CURRENT_LIST_DIR}` 相对
现状（脚本输出）：
```cmake
"D:/github/my/E-Track/USER/HAL"
"D:/github/my/E-Track/ArduinoAPI/Arduino.c"
```
期望输出：
```cmake
"${CMAKE_CURRENT_LIST_DIR}/../../USER/HAL"
"${CMAKE_CURRENT_LIST_DIR}/../../ArduinoAPI/Arduino.c"
```
实现要点：脚本已知 uvprojx 路径与生成目录路径，对每个解析出的源/头路径，先解析为绝对路径，
再计算**相对于生成的 CMakeLists.txt 所在目录**的相对路径，输出为
`${CMAKE_CURRENT_LIST_DIR}/<relpath>`（POSIX 分隔符）。仅当路径不在仓库树内时才保留绝对路径并打印警告。
注意：源文件位于源树外（上级目录）时 CMake 对象路径会出现 `D_/` 风格前缀，这是 CMake 正常行为，
配合已有的 `CMAKE_OBJECT_PATH_MAX 140` 与 `CMAKE_NINJA_FORCE_RESPONSE_FILE` 即可，无需处理。

### 2) Keil PACK 头目录（3 处）：映射到仓库 vendor 目录
现状：
```cmake
"D:/install/keil5 mdk/ARM/PACK/ARM/CMSIS/5.6.0/CMSIS/Include"
"D:/install/keil5 mdk/ARM/PACK/ArteryTek/AT32F435_437_DFP/2.2.6/Device/Firmware/Peripherals/inc"
"D:/install/keil5 mdk/ARM/PACK/ArteryTek/AT32F435_437_DFP/2.2.6/Device/Include"
```
期望输出（这三个目录的内容已经拷贝进 E-Track 仓库，路径如下，直接映射）：
```cmake
"${CMAKE_CURRENT_LIST_DIR}/../../vendor/CMSIS/Include"
"${CMAKE_CURRENT_LIST_DIR}/../../vendor/AT32F435_437_DFP/Peripherals/inc"
"${CMAKE_CURRENT_LIST_DIR}/../../vendor/AT32F435_437_DFP/Device/Include"
```
实现要点：建议做成可配置的「PACK 前缀 → 仓库目录」映射表（CLI 参数或脚本内配置），
匹配不到映射的 PACK 路径保留原样并警告，提示用户补充 vendor 拷贝。

### 3) 工具链 C++ multilib 头（2 处 `-isystem`）：绝对 → configure 时动态推导
现状：
```cmake
"$<$<COMPILE_LANGUAGE:CXX>:SHELL:-isystem D:/singlechip/gcc+gdb+openocd/tools/arm-gnu-toolchain-13.3.rel1-ming/arm-none-eabi/include/c++/13.3.1/arm-none-eabi/thumb/v7+fp/hard>"
"$<$<COMPILE_LANGUAGE:CXX>:SHELL:-isystem D:/singlechip/gcc+gdb+openocd/tools/arm-gnu-toolchain-13.3.rel1-ming/arm-none-eabi/include/c++/13.3.1/arm-none-eabi>"
```
**不能直接删除**：已实测删除后编译报 `bits/c++config.h: No such file or directory`
（arm-gnu-toolchain 13.3.rel1 的 multilib C++ 头不会被 g++ 驱动自动搜索）。
期望输出（在 `target_compile_options` 之前生成推导段）：
```cmake
execute_process(COMMAND ${CMAKE_CXX_COMPILER} -print-sysroot
    OUTPUT_VARIABLE ARM_GCC_SYSROOT OUTPUT_STRIP_TRAILING_WHITESPACE)
execute_process(COMMAND ${CMAKE_CXX_COMPILER} -dumpfullversion
    OUTPUT_VARIABLE ARM_GCC_VERSION OUTPUT_STRIP_TRAILING_WHITESPACE)
set(ARM_GXX_STDINC "${ARM_GCC_SYSROOT}/include/c++/${ARM_GCC_VERSION}")

target_compile_options(X_Track PRIVATE
    "$<$<COMPILE_LANGUAGE:CXX>:SHELL:-isystem ${ARM_GXX_STDINC}/arm-none-eabi/thumb/v7+fp/hard>"
    "$<$<COMPILE_LANGUAGE:CXX>:SHELL:-isystem ${ARM_GXX_STDINC}/arm-none-eabi>"
    ...)
```
（`-dumpfullversion` 在该工具链输出 `13.3.1`，已实测。）
更通用的做法：multilib 子目录 `thumb/v7+fp/hard` 可用
`${CMAKE_CXX_COMPILER} <当前-m标志> -print-multi-directory` 推导；若脚本已知 CPU/FPU 配置，
按现有方式生成固定子目录亦可接受。

### 4) 强制包含头（1 处 `-include`）：绝对 → `${CMAKE_CURRENT_LIST_DIR}`
现状：
```cmake
"$<$<COMPILE_LANGUAGE:C,CXX>:SHELL:-include D:/github/my/E-Track/MDK-ARM_F435/cmake-generated/cmake/gcc_compat.h>"
```
期望：
```cmake
"$<$<COMPILE_LANGUAGE:C,CXX>:SHELL:-include ${CMAKE_CURRENT_LIST_DIR}/cmake/gcc_compat.h>"
```

### 5) artifacts 步骤跨平台化（Linux runner 无 cmd）
现状：configure 期 `file(WRITE ...run_artifacts.bat)` 生成 Windows 批处理，
`X_Track_artifacts` 目标用 `COMMAND cmd /c "${ARTIFACT_SCRIPT}"` 执行 —— Linux runner 上不可用
（bat 内容本身用的就是 `${CMAKE_OBJCOPY}`/`${CMAKE_SIZE}`，展开后写死绝对路径，本地无碍）。
期望：改为跨平台的 custom target/command 直接调 CMake 变量，例如：
```cmake
add_custom_target(X_Track_artifacts ALL
    COMMAND ${CMAKE_OBJCOPY} -O ihex $<TARGET_FILE:X_Track> ${HEX_FILE}
    COMMAND ${CMAKE_OBJCOPY} -O binary $<TARGET_FILE:X_Track> ${BIN_FILE}
    COMMAND ${CMAKE_SIZE} --format=berkeley $<TARGET_FILE:X_Track>
    COMMAND ${CMAKE_COMMAND} -E touch ${ARTIFACT_STAMP}
    COMMAND ${CMAKE_COMMAND} -E copy_if_different compile_commands.json ${COMPILE_COMMANDS_COPY_TARGET}
    DEPENDS X_Track
    WORKING_DIRECTORY "${CMAKE_CURRENT_BINARY_DIR}"
    VERBATIM)
```
保留目标名 `X_Track_artifacts` 与产物名不变（VSCode 任务依赖）。
`copy_if_different` 在 compile_commands.json 不存在时会失败，需保留现有 `if exist` 语义
（可用 `$<$<...>>` 不易表达，允许拆成脚本文件或用 `cmake -E true` 兜底；Windows 本地行为不得回退）。

## 附带修正（同源小问题）

- `cmake/arm-none-eabi-toolchain.cmake` 若含本机工具链绝对路径回退逻辑，保留「先 PATH 查找、
  找不到再用可选的 `ARM_TOOLCHAIN_ROOT` 缓存变量」的顺序，不要写死盘符。
- 转换报告/校验 JSON（`conversion-report.json`、`build-validation.json`）里的绝对路径仅是记录，
  不影响构建，可不处理。

## 验收标准（全部满足才算完成）

1. 重新运行转换脚本生成后：`grep -c "D:/" MDK-ARM_F435/cmake-generated/CMakeLists.txt` 为 0
   （注释行除外）。
2. 本地 VSCode 任务链 `Configure GCC Debug → Build GCC Debug（X_Track_artifacts）` 全部成功，
   `build-gcc/X-Track.bin` 尺寸与改动前一致（当前基线：603,112 字节）。
3. 模拟 CI 全新构建通过：
   ```
   cmake -S MDK-ARM_F435/cmake-generated -B <全新临时目录> -G Ninja -DCMAKE_BUILD_TYPE=Release
   cmake --build <全新临时目录> --target X_Track_artifacts --parallel
   ```
   且该命令序列在把仓库复制/克隆到**任意其他路径**后同样通过（验证无路径耦合）。
4. `Rebuild GCC Debug`（--clean-first）与 `Clean GCC Debug` 任务行为不变。
5. 对照参考件 `D:\github\my\E-Track\.claude\CMakeLists-portable-reference.txt`：
   五类改动全部体现在生成逻辑中（实现方式可优于参考件，语义等价即可）。
