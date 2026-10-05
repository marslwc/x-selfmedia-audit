#!/usr/bin/env python3
"""
monetization_check.py — X 变现资格自检

逐项核对 2026 年 X 的变现门槛，区分「硬门槛」（内容解决不了）与「软门槛」（可以涨），
输出差距表与时间预期。

⚠️ 时效性：X 变现规则变动频繁。本脚本基于 2026 年 8–9 月公开信息。
   最终以 x.com/settings/monetization 显示的实时条件为准。

用法:
  python3 monetization_check.py --demo
  python3 monetization_check.py --premium yes --verified-followers 320 --followers 8000 \
      --impressions-90d 1200000 --age-months 14 --country US --stripe-supported yes \
      --email-verified yes --twofa yes --avatar yes --banner yes --bio yes \
      --good-standing yes --original-content yes --age 25 --active-30d yes
  python3 monetization_check.py --json profile.json

JSON 结构（字段名同命令行参数，下划线连接）:
{
  "premium": true, "verified_followers": 320, "followers": 8000,
  "impressions_90d": 1200000, "age_months": 14, "country": "US",
  "stripe_supported": true, "email_verified": true, "twofa": true,
  "avatar": true, "banner": true, "bio": true, "good_standing": true,
  "original_content": true, "age": 25, "active_30d": true
}
"""

import argparse
import json
import sys

# 已知不在 Stripe 支持列表内的国家/地区（据 2026 年公开信息）。
# 该列表可能变动，仅作预警，不作最终判定。
KNOWN_STRIPE_UNSUPPORTED = {"CN", "IR", "KP", "CU", "SY", "AF"}

# 门槛定义：(字段, 显示名, 比较类型, 阈值, 是否硬门槛, 说明)
OCR_GATES = [
    ("stripe_supported", "所在国家/地区支持 X 变现且可绑定 Stripe 收款", "bool", None, True,
     "X 变现计划仅对部分国家开放，且需能绑定 Stripe 收款。中国大陆目前不在 Stripe 支持列表内，"
     "这是硬门槛，内容无法解决"),
    ("age", "年满 18 周岁", "ge", 18, True, "无例外，家长同意也不豁免"),
    ("good_standing", "账号状态良好（无有效违规）", "bool", None, True,
     "有未解决的政策违规或申诉记录会直接导致拒绝"),
    ("premium", "持有有效 Premium / Premium+ / Business", "bool", None, False,
     "免费账号永久无资格；这是唯一可以花钱解决的软门槛"),
    ("email_verified", "邮箱已验证", "bool", None, False,
     "常被当作可选设置忽略，但会直接导致申请失败"),
    ("twofa", "已开启两步验证（2FA）", "bool", None, False,
     "同上，属于必填项而非可选项"),
    ("avatar", "已上传头像（非默认占位图）", "bool", None, False, "资料完整性检查项"),
    ("banner", "已上传横幅图（Banner）", "bool", None, False,
     "最容易被忽略的一项，仅缺横幅图即可能导致拒绝"),
    ("bio", "昵称与简介均已填写", "bool", None, False, "资料完整性检查项"),
    ("age_months", "账号注册时间 > 3 个月", "ge", 3, False, "新账号无论粉丝多少都无法申请"),
    ("original_content", "发布原创内容", "bool", None, False,
     "抄袭、轻微改动、非原创汇编、他人搬运的跨平台转发均不算原创"),
    ("verified_followers", "认证粉丝（持 Premium 的关注者）≥ 500", "ge", 500, False,
     "注意是「认证粉丝」不是「总粉丝」。Premium 用户仅占平台约 3%–8%"),
    ("impressions_90d", "近 90 天认证用户 Home Timeline 曝光 ≥ 500,000", "ge", 500000, False,
     "仅计 Premium 用户的唯一曝光，且帖子至少一半可见；排除回复产生的曝光与付费推广"),
]

SUB_GATES = [
    ("age", "年满 18 周岁", "ge", 18, True, "无例外"),
    ("active_30d", "近 30 天内有活动", "bool", None, False, "账号需保持活跃"),
    ("verified_followers", "认证粉丝 ≥ 2,000", "ge", 2000, False,
     "同样是认证粉丝口径，不是总粉丝"),
    ("impressions_90d", "近 3 个月有机曝光 ≥ 5,000,000", "ge", 5000000, False,
     "有机（非付费）曝光总量"),
]


def check_gate(profile, gate):
    field, label, kind, threshold, hard, note = gate
    val = profile.get(field)

    if val is None:
        return {"label": label, "status": "缺失", "value": "未提供",
                "hard": hard, "note": note}

    if kind == "bool":
        ok = bool(val)
        return {"label": label, "status": "通过" if ok else "未达标",
                "value": "是" if ok else "否", "hard": hard, "note": note}
    if kind == "ge":
        try:
            ok = float(val) >= float(threshold)
        except (TypeError, ValueError):
            return {"label": label, "status": "缺失", "value": "无法解析",
                    "hard": hard, "note": note}
        if field == "impressions_90d":
            shown = f"{float(val):,.0f}"
        else:
            shown = f"{float(val):g}"
        return {"label": label, "status": "通过" if ok else "未达标",
                "value": shown, "hard": hard, "note": note}
    return {"label": label, "status": "缺失", "value": "—", "hard": hard, "note": note}


def estimate_timeline(profile, results):
    """给出达到门槛的粗略时间预期。宁可保守，不要给承诺。"""
    notes = []
    vf = profile.get("verified_followers")
    imp = profile.get("impressions_90d")

    if isinstance(vf, (int, float)) and vf < 500:
        notes.append("认证粉丝是通常最慢的一项。按公开反馈，自然积累到 500 名认证粉丝"
                     "通常需要 6–18 个月：科技/金融领域约 4–8 个月，娱乐/生活方式约 12–24 个月。")
    if isinstance(imp, (int, float)) and imp < 500000:
        notes.append("90 天曝光门槛需日均约 5,500 次认证用户曝光。从零开始通常需 1–3 个月"
                     "持续高频发布（长帖效率最高）。")

    any_hard_fail = any(r["status"] == "未达标" and r["hard"] for r in results)
    if any_hard_fail:
        notes.append("存在未通过的硬门槛。硬门槛无法通过内容或运营解决，"
                     "需要先处理主体资格（地区/收款/年龄/账号状态）。")
    return notes


def suggest(profile, ocr_results, sub_results):
    ocr_fail_soft = [r for r in ocr_results if r["status"] == "未达标" and not r["hard"]]
    ocr_fail_hard = [r for r in ocr_results if r["status"] == "未达标" and r["hard"]]
    ocr_missing = [r for r in ocr_results if r["status"] == "缺失"]
    sub_fail = [r for r in sub_results if r["status"] == "未达标"]
    sub_missing = [r for r in sub_results if r["status"] == "缺失"]

    out = []
    if ocr_fail_hard:
        out.append("**路径 A（Original Content Rewards）暂不可申请**——存在硬门槛缺口："
                   + "、".join(r["label"] for r in ocr_fail_hard))
    elif ocr_missing:
        # 缺失 != 通过。早期版本会把"没提供数据"误判成"已满足条件"，这里显式拦截。
        out.append("**路径 A 无法判定**——以下门槛缺少数据，不能视为已通过："
                   + "、".join(r["label"] for r in ocr_missing)
                   + "。补齐后再看结论。")
        if ocr_fail_soft:
            out.append("路径 A 已确认的缺口：" + "、".join(r["label"] for r in ocr_fail_soft) + "。")
    elif not ocr_fail_soft:
        out.append("**路径 A 已满足全部条件**——建议直接到 Creator Studio 提交申请，"
                   "以页面显示的实时条件为准。")
    else:
        out.append("**路径 A 尚未达标**，缺口：" + "、".join(r["label"] for r in ocr_fail_soft)
                   + "。其中资料类（头像/横幅/简介/2FA/邮箱）当天可补齐。")

    if sub_missing:
        out.append("**路径 B 无法判定**——以下门槛缺少数据，不能视为已通过："
                   + "、".join(r["label"] for r in sub_missing) + "。")
    elif not sub_fail:
        out.append("**路径 B（Creator Subscriptions）已满足条件**，可申请。")
    else:
        out.append("**路径 B 尚未达标**，缺口：" + "、".join(r["label"] for r in sub_fail) + "。")

    # 门槛不现实时，明确建议转向独立收入
    vf = profile.get("verified_followers") or 0
    if isinstance(vf, (int, float)) and vf < 500:
        out.append("**现实建议**：粉丝量在 5K 以下时，不应把平台分成当作主要目标。"
                   "优先级应是独立收入路径——赞助/接单/咨询/数字产品/联盟营销。"
                   "平台分成是规模上去之后的附加收益，不是起点。")
    return out


def render(profile, ocr_results, sub_results):
    L = ["# X 变现资格自检\n"]
    L.append("> ⚠️ X 变现规则变动频繁。本结果基于 2026 年 8–9 月公开信息整理，")
    L.append("> **最终以 `x.com/settings/monetization` 显示的实时条件为准。**\n")
    L.append("> 另注：Creator Revenue Sharing 已于 2026-09-07 退役，"
             "其曝光计酬职能由 **Original Content Rewards** 接替。\n")

    for title, results in (("路径 A：Original Content Rewards", ocr_results),
                           ("路径 B：Creator Subscriptions", sub_results)):
        passed = sum(1 for r in results if r["status"] == "通过")
        L.append(f"## {title}\n")
        L.append(f"**{passed}/{len(results)} 项通过**\n")
        L.append("| 门槛 | 现状 | 判定 | 类型 | 说明 |")
        L.append("|---|---|---|---|---|")
        for r in results:
            mark = {"通过": "通过", "未达标": "**未达标**", "缺失": "数据缺失"}[r["status"]]
            kind = "硬门槛" if r["hard"] else "软门槛"
            L.append(f"| {r['label']} | {r['value']} | {mark} | {kind} | {r['note']} |")
        L.append("")

    L.append("## 结论\n")
    for s in suggest(profile, ocr_results, sub_results):
        L.append(f"- {s}")
    L.append("")

    L.append("## 时间预期\n")
    timeline = estimate_timeline(profile, ocr_results)
    if timeline:
        for t in timeline:
            L.append(f"- {t}")
    else:
        L.append("- 主要门槛已满足，无显著时间缺口。")
    L.append("")
    L.append("_以上为参考区间，不是承诺。实际速度取决于内容质量、领域与受众地区。_\n")

    L.append("## 补充：受众地理对收益的影响\n")
    L.append("| 受众地区 | 每百万有效曝光参考收益 |")
    L.append("|---|---|")
    L.append("| 美国 | 约 $29.75 |")
    L.append("| 英国 | 约 $23.80 |")
    L.append("| 加拿大 | 约 $21.25 |")
    L.append("| 澳大利亚 | 约 $19.55 |")
    L.append("| 德国 | 约 $17.00 |")
    L.append("| 全球平均 | 约 $8.50 |")
    L.append("")
    L.append("受众地理分布对收入的影响**远超曝光量本身**。若受众主要在低系数地区，"
             "平台分成的天花板很低，应优先走独立收入路径。\n")

    return "\n".join(L)


def demo_profile():
    return {
        "premium": True, "verified_followers": 320, "followers": 8000,
        "impressions_90d": 1200000, "age_months": 14, "country": "US",
        "stripe_supported": True, "email_verified": True, "twofa": True,
        "avatar": True, "banner": False, "bio": True, "good_standing": True,
        "original_content": True, "age": 25, "active_30d": True,
    }


def main():
    ap = argparse.ArgumentParser(description="X 变现资格自检",
                                 formatter_class=argparse.RawDescriptionHelpFormatter,
                                 epilog=__doc__)
    ap.add_argument("--json", metavar="FILE", help="JSON 档案文件（- 表示 stdin）")
    ap.add_argument("--demo", action="store_true", help="使用内置样例")
    ap.add_argument("--out", metavar="FILE", help="写入文件")

    ap.add_argument("--premium", choices=["yes", "no"], help="是否持有 Premium")
    ap.add_argument("--verified-followers", type=float, help="认证粉丝数（持 Premium 的关注者）")
    ap.add_argument("--followers", type=float, help="总粉丝数")
    ap.add_argument("--impressions-90d", type=float, help="近 90 天认证用户曝光量")
    ap.add_argument("--age-months", type=float, help="账号已注册月数")
    ap.add_argument("--country", help="国家/地区代码，如 US / CN")
    ap.add_argument("--stripe-supported", choices=["yes", "no"],
                    help="所在国家是否支持绑定 Stripe 收款")
    ap.add_argument("--email-verified", choices=["yes", "no"])
    ap.add_argument("--twofa", choices=["yes", "no"], help="是否开启两步验证")
    ap.add_argument("--avatar", choices=["yes", "no"])
    ap.add_argument("--banner", choices=["yes", "no"])
    ap.add_argument("--bio", choices=["yes", "no"])
    ap.add_argument("--good-standing", choices=["yes", "no"])
    ap.add_argument("--original-content", choices=["yes", "no"])
    ap.add_argument("--age", type=float, help="持有人年龄")
    ap.add_argument("--active-30d", choices=["yes", "no"], help="近 30 天是否有活动")
    args = ap.parse_args()

    if args.demo:
        profile = demo_profile()
    elif args.json:
        text = sys.stdin.read() if args.json == "-" else open(args.json, encoding="utf-8").read()
        profile = json.loads(text)
    else:
        profile = {}
        for field in ["premium", "email_verified", "twofa", "avatar", "banner",
                      "bio", "good_standing", "original_content", "active_30d",
                      "stripe_supported"]:
            v = getattr(args, field)
            if v is not None:
                profile[field] = (v == "yes")
        for field in ["verified_followers", "followers", "impressions_90d",
                      "age_months", "age"]:
            v = getattr(args, field)
            if v is not None:
                profile[field] = v
        if args.country:
            profile["country"] = args.country.upper()
        # 未显式提供 stripe_supported 时，按已知列表预警
        if "stripe_supported" not in profile and profile.get("country"):
            if profile["country"] in KNOWN_STRIPE_UNSUPPORTED:
                profile["stripe_supported"] = False
                profile["country"] = profile["country"]

    if not profile:
        ap.print_help()
        return 1

    # 未显式提供 stripe_supported 时，按已知不支持列表预警
    country = profile.get("country")
    if "stripe_supported" not in profile and country:
        profile["stripe_supported"] = country not in KNOWN_STRIPE_UNSUPPORTED

    ocr = [check_gate(profile, g) for g in OCR_GATES]
    sub = [check_gate(profile, g) for g in SUB_GATES]

    # 把国家代码补进 Stripe 门槛的现状列，方便用户核对
    if country:
        for r in ocr:
            if r["label"].startswith("所在国家"):
                r["value"] = f"{country} / {'是' if r['status'] == '通过' else '否'}"

    output = render(profile, ocr, sub)
    if args.out:
        with open(args.out, "w", encoding="utf-8") as f:
            f.write(output)
        print(f"已写入 {args.out}", file=sys.stderr)
    else:
        print(output)
    return 0


if __name__ == "__main__":
    sys.exit(main())
