"""单键 getprop 读不到版本时按分区属性回退（#195）。不用手机。"""
from pathlib import Path
import sys
import unittest
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "tool"))
import run


def fake_props(**values):
    """按 key 返回预设值，未列出的 key 一律空串（模拟这台 ROM 上读不到的那些）。"""
    return lambda serial, k: values.get(k, "")


class AndroidReleaseTests(unittest.TestCase):
    def test_primary_key_wins(self):
        # 其他机型：ro.build.version.release 可读，行为与原来一致
        with patch.object(run, "prop", fake_props(**{"ro.build.version.release": "16"})):
            self.assertEqual(run.android_release("x"), "16")

    def test_key_order_is_the_priority(self):
        # 五个 key 都有值时取 ro.build.version.release；顺序里任何一处被换掉这条都会红。
        # key 名写死是故意的：用 ANDROID_RELEASE_KEYS 生成样本会跟着顺序一起变，测不出顺序。
        values = {"ro.build.version.release": "16",
                  "ro.build.version.release_or_codename": "16a",
                  "ro.system.build.version.release": "17",
                  "ro.product.build.version.release": "17b",
                  "ro.system_ext.build.version.release": "15"}
        with patch.object(run, "prop", fake_props(**values)):
            self.assertEqual(run.android_release("x"), "16")

    def test_partition_key_when_primary_empty(self):
        # #195：HyperOS 4 / 24129PN74C 上 release 单键空，真值在 ro.system.* 里
        with patch.object(run, "prop", fake_props(**{"ro.system.build.version.release": "17"})):
            self.assertEqual(run.android_release("x"), "17")

    def test_last_key_still_reachable(self):
        with patch.object(run, "prop", fake_props(**{"ro.system_ext.build.version.release": "15"})):
            self.assertEqual(run.android_release("x"), "15")

    def test_all_empty_returns_empty(self):
        # 取值函数本身不编造版本，空就是空；「未知」由展示这一层给
        with patch.object(run, "prop", fake_props()):
            self.assertEqual(run.android_release("x"), "")

    def test_info_reports_unknown_when_all_empty(self):
        # #195 正文第 4 条：都拿不到时打印「未知」，不要留空
        with patch.object(run, "prop", fake_props()):
            self.assertEqual(run.info("x")["android"], "未知")

    def test_info_reports_17_on_this_device(self):
        # 这台必须给 17，不能为空
        with patch.object(run, "prop", fake_props(**{"ro.system.build.version.release": "17"})):
            self.assertEqual(run.info("x")["android"], "17")


if __name__ == "__main__":
    unittest.main()
