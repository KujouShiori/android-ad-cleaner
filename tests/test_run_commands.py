"""run.py 的命令接口，以及「只是搬家」的对拍。

两件事在这里守着：
- 每条命令是一个 handler，进程内调用拿退出码；退出码与错误渲染只在 main() 的出口（ADR-0005）。
- 对外可观察的行为（退出码 / stdout / stderr）与改动前逐字节相同：基线
  `tests/baselines/run_cli.json` 由 `tests/make_run_cli_baseline.py` 在 `git archive e319126`
  的干净副本上生成，喂的是同一份假 adb（`tests/run_cli_cases.py`）。

`ui-check` / `chan-scan` / `chan-off` / `chan-on` / `recipe` 会真的起子进程（fast.py /
chan_fast.py），输出取决于本机 adb 服务，所以不做逐字节对拍，改在这里替身化后断言返回值。
"""
import ast
import contextlib
import io
import json
import os
import sys
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "tool"))
sys.path.insert(0, str(ROOT / "tests"))
import adb_link
import run
import run_cli_cases
import run_cli_driver

BASELINE = ROOT / "tests" / "baselines" / "run_cli.json"


class CliParityTests(unittest.TestCase):
    """同一批输入喂给假 adb，比对新旧 run.py 的退出码与两路输出。"""

    @classmethod
    def setUpClass(cls):
        cls.baseline = json.loads(BASELINE.read_text(encoding="utf-8"))

    def test_every_command_is_covered(self):
        """命令表里的每条命令都要有对拍用例，漏一条这里就红（表增删时能被逼着回来补）。"""
        covered = {arg for spec in run_cli_cases.CASES for arg in spec["argv"] if arg in run.COMMANDS}
        self.assertEqual(covered, set(run.COMMANDS) - set(run_cli_cases.HOST_SIDE))
        self.assertTrue(any(spec["argv"][0] == "devices" for spec in run_cli_cases.CASES))

    @unittest.skipIf(os.name == "nt", "假 adb 是 sh 包装，Windows 上不跑")
    def test_matches_baseline(self):
        for spec in run_cli_cases.CASES:
            with self.subTest(spec["name"]), tempfile.TemporaryDirectory() as work:
                got, calls = run_cli_driver.run_once(ROOT, spec, work)
                # 守卫断言先跑：证明这条用例真的走到了目标分支，而不是「两边都没发生什么」。
                text = json.dumps(calls, ensure_ascii=False)
                for needle in spec["expect"]:
                    self.assertIn(needle, text)
                if spec["expect_empty"]:
                    self.assertEqual(calls, [])
                self.assertEqual(got, self.baseline["cases"][spec["name"]])


class HandlerInterfaceTests(unittest.TestCase):
    """进程内调用：拿到的是退出码，不是 SystemExit。"""

    def setUp(self):
        # 这些用例不关心 adb 装没装；解析本身由 test_adb_link 守着。
        patcher = patch.object(run, "adb", return_value="adb")
        patcher.start()
        self.addCleanup(patcher.stop)

    def test_help_and_unknown_command_stay_exit_zero(self):
        for argv in ([], ["-h"], ["-s", "S", "no-such-command"]):
            with self.subTest(argv), contextlib.redirect_stdout(out := io.StringIO()):
                self.assertEqual(run.main(argv), 0)
            self.assertIn("手机去广告", out.getvalue())

    def test_devices_stays_outside_the_table(self):
        """唯一不带序列号的命令，留在 -s 解析之前，不进 handler 表。"""
        self.assertNotIn("devices", run.COMMANDS)
        with patch.object(run.subprocess, "run", return_value=SimpleNamespace(stdout="")):
            self.assertEqual(run.main(["devices"]), 0)

    def test_failure_returns_one_and_writes_the_reason_to_stderr(self):
        err = io.StringIO()
        with patch.object(run, "pkg_list", return_value=""), \
             contextlib.redirect_stdout(io.StringIO()), contextlib.redirect_stderr(err):
            self.assertEqual(run.main(["-s", "S", "backup"]), 1)
        self.assertIn("读不到包列表", err.getvalue())

    def test_forwarded_child_code_is_kept(self):
        cases = (("ui-check", [], ("fast.py", "-s", "S", "check")),
                 ("chan-off", ["list.tsv"], ("chan_fast.py", "-s", "S", "off", "list.tsv")),
                 ("chan-on", ["list.tsv"], ("chan_fast.py", "-s", "S", "on", "list.tsv")))
        for command, rest, expected in cases:
            with self.subTest(command), patch.object(run, "py", return_value=3) as child:
                self.assertEqual(run.main(["-s", "S", command, *rest]), 3)
                self.assertEqual(child.call_args.args, expected)

    def test_chan_scan_forwards_child_code_and_its_stderr(self):
        err = io.StringIO()
        failed = SimpleNamespace(returncode=7, stdout="", stderr="读取失败\n")
        with patch.object(run, "latest_backup", return_value="/tmp/x"), \
             patch.object(run.subprocess, "run", return_value=failed), \
             contextlib.redirect_stdout(io.StringIO()), contextlib.redirect_stderr(err):
            self.assertEqual(run.main(["-s", "S", "chan-scan"]), 7)
        self.assertIn("读取失败", err.getvalue())

    def test_chan_off_without_a_list_fails_before_starting_anything(self):
        err = io.StringIO()
        with patch.object(run, "py") as child, contextlib.redirect_stderr(err):
            self.assertEqual(run.main(["-s", "S", "chan-off"]), 1)
        self.assertIn("要给清单文件", err.getvalue())
        self.assertFalse(child.called)

    def recipe(self, **overrides):
        info = {"brand": "Xiaomi", "model": "M154FF", "name": "Xiaomi 13", "build": "OS4.0", "android": "13"}
        stack = contextlib.ExitStack()
        stack.enter_context(patch.object(run, "info", return_value=info))
        stack.enter_context(patch.object(run, "recipe_for", return_value=("recipe.py", False)))
        stack.enter_context(patch.object(run, "recipe_meta", return_value={"build": "OS4.0"}))
        stack.enter_context(patch.object(run, "sh", return_value="15"))
        for name, value in overrides.items():
            stack.enter_context(patch.object(run, name, **value))
        return stack

    def test_recipe_forwards_the_child_code_after_restoring_stay_awake(self):
        with self.recipe(py={"return_value": 5}, wait_unlocked={"return_value": True}), \
             contextlib.redirect_stdout(io.StringIO()):
            self.assertEqual(run.main(["-s", "S", "recipe"]), 5)

    def test_locked_phone_fails_without_starting_the_recipe(self):
        err = io.StringIO()
        with self.recipe(wait_unlocked={"return_value": False}), patch.object(run, "py") as child, \
             contextlib.redirect_stdout(io.StringIO()), contextlib.redirect_stderr(err):
            self.assertEqual(run.main(["-s", "S", "recipe"]), 1)
        self.assertIn("手机一直锁屏", err.getvalue())
        self.assertFalse(child.called)

    def test_recipe_restore_failure_replaces_the_lock_message(self):
        """锁屏超时后恢复插电常亮又断线：旧实现里 `finally` 的异常顶掉挂起的 `SystemExit`，
        stderr 只剩恢复那一条。所以锁屏文案要等 `finally` 跑完才定。"""
        calls = []

        def shell(_serial, command):
            calls.append(command)
            if len(calls) == 3:                 # 第 3 条是 finally 里的恢复
                raise adb_link.DeviceLost("恢复断线")
            return "15"

        err = io.StringIO()
        with self.recipe(wait_unlocked={"return_value": False}), patch.object(run, "sh", side_effect=shell), \
             contextlib.redirect_stdout(io.StringIO()), contextlib.redirect_stderr(err):
            self.assertEqual(run.main(["-s", "S", "recipe"]), 1)
        self.assertEqual(err.getvalue(), "恢复断线\n")

    VIVO_QUICKAPP = {"pkg": "com.vivo.hybrid", "name": "快应用", "keep": False, "closed": False,
                     "method": "setting", "suspended": False, "tested": True, "running": False, "used": 0}

    def check_link_lost_is_not_a_component_failure(self, sub):
        """`except RuntimeError` 原来抓不到 `SystemExit`，断线是当场中止整条命令；
        改抛 `DeviceLost` 后它会变成「某个组件失败」——#293 明说不能这么报。"""
        err = io.StringIO()
        with patch.object(run, "quickapps", return_value=[self.VIVO_QUICKAPP]), \
             patch.object(run, "set_quickapp_service", side_effect=adb_link.DeviceLost("连接断了")), \
             contextlib.redirect_stdout(io.StringIO()), contextlib.redirect_stderr(err):
            self.assertEqual(run.main(["-s", "S", "quickapp", sub]), 1)
        self.assertEqual(err.getvalue(), "连接断了\n")

    def test_quickapp_off_reports_link_lost_instead_of_a_component_failure(self):
        self.check_link_lost_is_not_a_component_failure("off")

    def test_quickapp_on_reports_link_lost_instead_of_a_component_failure(self):
        self.check_link_lost_is_not_a_component_failure("on")

    def test_help_does_not_need_adb(self):
        """ADR-0005 声明的行为变化：没有 adb 时帮助照常输出（旧实现 import 期就退出了）。"""
        with patch.object(run, "adb", side_effect=run.NoAdb(adb_link.NO_ADB)), \
             contextlib.redirect_stdout(out := io.StringIO()):
            self.assertEqual(run.main(["-h"]), 0)
            self.assertEqual(run.main([]), 0)
        self.assertIn("手机去广告", out.getvalue())

    def test_bad_arguments_still_report_missing_adb_first(self):
        """参数写错时也先报「找不到 adb」：这与旧实现 import 期的先后一致，别在搬 adb() 时弄反。"""
        err = io.StringIO()
        with patch.object(run, "adb", side_effect=run.NoAdb(adb_link.NO_ADB)), contextlib.redirect_stderr(err):
            self.assertEqual(run.main(["-s", "S"]), 1)
        self.assertEqual(err.getvalue(), adb_link.NO_ADB + "\n")

    def test_link_lost_becomes_one_message_and_exit_code_one(self):
        err = io.StringIO()
        with patch.object(run, "sh", side_effect=adb_link.DeviceLost("连接断了")), \
             contextlib.redirect_stdout(io.StringIO()), contextlib.redirect_stderr(err):
            self.assertEqual(run.main(["-s", "S", "check"]), 1)
        self.assertEqual(err.getvalue(), "连接断了\n")

    def test_missing_adb_is_rendered_at_the_same_exit(self):
        err = io.StringIO()
        with patch.object(run, "adb", side_effect=run.NoAdb(adb_link.NO_ADB)), contextlib.redirect_stderr(err):
            self.assertEqual(run.main(["-s", "S", "check"]), 1)
        self.assertEqual(err.getvalue(), adb_link.NO_ADB + "\n")

    def test_exit_lives_only_at_the_entry(self):
        """handler 里不许再出现 sys.exit：退出码的唯一出口是 __main__ 那一行。"""
        tree = ast.parse(Path(run.__file__).read_text(encoding="utf-8"))
        exits = [node for node in ast.walk(tree)
                 if isinstance(node, ast.Call) and isinstance(node.func, ast.Attribute)
                 and node.func.attr == "exit" and getattr(node.func.value, "id", "") == "sys"]
        system_exits = [node for node in ast.walk(tree)
                        if isinstance(node, ast.Name) and node.id == "SystemExit"]
        self.assertEqual(exits, [])
        self.assertEqual(len(system_exits), 1)


if __name__ == "__main__":
    unittest.main()
