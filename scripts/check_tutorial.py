"""检查离线链接、案例全文代码与分享文件边界。"""
from html.parser import HTMLParser
from pathlib import Path
import ast
import sys
from urllib.parse import unquote, urlsplit
from package_tutorial import ROOT, public_files


class Page(HTMLParser):
    def __init__(self, text):
        super().__init__(convert_charrefs=True)
        self.links, self.ids, self.codes = [], set(), []
        self.code = None
        self.feed(text)
    def handle_starttag(self, tag, attrs):
        attrs = dict(attrs)
        if 'id' in attrs:
            self.ids.add(attrs['id'])
        for key in ('href', 'src'):
            if key in attrs:
                self.links.append(attrs[key])
        if tag == 'code':
            self.code = ''
    def handle_endtag(self, tag):
        if tag == 'code' and self.code is not None:
            self.codes.append(self.code)
            self.code = None
    def handle_data(self, data):
        if self.code is not None:
            self.code += data


def check():
    files = public_files()
    errors = []
    pages = {p.resolve(): Page(p.read_text(encoding='utf-8')) for p in files if p.suffix == '.html'}
    for path, page in pages.items():
        for link in page.links:
            parts = urlsplit(link)
            if parts.scheme or parts.netloc:
                continue
            target = (path.parent / unquote(parts.path)).resolve() if parts.path else path
            if not target.is_file():
                errors.append('断开的本地链接：%s -> %s' % (path.relative_to(ROOT), link))
            elif parts.fragment and target in pages and unquote(parts.fragment) not in pages[target].ids:
                errors.append('不存在的章节锚点：%s -> %s' % (path.relative_to(ROOT), link))
    for case in ('01-led-blink', '02-wifi-led', '03-bluetooth-led'):
        folder = ROOT / 'examples' / case
        source = (folder / 'main.py').read_text(encoding='utf-8').strip()
        if source not in pages[(folder / 'index.html').resolve()].codes:
            errors.append(case + ' 教程完整代码与 main.py 不一致')
    for path in files:
        if path.name == 'wifi_config.py' or any(part in ('.venv', 'backups') for part in path.parts):
            errors.append('分享范围误含私人文件：' + str(path.relative_to(ROOT)))
        if path.suffix == '.py':
            try:
                compile(path.read_bytes(), str(path), 'exec')
            except SyntaxError:
                errors.append('Python 语法错误：' + str(path.relative_to(ROOT)))
    # 已有配置时，避免真实网络名/密码意外进入公开文件；只报告文件名。
    config = ROOT / 'config' / 'wifi_config.py'
    if config.exists():
        try:
            values = {n.targets[0].id: ast.literal_eval(n.value)
                      for n in ast.parse(config.read_text(encoding='utf-8')).body
                      if isinstance(n, ast.Assign) and isinstance(n.targets[0], ast.Name)}
            secrets = [v.encode() for k,v in values.items()
                       if k in ('WIFI_PASSWORD','WIFI_SSID') and isinstance(v,str) and v]
            for path in files:
                if any(secret in path.read_bytes() for secret in secrets):
                    errors.append('公开文件含本地网络配置值（已隐藏）：' + str(path.relative_to(ROOT)))
        except (SyntaxError, ValueError, TypeError):
            errors.append('本地 Wi-Fi 配置无法安全解析；请检查赋值语法')
    if errors:
        print('\n'.join(errors), file=sys.stderr)
        return 1
    print('PASS: %d HTML pages; local links, code excerpts, Python syntax and %d public files checked.' % (len(pages), len(files)))
    return 0


if __name__ == '__main__':
    raise SystemExit(check())
