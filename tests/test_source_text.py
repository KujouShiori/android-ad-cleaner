"""源码里不写裸的零宽字符：用 \\u 转义，避免不可见、被格式化工具剥掉后静默改变判定。"""
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
# 用转义定义，这个文件自身不能出现裸字符。
FORBIDDEN = {
    "\u200b": "U+200B ZERO WIDTH SPACE",
    "\ufeff": "U+FEFF ZERO WIDTH NO-BREAK SPACE / BOM",
    "\u200c": "U+200C ZERO WIDTH NON-JOINER",
    "\u200d": "U+200D ZERO WIDTH JOINER",
    "\u2060": "U+2060 WORD JOINER",
}


class SourceTextTests(unittest.TestCase):
    def test_source_has_no_raw_zero_width_characters(self):
        hits = []
        for folder in ("tool", "gui", "tests"):
            for path in sorted((ROOT / folder).rglob("*.py")):
                for lineno, line in enumerate(path.read_text(encoding="utf-8").splitlines(), 1):
                    for char, label in FORBIDDEN.items():
                        if char in line:
                            hits.append(f"{path.relative_to(ROOT)}:{lineno}: {label}")
        self.assertEqual(hits, [], "源码里不写裸零宽字符，用 \\u 转义：\n" + "\n".join(hits))


if __name__ == "__main__":
    unittest.main()
