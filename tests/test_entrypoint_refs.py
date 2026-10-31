"""非测试入口对 `gui.app` 的引用得像真的一样存在 —— 截图、冒烟这类脚本跑不进测试面。

#355 把 `Api()` 改成必填参数时，`gui/shots.py` 静默坏了，全量回归一片绿。这里只读 AST：
`app.<名字>` 的属性要在模块上找得到，`app.<名字>(…)` 的实参要能绑定到它的签名。不执行脚本。
"""
import ast
import inspect
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from gui import app  # noqa: E402


def entrypoints():
    """gui/ 下 import 了 app 的脚本：[(路径, 语法树)]。"""
    found = []
    for path in sorted((ROOT / "gui").glob("*.py")):
        tree = ast.parse(path.read_text(encoding="utf-8"))
        if any(isinstance(node, ast.Import) and any(alias.name == "app" for alias in node.names)
               for node in ast.walk(tree)):
            found.append((path, tree))
    return found


def app_attributes(tree):
    """[(行号, 名字, 调用实参或 None)]：`app.<名字>` 形式，调用带上它的实参。"""
    refs = []
    for node in ast.walk(tree):
        if not isinstance(node, ast.Attribute) or not isinstance(node.value, ast.Name) or node.value.id != "app":
            continue
        refs.append((node.lineno, node.attr, None))
    for node in ast.walk(tree):
        if isinstance(node, ast.Call) and isinstance(node.func, ast.Attribute) and \
                isinstance(node.func.value, ast.Name) and node.func.value.id == "app":
            if any(isinstance(arg, ast.Starred) for arg in node.args) or \
                    any(kw.arg is None for kw in node.keywords):
                continue                                    # 展开写法无法静态绑定
            refs.append((node.lineno, node.func.attr, (node.args, node.keywords)))
    return refs


class EntrypointReferenceTests(unittest.TestCase):
    def test_entrypoints_only_reference_things_app_actually_has(self):
        scripts = entrypoints()
        self.assertTrue(scripts, "没找到任何 import app 的脚本，这条守卫会变成空转")
        checked = 0
        for path, tree in scripts:
            for line, name, call in app_attributes(tree):
                with self.subTest(script=path.name, line=line, name=name):
                    self.assertTrue(hasattr(app, name), f"{path.name}:{line} 引用了不存在的 app.{name}")
                    if call is None:
                        continue
                    args, keywords = call
                    try:
                        signature = inspect.signature(getattr(app, name))
                    except (TypeError, ValueError):
                        continue                            # 取不到签名的内建/动态对象，跳过绑定检查
                    try:
                        signature.bind(*([None] * len(args)), **{kw.arg: None for kw in keywords})
                    except TypeError as e:
                        self.fail(f"{path.name}:{line} app.{name}(…) 的实参绑不上：{e}")
                    checked += 1
        self.assertGreater(checked, 0, "没有任何 app.<名字>(…) 调用被检查过")


if __name__ == "__main__":
    unittest.main()
