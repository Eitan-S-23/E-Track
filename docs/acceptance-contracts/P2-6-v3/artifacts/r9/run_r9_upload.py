# -*- coding: utf-8 -*-
"""R9 上传 wrapper：把 BAD-2.8.2.etu 经 tests/ota/p2_6_rtt_sd_uploader.py 传到 SD 新路径。

仓库 uploader/driver 为冻结测试基建，本轮零改动；此处运行时 monkey-patch 两道
冻结门禁（等效替代，保持 fail-closed，将在证据文档登记）：
1. uploader.FROZEN_ASSETS 注入 BAD-2.8.2.etu 的 SHA-256（dict 注入，未知输入仍拒绝）；
2. driver.FROZEN_V280_IMAGE_SHA256 常量按板卡现运行 v2.8.1 冻结资产登记
   （load_frozen_device_header 的校验逻辑零改动，仅换冻结哈希——板卡自 R8 升级后
   运行 v2.8.1，设备镜像传入 v2.8.1 finalized bin）。
"""
import sys

sys.path.insert(0, "tests/ota")

import p2_6_rtt_sd_uploader as uploader
import p2_6_rtt_ota_driver as driver

BAD_ETU_SHA256 = "EA7C5CA22E572BFB2D211E21C9475091D9F68725F862939B71FA874E5FA24C30"
V281_FINALIZED_SHA256 = (
    "A2D3083B25EE32813EFF6CC1BD0CF77CE235FD03BF79947C08B8A3C815D58E00"
)

uploader.FROZEN_ASSETS[BAD_ETU_SHA256] = "FULL"
driver.FROZEN_V280_IMAGE_SHA256 = V281_FINALIZED_SHA256

sys.argv = [
    "p2_6_rtt_sd_uploader.py",
    "--input", ".cache/p2-6-sd-r9-20260901-01-implementation/tmp/BAD-2.8.2.etu",
    # 第 1 次 (-01) 上传在 Windows 经 USB MSC 挂载 SD 期间执行, 设备侧 SDIO 被
    # MSC 独占, 首块写入 I/O 失败, 卡上遗留 0 字节半成品 (不可覆盖, uploader 拒绝
    # 既有目标)。本次 (-02) 为释放 MSC 后的重试, 新路径绕开半成品。
    "--mcu-path", "/P2-6A-FULL-v2.8.2-BAD-R9-20260901-02.etu",
    "--output-prefix", "p2-6-sd-r9-bad-upload-hw-02",
    "--device-image", ".cache/p2-6-sd-ota/assets/X-Track-App-GCC-p2-6a-test-v2.8.1.finalized.bin",
    "--log-dir", ".cache/p2-6-sd-r9-20260901-01-implementation/logs",
    "--tmp-dir", ".cache/p2-6-sd-r9-20260901-01-implementation/tmp",
    "--timeout", "600",
]

raise SystemExit(uploader.main())
