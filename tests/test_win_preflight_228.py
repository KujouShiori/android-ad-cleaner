"""Windows 启动失败归因：缺 WebView2 / 程序文件带 MOTW / 其他（#228）。

注册表读取与 ADS 探测都从外面注入，所以这套判定在 macOS 上也能跑。
"""
import sys
import tempfile
import unittest
from pathlib import Path

from gui import winpreflight

CID = winpreflight.WEBVIEW2_CLIENT_ID


def fake_read(values):
    """values: {(hive, 客户端 ID): pv 或异常}；不在表里的键一律当作键不存在。"""
    def read(hive, path):
        value = values.get((hive, path.rsplit("\\", 1)[-1]))
        if isinstance(value, Exception):
            raise value
        if value is None:
            raise FileNotFoundError(path)
        return value

    return read


def always_raise(error):
    def read(hive, path):
        raise error

    return read


class RegistryStateTests(unittest.TestCase):
    def test_installed_when_one_key_has_a_version(self):
        read = fake_read({("HKLM", CID): "156.0.3414.50"})
        self.assertEqual(winpreflight.webview2_state(read), "installed")

    def test_missing_when_no_key_exists(self):
        self.assertEqual(winpreflight.webview2_state(fake_read({})), "missing")

    def test_unknown_when_every_key_raises(self):
        read = always_raise(PermissionError("拒绝访问"))
        self.assertEqual(winpreflight.webview2_state(read), "unknown")

    def test_unknown_does_not_hide_a_real_install(self):
        read = fake_read({("HKLM", CID): PermissionError("拒绝访问"),
                          ("HKCU", CID): "156.0.3414.50"})
        self.assertEqual(winpreflight.webview2_state(read), "installed")

    def test_empty_version_counts_as_missing(self):
        self.assertEqual(winpreflight.webview2_state(fake_read({("HKLM", CID): ""})), "missing")

    @unittest.skipIf(sys.platform == "win32", "Windows 上默认读取会真读注册表")
    def test_default_reader_does_not_raise_off_windows(self):
        self.assertEqual(winpreflight.webview2_state(), "unknown")


class BlockedFilesTests(unittest.TestCase):
    def setUp(self):
        self.dir = tempfile.TemporaryDirectory()
        self.addCleanup(self.dir.cleanup)
        self.root = Path(self.dir.name)

    def touch(self, *parts):
        path = self.root.joinpath(*parts)
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text("", encoding="utf-8")
        return path

    def test_reports_the_two_load_bearing_dlls(self):
        runtime = self.touch("pythonnet", "runtime", "Python.Runtime.dll")
        loader = self.touch("clr_loader", "ffi", "dlls", "amd64", "ClrLoader.dll")
        blocked = winpreflight.blocked_files(str(self.root), detect=lambda p: True)
        self.assertEqual({Path(p) for p in blocked}, {runtime, loader})

    def test_ignores_files_without_the_stream(self):
        self.touch("pythonnet", "runtime", "Python.Runtime.dll")
        self.assertEqual(winpreflight.blocked_files(str(self.root), detect=lambda p: False), ())

    def test_does_not_probe_files_that_are_not_there(self):
        probed = []
        winpreflight.blocked_files(str(self.root),
                                   detect=lambda p: probed.append(p) or True)
        self.assertEqual(probed, [])

    def test_finds_the_dlls_under_internal_layout(self):
        runtime = self.touch("_internal", "pythonnet", "runtime", "Python.Runtime.dll")
        blocked = winpreflight.blocked_files(str(self.root), detect=lambda p: True)
        self.assertEqual(blocked, (str(runtime),))

    def test_default_detector_reports_nothing_for_a_plain_file(self):
        self.touch("pythonnet", "runtime", "Python.Runtime.dll")
        self.assertEqual(winpreflight.blocked_files(str(self.root)), ())


class DescribeTests(unittest.TestCase):
    def setUp(self):
        self.dir = tempfile.TemporaryDirectory()
        self.addCleanup(self.dir.cleanup)
        self.root = Path(self.dir.name)
        for rel in (("pythonnet", "runtime", "Python.Runtime.dll"),
                    ("clr_loader", "ffi", "dlls", "amd64", "ClrLoader.dll")):
            path = self.root.joinpath(*rel)
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text("", encoding="utf-8")

    def test_line_names_both_facts(self):
        line = winpreflight.describe(str(self.root),
                                     read=fake_read({("HKLM", CID): "156.0.3414.50"}),
                                     detect=lambda p: True)
        self.assertEqual(line, "webview2=installed motw=yes")

    def test_line_says_no_when_nothing_is_wrong(self):
        line = winpreflight.describe(str(self.root), read=fake_read({}), detect=lambda p: False)
        self.assertEqual(line, "webview2=missing motw=no")


class StartupAdviceTests(unittest.TestCase):
    """窗口起不来时用户看到的那段话，以及要不要跳微软官网。"""

    def advice(self, state, blocked=()):
        from gui import app
        return app.startup_advice(state, blocked, RuntimeError("loading Python.Runtime.dll failed"))

    def test_missing_runtime_points_at_the_bootstrap_installer(self):
        text, open_site = self.advice("missing")
        self.assertIn("缺少微软 Edge WebView2 运行时", text)
        self.assertIn("Evergreen Bootstrapper", text)
        self.assertTrue(open_site)

    def test_blocked_files_explain_the_unlock_step_and_stay_off_the_site(self):
        text, open_site = self.advice("installed", blocked=("x",))
        self.assertIn("解除锁定", text)
        self.assertIn("Unblock-File", text)
        self.assertNotIn("缺少微软 Edge WebView2 运行时", text)
        self.assertFalse(open_site)

    def test_unknown_failure_shows_the_real_error_and_a_feedback_link(self):
        text, open_site = self.advice("installed")
        self.assertIn("loading Python.Runtime.dll failed", text)
        self.assertIn("issues/new", text)
        self.assertNotIn("缺少微软 Edge WebView2 运行时", text)
        self.assertFalse(open_site)

    def test_unknown_registry_state_is_not_treated_as_missing(self):
        text, open_site = self.advice("unknown")
        self.assertNotIn("缺少微软 Edge WebView2 运行时", text)
        self.assertFalse(open_site)


if __name__ == "__main__":
    unittest.main()
