# 固件来源

本项目曾使用 MicroPython 1.29.0 的经典 ESP32 通用固件：

- 板型页面：https://micropython.org/download/ESP32_GENERIC/
- 下载：https://micropython.org/resources/firmware/ESP32_GENERIC-20260824-v1.29.0.bin
- 本地文件 SHA-256：`e67ad6015a0a504c1fec9aa9bbf589d0432ed28e62546f4f8dd8a147f8bd95f6`

SHA-256 是本次下载的本地校验记录，不替代官方签名验证。二进制文件不进入分享包；学习者按自己的芯片型号下载。
C3 / S3 等型号不能直接套用经典 ESP32 固件或刷写地址。

首次刷写步骤见 `docs/setup.html`。以后切换案例只上传 Python 文件，无需重新刷固件。
本地 flash.log 记录过固件写入哈希校验成功；原 Flash 备份失败，不存在可宣称有效的原固件完整备份。
