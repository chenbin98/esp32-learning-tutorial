"""上传/分享边界的本地测试，不接触开发板。"""
from contextlib import redirect_stdout
import hashlib
import io
import json
from pathlib import Path
import sys
import tempfile
from types import SimpleNamespace
import unittest
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'scripts'))
import device
import package_tutorial


class ToolsTest(unittest.TestCase):
    def test_unknown_case_is_rejected(self):
        with self.assertRaises(ValueError):
            device.load_case('99')

    def test_manifest_rejects_escape_and_missing_files(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            folder = root / 'examples' / '01-demo'
            folder.mkdir(parents=True)
            for filename in ('../../outside.py', 'missing.py'):
                (folder / 'case.json').write_text(json.dumps({'files': {filename: 'main.py'}}))
                with self.assertRaises(ValueError):
                    device.load_case('01', root)

    def test_wifi_placeholder_rejected_without_exposing_password(self):
        with tempfile.TemporaryDirectory() as tmp:
            config = Path(tmp) / 'wifi_config.py'
            config.write_text('WIFI_SSID=""\nWIFI_PASSWORD="private-test-value"\n')
            with self.assertRaises(ValueError) as caught:
                device.validate_wifi(config)
            self.assertNotIn('private-test-value', str(caught.exception))

    def test_dry_run_never_contacts_device(self):
        with patch.object(device, 'mpremote') as remote, redirect_stdout(io.StringIO()):
            device.deploy('01', 'not-a-real-port', dry_run=True)
        remote.assert_not_called()

    def simulate_upload(self, corrupt=False):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            source = root / 'main.py'
            source.write_text('print("example")\n')
            calls = []
            def remote(port, *args, capture=False):
                calls.append(args)
                if args == ('exec', 'import os; print(os.listdir())'):
                    return SimpleNamespace(stdout="['main.py']\n")
                if args[0] == 'exec' and 'hashlib.sha256' in args[1]:
                    digest = 'invalid' if corrupt else hashlib.sha256(source.read_bytes()).hexdigest()
                    return SimpleNamespace(stdout=digest + '\n')
                return SimpleNamespace(stdout='')
            with patch.object(device, 'ROOT', root), patch.object(device, 'load_case', return_value=('01-demo', [(source,'main.py')])), patch.object(device, 'mpremote', side_effect=remote), patch('serial.tools.list_ports.comports', return_value=[SimpleNamespace(device='TEST')]), redirect_stdout(io.StringIO()):
                if corrupt:
                    with self.assertRaises(ValueError):
                        device.deploy('01','TEST')
                else:
                    device.deploy('01','TEST')
            return calls

    def test_failed_checksum_does_not_replace_or_reset(self):
        calls = self.simulate_upload(corrupt=True)
        self.assertFalse(any(call[0] == 'reset' or 'os.rename(' in str(call) for call in calls))

    def test_verified_upload_backs_up_then_installs_and_resets(self):
        calls = self.simulate_upload()
        backup = next(i for i,c in enumerate(calls) if c[:3] == ('fs','cp',':main.py'))
        upload = next(i for i,c in enumerate(calls) if c[0] == 'fs' and c[-1] == ':main.py.upload')
        verify = next(i for i,c in enumerate(calls) if 'hashlib.sha256' in str(c))
        install = next(i for i,c in enumerate(calls) if 'os.rename(' in str(c))
        self.assertLess(backup, upload)
        self.assertLess(upload, verify)
        self.assertLess(verify, install)
        self.assertEqual(calls[-1], ('reset',))

    def test_release_allowlist_excludes_local_data_and_symlinks(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            for name in ('index.html', 'config/wifi_config.py', 'backups/main.py',
                         'firmware/private.bin', 'docs/assets/tutorial.css',
                         'examples/02-wifi-led/main.py', 'examples/02-wifi-led/wifi_config.py'):
                path = root / name
                path.parent.mkdir(parents=True, exist_ok=True)
                path.write_text('sample')
            (root / 'README.md').symlink_to(root / 'config/wifi_config.py')
            names = {p.relative_to(root).as_posix() for p in package_tutorial.public_files(root)}
            self.assertEqual(names, {'index.html', 'docs/assets/tutorial.css','examples/02-wifi-led/main.py'})


if __name__ == '__main__':
    unittest.main()
