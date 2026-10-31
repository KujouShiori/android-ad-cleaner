"""生成 run.py 命令的对拍基线 tests/baselines/run_cli.json。

必须用改动前的干净副本跑，别用当前工作区（工作区随时会被改）：
  git archive <sha> | tar -x -C /tmp/aac-base
  .venv/bin/python tests/make_run_cli_baseline.py /tmp/aac-base <sha>

产物里只放退出码与两路输出，路径与备份目录名已规范化（见 tests/run_cli_driver.py）。
"""
import json
import sys
import tempfile
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import run_cli_cases
import run_cli_driver

OUT = HERE / "baselines" / "run_cli.json"
HOW = "git archive <sha> | tar -x -C /tmp/aac-base && .venv/bin/python tests/make_run_cli_baseline.py /tmp/aac-base <sha>"


def main(argv):
    if len(argv) != 2:
        print(__doc__)
        return 2
    root, sha = Path(argv[0]), argv[1]
    cases = {}
    for spec in run_cli_cases.CASES:
        with tempfile.TemporaryDirectory() as work:
            result, _ = run_cli_driver.run_once(root, spec, work)
        cases[spec["name"]] = result
        print(f"{spec['name']}\trc={result['rc']}")
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps({"provenance": {"baseline": sha, "how": HOW, "cases": len(cases)},
                               "cases": cases}, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
