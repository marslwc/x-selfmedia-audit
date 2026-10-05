#!/usr/bin/env python3
"""
回归测试 —— 覆盖 v1.0.1 / v1.0.2 修复的三个真实 bug

用标准库运行，无需 pytest：
    python3 tests/test_regressions.py

覆盖：
  1. 曝光分布被单条爆量帖主导时，四象限不得误判为「分发正常」
  2. 变现资格在数据缺失时，不得输出「已满足条件」
  3. 零互动帖占比过高时应给出分发侧预警
"""

import json
import os
import subprocess
import sys
import tempfile

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
X_AUDIT = os.path.join(ROOT, "scripts", "x_audit.py")
MONETIZATION = os.path.join(ROOT, "scripts", "monetization_check.py")

PY = sys.executable or "python3"

_passed = 0
_failed = 0


def check(name, condition, detail=""):
    global _passed, _failed
    if condition:
        _passed += 1
        print(f"  \033[32mPASS\033[0m  {name}")
    else:
        _failed += 1
        print(f"  \033[31mFAIL\033[0m  {name}")
        if detail:
            print(f"        {detail}")


def run(script, args, stdin_data=None):
    proc = subprocess.run(
        [PY, script] + args,
        input=stdin_data,
        capture_output=True,
        text=True,
        timeout=60,
    )
    return proc.returncode, proc.stdout, proc.stderr


def write_json(payload):
    fd, path = tempfile.mkstemp(suffix=".json")
    with os.fdopen(fd, "w", encoding="utf-8") as f:
        json.dump(payload, f, ensure_ascii=False)
    return path


def skewed_dataset():
    """1 条爆量帖 + 9 条低曝光帖。均值被拉高约 20 倍。"""
    posts = [{
        "text": "爆款帖", "date": "2026-09-10T09:00", "impressions": 20000,
        "likes": 400, "replies": 100, "retweets": 50, "bookmarks": 20,
        "type": "thread",
    }]
    for i in range(9):
        posts.append({
            "text": f"普通帖 {i + 1}", "date": f"2026-09-{11 + i:02d}T09:00",
            "impressions": 100, "likes": 0, "replies": 0,
            "retweets": 0, "bookmarks": 0, "type": "opinion",
        })
    return {
        "account": {"handle": "@skew", "followers": 1000, "following": 300,
                    "created": "2025-01-01", "premium": False},
        "window_days": 28,
        "posts": posts,
    }


def balanced_dataset():
    """无异常值的健康账号，用于确认偏度保护不会误触发。"""
    posts = []
    for i in range(10):
        posts.append({
            "text": f"帖子 {i + 1}", "date": f"2026-09-{10 + i:02d}T09:00",
            "impressions": 2000, "likes": 40, "replies": 12,
            "retweets": 6, "bookmarks": 4, "type": "opinion",
        })
    return {
        "account": {"handle": "@balanced", "followers": 3000, "following": 400,
                    "created": "2024-01-01", "premium": True},
        "window_days": 28,
        "posts": posts,
    }


# ---------------------------------------------------------------- 测试 1

def test_skew_protection():
    print("\n[1] 偏度保护：单条爆量帖不得让四象限误判为「分发正常」")
    path = write_json(skewed_dataset())
    try:
        code, out, err = run(X_AUDIT, ["--json", path])
        check("脚本正常退出", code == 0, err[:300])
        check("结论翻转为「分发问题为主」",
              "分发问题为主" in out,
              f"未找到预期结论。实际四象限输出：\n{out[out.find('四象限'):out.find('四象限') + 400]}")
        check("不再输出「分发与内容均正常」",
              "分发与内容均正常" not in out)
        check("显式标注偏度警告",
              "均值/中位数" in out or "偏度" in out)
        check("给出中位数口径依据",
              "中位数口径" in out)
    finally:
        os.unlink(path)


# ---------------------------------------------------------------- 测试 2

def test_zero_interaction_flag():
    print("\n[2] 零互动帖占比 ≥50% 应触发分发侧预警")
    path = write_json(skewed_dataset())
    try:
        code, out, err = run(X_AUDIT, ["--json", path])
        check("脚本正常退出", code == 0, err[:300])
        check("输出零互动帖占比预警",
              "零互动帖占比" in out,
              "未找到零互动帖相关输出")
        check("处方指向分发而非「多发帖」",
              "分发" in out)
    finally:
        os.unlink(path)


# ---------------------------------------------------------------- 测试 3

def test_no_false_positive_on_healthy_data():
    print("\n[3] 健康数据不得被偏度保护误伤")
    path = write_json(balanced_dataset())
    try:
        code, out, err = run(X_AUDIT, ["--json", path])
        check("脚本正常退出", code == 0, err[:300])
        check("偏度低时使用均值口径", "均值口径" in out)
        check("不输出偏度警告", "偏度" not in out)
    finally:
        os.unlink(path)


# ---------------------------------------------------------------- 测试 4

def test_monetization_missing_data():
    print("\n[4] 变现资格：数据缺失不得判定为「已满足条件」")
    code, out, err = run(MONETIZATION, ["--age", "25", "--active-30d", "yes"])
    check("脚本正常退出", code == 0, err[:300])
    check("不再输出「路径 A 已满足全部条件」",
          "路径 A 已满足全部条件" not in out,
          "旧 bug 复发：数据缺失时误判为已满足")
    check("不再输出「路径 B 已满足条件」",
          "路径 B（Creator Subscriptions）已满足条件" not in out,
          "旧 bug 复发：数据缺失时误判为已满足")
    check("明确输出「无法判定」", "无法判定" in out)
    check("说明缺失项不可视为通过", "不能视为已通过" in out)


# ---------------------------------------------------------------- 测试 5

def test_monetization_hard_gate():
    print("\n[5] 变现资格：硬门槛缺口应阻断路径 A")
    code, out, err = run(MONETIZATION, [
        "--country", "CN", "--premium", "yes", "--verified-followers", "120",
        "--followers", "3000", "--impressions-90d", "300000",
        "--age-months", "8", "--age", "28",
    ])
    check("脚本正常退出", code == 0, err[:300])
    check("识别出硬门槛缺口", "暂不可申请" in out and "硬门槛" in out)


# ---------------------------------------------------------------- 测试 6

def test_reply_impression_paradox():
    print("\n[7] 回复区悖论：变现输出必须提示回复曝光不计入")
    code, out, err = run(MONETIZATION, ["--demo"])
    check("脚本正常退出", code == 0, err[:300])
    check("输出回复区悖论章节", "回复区悖论" in out)
    check("明确说明回复曝光不计入",
          "不计入" in out and "回复" in out,
          "未找到「回复曝光不计入」的明确说明")
    check("给出目标分岔的配比建议",
          "原创 70%" in out and "回复 50%" in out)
    # x_audit 侧的算法规则文件也应有交叉引用
    algo = os.path.join(ROOT, "references", "algorithm-rules.md")
    with open(algo, encoding="utf-8") as f:
        algo_text = f.read()
    check("算法规则文件有反向交叉引用",
          "不计入变现门槛" in algo_text,
          "algorithm-rules.md 未提示回复曝光不计入变现")


def test_demo_still_works():
    print("\n[6] 内置样例数据仍可正常运行（回归保护）")
    for script, label in ((X_AUDIT, "x_audit"), (MONETIZATION, "monetization_check")):
        code, out, err = run(script, ["--demo"])
        check(f"{label} --demo 正常退出", code == 0, err[:300])
        check(f"{label} --demo 有输出", len(out) > 200)


def main():
    print("=" * 62)
    print("x-selfmedia-audit 回归测试")
    print("=" * 62)

    for path, name in ((X_AUDIT, "scripts/x_audit.py"),
                       (MONETIZATION, "scripts/monetization_check.py")):
        if not os.path.isfile(path):
            print(f"\n\033[31m找不到 {name}，请从仓库根目录运行。\033[0m")
            return 1

    test_skew_protection()
    test_zero_interaction_flag()
    test_no_false_positive_on_healthy_data()
    test_monetization_missing_data()
    test_monetization_hard_gate()
    test_demo_still_works()
    test_reply_impression_paradox()

    print("\n" + "=" * 62)
    total = _passed + _failed
    if _failed:
        print(f"\033[31m{_failed} 项失败 / 共 {total} 项\033[0m")
    else:
        print(f"\033[32m全部通过：{_passed} / {total}\033[0m")
    print("=" * 62)
    return 1 if _failed else 0


if __name__ == "__main__":
    sys.exit(main())
