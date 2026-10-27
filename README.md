# ESP32 学习手记

用一个个可运行的小案例，记录个人学习 ESP32 / MicroPython 的过程。

**教程入口：[index.html](index.html)**。在文件管理器中双击打开即可离线阅读，无需网站构建工具。

## 学习顺序

1. [环境准备](docs/setup.html)：Python 工具、串口识别、首次安装 MicroPython。
2. [案例 01：点亮第一盏 LED](examples/01-led-blink/index.html)：D2 / GPIO2 亮 1 秒、灭 1 秒。
3. [案例 02：Wi-Fi 网页控制 LED](examples/02-wifi-led/index.html)：连接 2.4 GHz Wi-Fi，通过局域网网页开关 LED。
4. [案例 03：手机 BLE 控制 LED](examples/03-bluetooth-led/index.html)：手机通过 BLE GATT 写入开关指令。
5. [案例 04：网页温湿度监测](examples/04-temperature-humidity/index.html)：DHT11 接入 D2/GPIO2，网页自动显示温湿度。
6. [记录新案例](docs/contributing.html)：模板、记录规范与分享方法。

实测起点：macOS、Python 3.12.2、ESP32-D0WD-V3 / 4 MB Flash、MicroPython 1.29.0。其他板型先核对引脚与固件。Windows / Linux 操作差异已写入环境教程，尚未实机验证。

## 目录

```text
index.html                         教程首页
examples/
  01-led-blink/                     独立脚本 + HTML 教程 + case.json
  02-wifi-led/                      独立脚本 + HTML 教程 + 配置模板 + case.json
  03-bluetooth-led/                 BLE 脚本 + HTML 教程 + case.json
  04-temperature-humidity/          DHT11 脚本 + HTML 教程 + case.json
config/wifi_config.py               私人 Wi-Fi 配置，不分享
scripts/device.py                  电脑端串口 / 上传工具
scripts/check_tutorial.py           文档链接与公开文件检查
scripts/package_tutorial.py         生成不含私人配置的分享包
docs/                              环境准备、扩展指南、样式与组织设计
templates/case/                     下一个案例的起点
tests/                             电脑端工具检查
firmware/                          本地固件镜像及来源说明
backups/                           本地历史文件与设备上传前备份，不分享
```

## 已有环境快速使用

从项目根目录执行；请把示例端口替换为实际端口。命令块不含 zsh 注释行。

```bash
source .venv/bin/activate
python scripts/device.py ports
python scripts/device.py deploy 01 --port /dev/cu.usbserial-0001
```

案例 02：首次使用先把 `examples/02-wifi-led/wifi_config.example.py` 复制成 `config/wifi_config.py` 并填写凭据。已有配置请保留。

```bash
python scripts/device.py deploy 02 --port /dev/cu.usbserial-0001 --repl
```

启动后串口输出 `Open in browser: http://设备IP/`，用浏览器打开这个地址。Ctrl-] 退出串口终端。

案例 03 可使用 nRF Connect for Mobile；nRF Connect for Desktop 也可控制，但需要兼容的 Nordic DK / USB Dongle 作为本地 BLE Adapter：

```bash
python scripts/device.py deploy 03 --port /dev/cu.usbserial-0001 --repl
```

手机端扫描并连接 `ESP32-LED-03`，向 FFF0 服务下的 FFF1 特征值写入 `on` 或 `off`。Desktop 的 Adapter 要求和操作步骤见案例教程。

案例 04：首次使用确认 `config/wifi_config.py` 已填写本人 Wi-Fi 配置，部署后按串口打印的 IP 打开温湿度网页：

```bash
python scripts/device.py deploy 04 --port /dev/cu.usbserial-0001 --repl
```

DHT11 约每 2.5 秒采样一次，网页状态每秒刷新。完整接线和供电说明见案例教程。
`--dry-run` 只检查文件和显示上传路径，不连接设备。

上传工具会中断板上当前程序，备份将被替换的同名文件，上传临时文件并核对 SHA-256，全部通过后替换文件、重启。选择案例会替换板上的 `main.py`；它不删除其他文件，也不擦除固件。多文件替换不是断电原子事务，异常时应修正问题并重新部署，不能把中途失败当作完成。

## 文件位置与设备部署

- 原根目录 `main.py` → `examples/02-wifi-led/main.py`，内容保持一致。
- 原根目录 `wifi_config.py` → `config/wifi_config.py`，保留已有凭据。
- 旧文件快照：`backups/before-tutorial-20261027/`。
- 每个案例都是完整的设备程序；根目录不再放容易混淆的活动 `main.py`。
- 案例 04 已部署到本机开发板；切换案例会替换板上 `main.py`，上传工具会先在本地备份被替换文件。

## 检查与分享

```bash
python -m unittest discover -s tests -v
python scripts/check_tutorial.py
python scripts/package_tutorial.py
```

分享 `dist/esp32-learning-tutorial.zip`。脚本只打包公开文件，不含 Wi-Fi 密码、.venv、备份、固件二进制或日志。请勿直接压缩整个工作目录。

教程中的历史验证与本次本地检查分开记录。实际硬件现象由每个案例的验收清单确认。
