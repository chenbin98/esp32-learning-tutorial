"""只打包公开教程文件；不递归收集个人目录。"""
from pathlib import Path
import zipfile

ROOT = Path(__file__).resolve().parents[1]


def public_files(root=ROOT):
    exact = ['index.html', 'README.md', '.gitignore', 'requirements.txt',
             'config/README.md', 'firmware/README.md']
    paths = {root / name for name in exact}
    for pattern in ('docs/*.html', 'docs/*.md', 'docs/assets/*.css', 'docs/assets/*.js',
                    'examples/*/index.html', 'examples/*/main.py', 'examples/*/case.json',
                    'examples/*/*.example.py', 'scripts/*.py', 'tests/*.py',
                    'templates/case/*.html', 'templates/case/*.py', 'templates/case/*.json'):
        paths.update(root.glob(pattern))
    return sorted(p for p in paths if p.is_file() and not p.is_symlink())


def main():
    target = ROOT / 'dist' / 'esp32-learning-tutorial.zip'
    target.parent.mkdir(exist_ok=True)
    with zipfile.ZipFile(target, 'w', zipfile.ZIP_DEFLATED) as archive:
        for path in public_files():
            archive.write(path, 'esp32-learning/' + path.relative_to(ROOT).as_posix())
    print('分享包：', target)
    print('仅包含教程、示例代码和工具；不包含个人 Wi-Fi 配置、环境、备份、固件镜像或日志。')


if __name__ == '__main__':
    main()
