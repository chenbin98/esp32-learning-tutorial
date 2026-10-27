"""电脑端工具：列出串口、按案例部署、进入 MicroPython REPL。"""
import argparse
import ast
from datetime import datetime
import hashlib
import json
from pathlib import Path
import subprocess
import sys

ROOT = Path(__file__).resolve().parents[1]


def load_case(case_id, root=ROOT):
    matches = [p for p in (root / "examples").iterdir()
               if p.is_dir() and (p.name == case_id or p.name.startswith(case_id + "-"))]
    if len(matches) != 1:
        raise ValueError("案例编号不存在或不唯一，请使用 01、02 或完整目录名。")
    folder = matches[0]
    manifest = json.loads((folder / "case.json").read_text(encoding="utf-8"))
    files = []
    for section, base in (("files", folder), ("config", root / "config")):
        for source, destination in manifest.get(section, {}).items():
            path = (base / source).resolve()
            if not path.is_relative_to(base.resolve()) or Path(destination).name != destination or destination in ("", ".", ".."):
                raise ValueError("清单中的路径必须在案例或配置目录内，目标必须是文件名。")
            if not path.is_file():
                raise ValueError("缺少文件：%s；案例 02 请先复制并填写配置模板。" % path)
            if path.suffix == ".py":
                try:
                    compile(path.read_bytes(), str(path), "exec")
                except SyntaxError:
                    raise ValueError("Python 语法错误：%s（内容不回显）" % path) from None
            if destination == "wifi_config.py":
                validate_wifi(path)
            files.append((path, destination))
    if "main.py" not in [name for _, name in files]:
        raise ValueError("清单必须包含 main.py。")
    if len({name for _, name in files}) != len(files):
        raise ValueError("清单中有重复的目标文件名。")
    return folder.name, sorted(files, key=lambda item: item[1] == "main.py")


def validate_wifi(path):
    try:
        values = {node.targets[0].id: ast.literal_eval(node.value)
                  for node in ast.parse(path.read_text(encoding="utf-8")).body
                  if isinstance(node, ast.Assign) and isinstance(node.targets[0], ast.Name)}
        ssid, password = values.get("WIFI_SSID"), values.get("WIFI_PASSWORD")
        if not isinstance(ssid, str) or not ssid or ssid == "your-2.4GHz-wifi-name":
            raise ValueError()
        if not isinstance(password, str) or password == "your-wifi-password":
            raise ValueError()
    except (SyntaxError, ValueError, TypeError):
        raise ValueError("请在 config/wifi_config.py 填写有效的 Wi-Fi 配置；密码不会输出。") from None


def mpremote(port, *args, capture=False):
    command = [sys.executable, "-m", "mpremote", "connect", port, *args]
    return subprocess.run(command, check=True, text=True, capture_output=capture)


def deploy(case_id, port, dry_run=False, repl=False):
    name, files = load_case(case_id)
    print("案例：", name)
    for path, destination in files:
        print("  %s -> :%s" % (path.relative_to(ROOT), destination))
    if dry_run:
        print("预览完成；未打开串口，未上传或重启设备。")
        return
    from serial.tools import list_ports
    if port not in [entry.device for entry in list_ports.comports()]:
        raise ValueError("串口不存在：%s；请运行 ports 并检查 USB 数据连接。" % port)
    listing = mpremote(port, "exec", "import os; print(os.listdir())", capture=True).stdout
    existing = ast.literal_eval(listing.strip().splitlines()[-1])
    backup = ROOT / "backups" / (datetime.now().strftime("deploy-%Y%m%d-%H%M%S-%f"))
    backup.mkdir(parents=True)
    for _, destination in files:
        if destination in existing:
            mpremote(port, "fs", "cp", ":" + destination, str(backup / destination))
    for source, destination in files:
        temporary = destination + ".upload"
        mpremote(port, "fs", "cp", str(source), ":" + temporary)
        expression = ("import hashlib, binascii; "
                      "print(binascii.hexlify(hashlib.sha256(open(%r, 'rb').read()).digest()).decode())" % temporary)
        result = mpremote(port, "exec", expression, capture=True).stdout.strip()
        if result != hashlib.sha256(source.read_bytes()).hexdigest():
            raise ValueError("%s 上传校验失败；启动文件未替换，备份在 %s。" % (destination, backup))
    # 全部文件校验通过后再安装，main.py 最后替换。
    expression = "import os; " + "; ".join(
        "os.rename(%r, %r)" % (destination + ".upload", destination) for _, destination in files)
    mpremote(port, "exec", expression)
    print("文件校验通过。原文件备份：", backup.relative_to(ROOT))
    mpremote(port, "reset", *(["+", "repl"] if repl else []))
    print("已上传并重启。程序实际效果请按案例教程验收。")


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    commands = parser.add_subparsers(dest="command", required=True)
    commands.add_parser("ports", help="列出系统当前串口")
    upload = commands.add_parser("deploy", help="备份、上传、校验并重启一个案例")
    upload.add_argument("case", help="01、02 或完整案例目录名")
    upload.add_argument("--port", required=True, help="例如 /dev/cu.usbserial-0001 或 COM3")
    upload.add_argument("--dry-run", action="store_true", help="仅检查文件并预览上传路径")
    upload.add_argument("--repl", action="store_true", help="重启后进入串口终端；Ctrl-] 退出")
    terminal = commands.add_parser("repl", help="打开串口终端；Ctrl-] 退出")
    terminal.add_argument("--port", required=True)
    args = parser.parse_args()
    try:
        if args.command == "ports":
            from serial.tools import list_ports
            ports = list(list_ports.comports())
            for entry in ports:
                print("%s  %s" % (entry.device, entry.description))
            if not ports:
                print("未发现串口，请检查 USB 数据线。")
        elif args.command == "repl":
            mpremote(args.port, "repl")
        else:
            deploy(args.case, args.port, args.dry_run, args.repl)
    except (ValueError, OSError, subprocess.CalledProcessError) as error:
        print("操作失败：", error, file=sys.stderr)
        print("未确认部署成功；请修正问题后重试。", file=sys.stderr)
        return 1
    except KeyboardInterrupt:
        return 130
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
