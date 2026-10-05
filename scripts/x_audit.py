#!/usr/bin/env python3
"""
x_audit.py — X 账号数据体检器

读取账号与帖子数据，计算机械指标、对比基准、识别异常，输出体检表与 L1 评分草稿。

用法:
  python3 x_audit.py --demo                      # 生成样例数据并体检
  python3 x_audit.py --json data.json            # 从 JSON 读入
  python3 x_audit.py --csv posts.csv --followers 1200 --following 800
  cat data.json | python3 x_audit.py             # 从 stdin 读入
  python3 x_audit.py --json data.json --format json

输入 JSON 结构:
{
  "account": {"handle": "@you", "followers": 1200, "following": 800,
              "created": "2024-01-15", "premium": false},
  "window_days": 28,
  "profile_visits": 340,
  "new_follows": 45,
  "posts": [
    {"text": "...", "date": "2026-09-01T09:00",
     "impressions": 1200, "likes": 30, "replies": 5,
     "retweets": 2, "bookmarks": 1, "profile_clicks": 3, "follows": 1,
     "type": "opinion"}
  ]
}

CSV 表头（大小写不敏感）:
  text,date,impressions,likes,replies,retweets,bookmarks,profile_clicks,follows,type

注意:
  - 所有比率计算以此脚本为准，不要心算。
  - 公开的互动率基准口径不一（差异可达百倍）。本脚本主判据为「曝光口径互动率」，
    粉丝口径仅作参考，且明确标注口径存疑。
"""

import argparse
import csv
import io
import json
import statistics
import sys
from datetime import datetime, timedelta

# ---------------------------------------------------------------- 基准定义

# 曝光口径互动率（总互动 ÷ 曝光）参考区间。
# 说明：公开来源口径混乱（0.015% ~ 3% 都有），以下为综合多来源的「方向性」区间，
# 用于相对定位，不是行业标准。
IMPRESSION_ER_BANDS = [
    (4.0, "优秀", "显著高于平台水平，内容与受众匹配度高"),
    (2.0, "良好", "高于平台均值（约 1.5%），属于健康区间"),
    (1.0, "正常", "接近平台均值，有提升空间"),
    (0.5, "偏低", "明显低于平台均值，需检查钩子与受众匹配"),
    (0.0, "弱", "严重偏低，优先排查内容类型与外链污染"),
]

# 粉丝口径互动率参考（来源标注为 follower-based，但量级与主流报告中位数严重矛盾，
# 口径存疑，仅用于同量级账号之间的相对比较）。
FOLLOWER_TIERS = [
    (1_000_000, "Mega", 0.2, 0.3),
    (200_000, "Macro", 0.5, 1.5),
    (50_000, "Mid-Tier", 1.0, 3.0),
    (5_000, "Micro", 3.0, 5.0),
    (0, "Nano", 5.0, 8.0),
]

# 单条爆款判定倍数
VIRAL_MULTIPLE = 3.0
# 主页访问占曝光的参考下限
PROFILE_CLICK_FLOOR = 0.005
# 回复/点赞比的参考下限（算法给回复 +13.5，点赞 +0.5）
REPLY_LIKE_FLOOR = 0.05


def band_for(value, bands):
    for threshold, label, note in bands:
        if value >= threshold:
            return label, note
    return bands[-1][1], bands[-1][2]


def tier_for(followers):
    for threshold, name, lo, hi in FOLLOWER_TIERS:
        if followers >= threshold:
            return name, lo, hi
    return "Nano", 5.0, 8.0


# ---------------------------------------------------------------- 数据载入

POST_FIELDS = ["text", "date", "impressions", "likes", "replies", "retweets",
               "bookmarks", "profile_clicks", "follows", "type"]

NUMERIC = ["impressions", "likes", "replies", "retweets", "bookmarks",
           "profile_clicks", "follows"]


def normalize_post(raw):
    post = {}
    for k in POST_FIELDS:
        v = raw.get(k)
        if k in NUMERIC:
            try:
                post[k] = float(v) if v not in (None, "", "null") else 0.0
            except (TypeError, ValueError):
                post[k] = 0.0
        else:
            post[k] = (str(v).strip() if v not in (None, "null") else "")
    return post


def load_json(text):
    data = json.loads(text)
    account = data.get("account", {}) or {}
    posts = [normalize_post(p) for p in data.get("posts", [])]
    return {
        "account": account,
        "posts": posts,
        "profile_visits": data.get("profile_visits"),
        "account_impressions": data.get("account_impressions"),
        "new_follows": data.get("new_follows"),
        "window_days": data.get("window_days"),
    }


def load_csv(text, followers=None, following=None):
    reader = csv.DictReader(io.StringIO(text))
    posts = []
    for row in reader:
        low = {(k or "").strip().lower(): v for k, v in row.items()}
        posts.append(normalize_post(low))
    account = {}
    if followers is not None:
        account["followers"] = followers
    if following is not None:
        account["following"] = following
    return {"account": account, "posts": posts,
            "profile_visits": None, "new_follows": None, "window_days": None}


# ---------------------------------------------------------------- 计算

def total_interactions(p):
    """算法相关互动的加总（不含曝光）。"""
    return p["likes"] + p["replies"] + p["retweets"] + p["bookmarks"]


def analyze(dataset):
    posts = dataset["posts"]
    account = dataset["account"]
    followers = float(account.get("followers") or 0)
    following = float(account.get("following") or 0)

    if not posts:
        return {"error": "没有帖子数据，无法体检。请提供至少 5 条帖子的数据。"}

    for p in posts:
        p["_interactions"] = total_interactions(p)
        p["_er_imp"] = (p["_interactions"] / p["impressions"] * 100) if p["impressions"] > 0 else 0.0
        p["_er_fol"] = (p["_interactions"] / followers * 100) if followers > 0 else 0.0

    # 注意：粉丝口径互动率是「单帖」指标。用 N 条帖子的互动总和除以粉丝数会
    # 虚高约 N 倍，必须用单帖平均互动数除以粉丝数。

    n = len(posts)
    sum_imp = sum(p["impressions"] for p in posts)
    sum_int = sum(p["_interactions"] for p in posts)
    sum_likes = sum(p["likes"] for p in posts)
    sum_replies = sum(p["replies"] for p in posts)
    sum_rt = sum(p["retweets"] for p in posts)
    sum_bm = sum(p["bookmarks"] for p in posts)
    sum_pc = sum(p["profile_clicks"] for p in posts)

    er_imp = (sum_int / sum_imp * 100) if sum_imp > 0 else 0.0
    # 粉丝口径：单帖平均互动 ÷ 粉丝数（不是总和 ÷ 粉丝数）
    er_fol = ((sum_int / n) / followers * 100) if followers > 0 else 0.0
    per_post_er = [p["_er_imp"] for p in posts]
    median_er = statistics.median(per_post_er) if per_post_er else 0.0
    avg_er = statistics.fmean(per_post_er) if per_post_er else 0.0

    # 曝光分布：均值 vs 中位数。
    # 均值极易被单条爆量帖子拉高，进而把四象限的「分发」判定带偏，
    # 因此两者都要算，并在偏度大时以中位数为准。
    impressions_list = [p["impressions"] for p in posts]
    median_imp = statistics.median(impressions_list) if impressions_list else 0.0
    avg_imp = sum_imp / n
    mean_median_skew = (avg_imp / median_imp) if median_imp > 0 else 0.0
    reach_ratio_mean = (avg_imp / followers) if followers > 0 else 0.0
    reach_ratio_median = (median_imp / followers) if followers > 0 else 0.0
    zero_interaction_share = (sum(1 for p in posts if p["_interactions"] == 0) / n * 100)

    mean_int = sum_int / n
    viral = [p for p in posts if mean_int > 0 and p["_interactions"] >= VIRAL_MULTIPLE * mean_int]
    viral_rate = len(viral) / n * 100

    sorted_posts = sorted(posts, key=lambda p: p["_interactions"], reverse=True)
    top = sorted_posts[:3]
    bottom = sorted_posts[-3:][::-1]

    reply_like = (sum_replies / sum_likes) if sum_likes > 0 else 0.0
    profile_click_rate = (sum_pc / sum_imp) if sum_imp > 0 else 0.0

    # 主页访问数：优先用账号级数据，缺失则用帖子级 profile_clicks 加总。
    # 两者都拿不到时标记为「缺失」，不能当成 0 处理（否则会产生假预警）。
    #
    # ⚠️ 窗口一致性：profile_visits 通常来自后台（如近 28 天），而 posts 可能只是
    # 最近 2 天的样本。若直接相除，会得到一个毫无意义的比率（可能虚高十几倍）。
    # 因此要求同时提供 account_impressions（与 profile_visits 同窗口的后台曝光总量）。
    pv = dataset.get("profile_visits")
    acc_imp = dataset.get("account_impressions")
    profile_conv_known = True
    if pv is None:
        if sum_pc > 0:
            pv = sum_pc
        else:
            pv = 0.0
            profile_conv_known = False
    if acc_imp and float(acc_imp) > 0:
        profile_conv = (float(pv) / float(acc_imp)) if profile_conv_known else None
        profile_conv_basis = f"账号级曝光 {float(acc_imp):,.0f}（与主页访问同窗口）"
    else:
        profile_conv = (float(pv) / sum_imp) if (sum_imp > 0 and profile_conv_known) else None
        profile_conv_basis = "帖子样本曝光合计"
    # 只给了主页访问、没给同窗口曝光 → 分母可能错窗口，必须提示
    window_mismatch = bool(profile_conv_known and pv and not acc_imp)

    # 内容类型分布
    by_type = {}
    for p in posts:
        t = p["type"] or "未标注"
        slot = by_type.setdefault(t, {"count": 0, "interactions": 0.0, "impressions": 0.0})
        slot["count"] += 1
        slot["interactions"] += p["_interactions"]
        slot["impressions"] += p["impressions"]
    for t, slot in by_type.items():
        slot["share"] = slot["count"] / n * 100
        slot["avg_interactions"] = slot["interactions"] / slot["count"] if slot["count"] else 0
        slot["er_imp"] = (slot["interactions"] / slot["impressions"] * 100) if slot["impressions"] > 0 else 0.0

    # 时段分析（仅在有可解析时间时）
    by_hour = {}
    for p in posts:
        if not p["date"]:
            continue
        try:
            dt = datetime.fromisoformat(p["date"].replace("Z", ""))
        except ValueError:
            continue
        slot = by_hour.setdefault(dt.hour, {"count": 0, "interactions": 0.0, "impressions": 0.0})
        slot["count"] += 1
        slot["interactions"] += p["_interactions"]
        slot["impressions"] += p["impressions"]

    # 关注比例安全线（TweepCred 双条件）
    follow_ratio = (following / followers) if followers > 0 else float("inf") if following > 0 else 0.0
    follow_risk = None
    if following > 2500 and follow_ratio > 0.6:
        follow_risk = "高"
    elif following > 500 and follow_ratio > 0.6:
        follow_risk = "中"
    elif following > 500:
        follow_risk = "低（比例尚可，但已过 500 阈值）"
    else:
        follow_risk = "无（500 以内安全）"

    return {
        "account": account,
        "followers": followers,
        "following": following,
        "n_posts": n,
        "sum_impressions": sum_imp,
        "sum_interactions": sum_int,
        "avg_impressions": sum_imp / n,
        "median_impressions": median_imp,
        "mean_median_skew": mean_median_skew,
        "reach_ratio_mean": reach_ratio_mean,
        "reach_ratio_median": reach_ratio_median,
        "zero_interaction_share": zero_interaction_share,
        "avg_interactions": mean_int,
        "er_imp": er_imp,
        "er_fol": er_fol,
        "avg_per_post_er": avg_er,
        "median_per_post_er": median_er,
        "sum_likes": sum_likes,
        "sum_replies": sum_replies,
        "sum_retweets": sum_rt,
        "sum_bookmarks": sum_bm,
        "reply_like_ratio": reply_like,
        "profile_visits": float(pv),
        "profile_conv": profile_conv,
        "profile_conv_basis": profile_conv_basis,
        "window_mismatch": window_mismatch,
        "profile_click_rate": profile_click_rate,
        "new_follows": dataset.get("new_follows"),
        "viral_count": len(viral),
        "viral_rate": viral_rate,
        "top": top,
        "bottom": bottom,
        "by_type": by_type,
        "by_hour": by_hour,
        "follow_ratio": follow_ratio,
        "follow_risk": follow_risk,
        "window_days": dataset.get("window_days"),
    }


# ---------------------------------------------------------------- L1 评分

def score_l1(r):
    """数据健康维度（满分 12）的草稿评分。"""
    score = 0.0
    notes = []

    # 互动率（曝光口径）：最多 5 分
    band, _ = band_for(r["er_imp"], IMPRESSION_ER_BANDS)
    band_points = {"优秀": 5.0, "良好": 4.0, "正常": 2.5, "偏低": 1.0, "弱": 0.0}[band]
    score += band_points
    notes.append(f"曝光口径互动率 {r['er_imp']:.2f}% → 判定「{band}」（{band_points}/5）")

    # 回复/点赞比：最多 3 分（算法给回复 +13.5、点赞 +0.5）
    rl = r["reply_like_ratio"]
    if rl >= 0.15:
        rl_points = 3.0
    elif rl >= REPLY_LIKE_FLOOR:
        rl_points = 2.0
    elif rl >= 0.02:
        rl_points = 1.0
    else:
        rl_points = 0.0
    score += rl_points
    notes.append(f"回复/点赞比 {rl:.3f} → {rl_points}/3（算法给回复 +13.5、点赞 +0.5，此比偏低说明没拿到主要红利）")

    # 主页转化率：最多 2 分
    pc = r["profile_conv"]
    if pc is None:
        pc_points = 0.0
        notes.append("主页访问数据缺失 → 0/2（无法评估转化层。建议补充后台的「主页访问」数据）")
    else:
        if pc >= 0.02:
            pc_points = 2.0
        elif pc >= PROFILE_CLICK_FLOOR:
            pc_points = 1.0
        else:
            pc_points = 0.0
        notes.append(f"主页访问/曝光 {pc*100:.2f}% → {pc_points}/2（低于 0.5% 说明内容没激发「想认识你」）")
    score += pc_points

    # 爆款率：最多 2 分
    vr = r["viral_rate"]
    if vr >= 15:
        v_points = 2.0
    elif vr >= 5:
        v_points = 1.0
    else:
        v_points = 0.0
    score += v_points
    notes.append(f"爆款率 {vr:.1f}%（≥3× 均值的帖子占比）→ {v_points}/2（低于 5% 说明缺乏稳定的引爆能力）")

    return round(min(score, 12.0), 1), notes


def compute_flags(r):
    """把指标翻译成可执行预警。每条预警 = 问题 + 依据 + 动作。"""
    flags = []
    n = r["n_posts"]
    by_type = r["by_type"]

    def share_of(name):
        s = by_type.get(name)
        return (s["share"] if s else 0.0)

    # 分布健康度：先看整体分布，再看具体类型
    if r.get("mean_median_skew", 0) >= 2.0:
        flags.append(("中", f"曝光分布被单条帖子主导（均值/中位数 = {r['mean_median_skew']:.1f}×）",
                      "均值口径会让「单帖平均曝光」看起来正常，掩盖大多数帖子分发不足的事实",
                      "改用中位数评估分发；同时解剖那条高曝光帖子，看曝光来自推荐还是搜索、能否复制"))
    if r.get("zero_interaction_share", 0) >= 50:
        flags.append(("高", f"零互动帖占比 {r['zero_interaction_share']:.1f}%",
                      "超过一半的帖子没有任何回应。这更像分发问题（帖子没被推出去），而不是内容质量问题",
                      "先降发帖密度（同作者衰减 ×0.625/×0.4375），再检查钩子；不要用「多发」解决「没人理」"))

    link_share = share_of("link")
    rt_share = share_of("retweet")
    daily_share = share_of("daily")

    if link_share >= 20:
        flags.append(("高", f"外链帖占比 {link_share:.0f}%",
                      "免费账号的外链帖子自 2025-03 起近乎零分发，会拖累整体曝光",
                      "立即停止在帖子里放外链；链接改放评论区首条或简介"))
    elif link_share > 0:
        flags.append(("低", f"存在外链帖（占比 {link_share:.0f}%）",
                      "外链在免费账号中分发极差",
                      "评估是否必要；若非必要，改用「评论区放链接」的形式"))

    if rt_share >= 20:
        flags.append(("中", f"纯转发占比 {rt_share:.0f}%",
                      "纯转发是算法中互动最低的格式，且不产生你自己的内容面",
                      "改用「引用 + 你的观点」，多一个内容面和对话入口"))

    if daily_share >= 25:
        flags.append(("中", f"与定位无关的日常内容占比 {daily_share:.0f}%",
                      "会稀释账号的社区标签（SimClusters），让算法难以给你贴清晰标签",
                      "压缩到 10% 以内；日常内容也要挂在你的专业视角下"))

    if r["reply_like_ratio"] < REPLY_LIKE_FLOOR:
        flags.append(("高", f"回复/点赞比仅 {r['reply_like_ratio']:.3f}",
                      "算法给回复 +13.5、点赞 +0.5（27 倍差），说明你没拿到主要算法红利",
                      "改内容结构：每条帖子结尾加一个真正想听回答的问题；每天回 3–5 条领域大号评论"))

    if r["profile_conv"] is None:
        flags.append(("低", "主页访问数据缺失",
                      "无法评估「曝光 → 主页 → 关注」的转化漏斗中段",
                      "从 X Analytics 补「主页访问数」，这是判断门面好坏的唯一依据"))
    elif r.get("window_mismatch"):
        flags.append(("中", "主页访问率的分母窗口不一致，结论不可信",
                      "主页访问数来自后台（如近 28 天），但曝光分母只是帖子样本的合计，"
                      "两者窗口不同，相除会得到虚高的比率",
                      "补一个 account_impressions 字段（与主页访问同窗口的后台曝光总量）后重跑"))
    elif r["profile_conv"] < PROFILE_CLICK_FLOOR:
        flags.append(("高", f"主页访问/曝光仅 {r['profile_conv']*100:.2f}%",
                      "低于 0.5% 参考下限，说明内容没有激发「想认识你」的冲动",
                      "检查首行钩子；同时在内容中植入「我是谁」的信号（案例、成果、身份）"))

    if r["viral_rate"] < 5:
        flags.append(("中", f"爆款率 {r['viral_rate']:.1f}%（≥3× 均值）",
                      "低于 5% 说明缺乏稳定可复制的引爆能力，增长依赖运气",
                      "对 Top 3 帖子做结构解剖，把有效结构固化成模板反复用"))

    if r["follow_risk"] in ("中", "高"):
        flags.append(("高" if r["follow_risk"] == "高" else "中",
                      f"关注比例风险：{r['follow_risk']}（关注 {r['following']:,.0f} / 粉丝 {r['followers']:,.0f}，比值 {r['follow_ratio']:.2f}）",
                      "关注 > 500 且比值 > 0.6 会触发 TweepCred 基础分指数衰减；关注 > 2500 时 PageRank 最高除以 50",
                      "修剪关注列表至安全线（关注数 ≤ 0.6 × 粉丝数）；取关不会损伤你的信誉"))

    if r["followers"] > 0:
        reach_ratio = r["avg_impressions"] / r["followers"]
        if reach_ratio < 0.15:
            flags.append(("高", f"单帖平均曝光仅为粉丝数的 {reach_ratio*100:.0f}%",
                          "低于 15% 说明分发受限，帖子没有被推到粉丝时间线之外",
                          "走限流自查流程；同时检查发布时段与领域关键词"))

    # 时段过度分散
    if len(r["by_hour"]) >= 6:
        flags.append(("低", f"发布时段分散在 {len(r['by_hour'])} 个不同小时",
                      "过于分散难以形成稳定的受众预期，也不利于识别最佳时段",
                      "收敛到 1–2 个固定时段，连续两周后再对比数据"))

    # 高互动低曝光 vs 低互动高曝光
    hi_er_low_imp = [p for p in r["top"] if p["_er_imp"] >= 3.0 and p["impressions"] < r["avg_impressions"] * 0.5]
    if hi_er_low_imp:
        flags.append(("中", f"{len(hi_er_low_imp)} 条高互动率帖子的曝光远低于均值",
                      "内容质量没问题，但没被推出去——这是分发/时机问题，不是内容问题",
                      "把这类内容换到受众活跃时段重发，或做成 Thread 二次分发"))

    return flags


def diagnose_quadrant(r):
    """四象限排除法：先判分发问题还是内容问题。"""
    band, _ = band_for(r["er_imp"], IMPRESSION_ER_BANDS)
    followers = r["followers"]

    # 偏度保护：单条爆量帖子会把均值曝光拉高，使 reach_ratio 越过 0.15 阈值，
    # 从而把「分发受限」误判成「分发正常」。均值 ≥2× 中位数时改用中位数口径。
    skew = r.get("mean_median_skew") or 0.0
    if followers > 0 and skew >= 2.0:
        reach_ratio = r.get("reach_ratio_median") or 0.0
        reach_basis = f"中位数口径（均值/中位数={skew:.1f}×，均值被异常值主导）"
    else:
        reach_ratio = (r["avg_impressions"] / followers) if followers > 0 else 0.0
        reach_basis = "均值口径"

    if followers > 0:
        if reach_ratio >= 0.5:
            reach_label = "分发正常（单帖曝光 ≥ 粉丝数的 50%）"
        elif reach_ratio >= 0.15:
            reach_label = "分发偏弱（单帖曝光约为粉丝数的 15%–50%）"
        else:
            reach_label = "分发受限（单帖曝光 < 粉丝数的 15%）"
    else:
        reach_label = "无法判断（缺少粉丝数）"

    er_weak = band in ("偏低", "弱")
    reach_weak = followers > 0 and reach_ratio < 0.15

    if reach_weak and not er_weak:
        verdict = "分发问题为主"
        action = "优先处理分发：检查发布时段、领域关键词、社群分发、账号权重与限流自查"
    elif not reach_weak and er_weak:
        verdict = "内容问题为主"
        action = "优先处理内容：检查首行钩子、受众匹配、格式（外链污染？）、观点强度"
    elif reach_weak and er_weak:
        verdict = "分发与内容双重问题"
        action = "先修内容（成本低、可控），再处理分发；同时排查是否被限流"
    else:
        verdict = "分发与内容均正常"
        action = "转向转化层：检查简介、置顶帖、头像、CTA（主页转化）"

    return {"verdict": verdict, "action": action, "reach_label": reach_label,
            "reach_basis": reach_basis, "reach_ratio": reach_ratio,
            "er_band": band, "zero_interaction_share": r.get("zero_interaction_share")}


# ---------------------------------------------------------------- 输出

def render_markdown(r, score, notes, quad, flags):
    L = []
    a = r["account"]
    handle = a.get("handle", "（未提供）")
    tier, lo, hi = tier_for(r["followers"])

    L.append("# X 账号数据体检表\n")
    L.append(f"**账号**：{handle}　**粉丝**：{r['followers']:,.0f}　"
             f"**关注**：{r['following']:,.0f}　**样本**：{r['n_posts']} 条帖子\n")
    if r.get("window_days"):
        L.append(f"**统计窗口**：{r['window_days']} 天\n")
    L.append("")

    L.append("## 一、核心指标\n")
    L.append("| 指标 | 数值 | 说明 |")
    L.append("|---|---|---|")
    L.append(f"| 曝光总量 | {r['sum_impressions']:,.0f} | |")
    L.append(f"| 单帖平均曝光 | {r['avg_impressions']:,.0f} | 易被单条爆量帖拉高，勿单独使用 |")
    L.append(f"| **单帖曝光中位数** | **{r.get('median_impressions', 0):,.0f}** | 更接近「一条普通帖子」的真实量级 |")
    L.append(f"| 单帖曝光/粉丝（均值） | {r.get('reach_ratio_mean', 0)*100:.1f}% | 健康参考 ≥15% |")
    L.append(f"| 单帖曝光/粉丝（中位数） | {r.get('reach_ratio_median', 0)*100:.1f}% | 健康参考 ≥15% |")
    L.append(f"| 零互动帖占比 | {r.get('zero_interaction_share', 0):.1f}% | 越低越好；偏高说明多数帖子无人回应 |")
    L.append(f"| 互动总量 | {r['sum_interactions']:,.0f} | 赞+回复+转推+收藏 |")
    L.append(f"| **互动率（曝光口径）** | **{r['er_imp']:.2f}%** | 主判据 |")
    L.append(f"| 互动率（粉丝口径，单帖） | {r['er_fol']:.2f}% | 口径存疑，仅作同量级相对比较 |")
    L.append(f"| 单帖互动率中位数 | {r['median_per_post_er']:.2f}% | 排除爆款拉高均值 |")
    L.append(f"| 回复/点赞比 | {r['reply_like_ratio']:.3f} | 算法：回复 +13.5 vs 点赞 +0.5 |")
    if r["profile_conv"] is None:
        pc_display, pc_note = "缺失", "未提供主页访问数据，无法评估转化层"
    else:
        pc_display = f"{r['profile_conv']*100:.2f}%"
        pc_note = ("低于 0.5%，内容没激发「想认识你」的冲动" if r["profile_conv"] < PROFILE_CLICK_FLOOR
                   else "在参考区间内" if r["profile_conv"] < 0.02 else "表现良好，主页承接能力强")
        pc_note = f"{pc_note}（分母：{r.get('profile_conv_basis', '—')}）"
        if r.get("window_mismatch"):
            pc_note += " ⚠️ 窗口可能不一致，此比率不可信"
    L.append(f"| 主页访问/曝光 | {pc_display} | {pc_note} |")
    L.append(f"| 爆款率 | {r['viral_rate']:.1f}% | ≥3× 均值的帖子占比 |")
    if r.get("new_follows") is not None:
        L.append(f"| 新增关注 | {r['new_follows']} | |")
    L.append("")

    L.append("## 二、基准对比\n")
    band, band_note = band_for(r["er_imp"], IMPRESSION_ER_BANDS)
    L.append(f"- **曝光口径互动率 {r['er_imp']:.2f}% → 判定：{band}**（{band_note}）")
    L.append(f"  - 平台参考：均值约 1.5%，良好区间 2%–4%，优秀 > 4%（公开口径混乱，此为方向性参考）")
    L.append(f"- 账号量级：**{tier}**（粉丝 {r['followers']:,.0f}）")
    L.append(f"  - 该量级粉丝口径互动率参考区间 {lo}%–{hi}%（口径存疑，仅作同量级相对比较，勿与曝光口径混用）")
    L.append("")

    L.append("## 三、四象限排除法\n")
    L.append(f"- 分发判断：{quad['reach_label']}（{quad.get('reach_basis', '均值口径')}）")
    L.append(f"- 互动率判定：{quad['er_band']}")
    if r.get("mean_median_skew", 0) >= 2.0:
        L.append(f"- ⚠️ 曝光分布偏度高：均值是中位数的 {r['mean_median_skew']:.1f} 倍，"
                 f"说明有单条帖子主导了均值。**此时不要用均值下结论**，"
                 f"以中位数（{r.get('median_impressions', 0):,.0f}）为准。")
    if r.get("zero_interaction_share", 0) >= 50:
        L.append(f"- ⚠️ 零互动帖占比 {r['zero_interaction_share']:.1f}%，"
                 f"说明大多数帖子没有引起任何回应——这通常指向分发问题，而非内容质量问题。")
    L.append(f"- **结论：{quad['verdict']}**")
    L.append(f"- **处方方向：{quad['action']}**")
    L.append("")

    L.append("## 四、预警清单\n")
    if flags:
        order = {"高": 0, "中": 1, "低": 2}
        for lvl, title, why, todo in sorted(flags, key=lambda f: order.get(f[0], 3)):
            L.append(f"**[{lvl}] {title}**")
            L.append(f"- 依据：{why}")
            L.append(f"- 动作：{todo}")
            L.append("")
    else:
        L.append("_未触发预警。_")
        L.append("")

    L.append("## 五、内容类型分布\n")
    if r["by_type"]:
        L.append("| 类型 | 条数 | 占比 | 平均互动 | 曝光口径互动率 |")
        L.append("|---|---|---|---|---|")
        for t, s in sorted(r["by_type"].items(), key=lambda kv: -kv[1]["count"]):
            L.append(f"| {t} | {s['count']} | {s['share']:.0f}% | {s['avg_interactions']:.1f} | {s['er_imp']:.2f}% |")
    else:
        L.append("_未标注内容类型，无法分析配比。建议在数据里补 `type` 字段。_")
    L.append("")

    L.append("## 六、Top 3 / Bottom 3\n")
    L.append("**表现最好**\n")
    L.append("| 互动 | 曝光 | 互动率 | 内容摘要 |")
    L.append("|---|---|---|---|")
    for p in r["top"]:
        L.append(f"| {p['_interactions']:.0f} | {p['impressions']:.0f} | {p['_er_imp']:.2f}% | {shorten(p['text'])} |")
    L.append("")
    L.append("**表现最差**\n")
    L.append("| 互动 | 曝光 | 互动率 | 内容摘要 |")
    L.append("|---|---|---|---|")
    for p in r["bottom"]:
        L.append(f"| {p['_interactions']:.0f} | {p['impressions']:.0f} | {p['_er_imp']:.2f}% | {shorten(p['text'])} |")
    L.append("")

    if r["by_hour"]:
        L.append("## 七、发布时段\n")
        L.append("| 小时 | 条数 | 平均曝光 | 平均互动 |")
        L.append("|---|---|---|---|")
        for h in sorted(r["by_hour"]):
            s = r["by_hour"][h]
            L.append(f"| {h:02d}:00 | {s['count']} | {s['impressions']/s['count']:.0f} | {s['interactions']/s['count']:.1f} |")
        L.append("")

    L.append("## 八、账号安全线\n")
    L.append(f"- 关注/粉丝比：{r['follow_ratio']:.2f}（关注 {r['following']:,.0f} / 粉丝 {r['followers']:,.0f}）")
    L.append(f"- 关注比例风险：**{r['follow_risk']}**")
    L.append(f"  - 规则：关注 > 500 且 关注/粉丝 > 0.6 触发基础分惩罚；关注 > 2500 时 PageRank 最高除以 50")
    L.append("")

    L.append("## 九、L1 数据健康评分（草稿）\n")
    L.append(f"**{score} / 12**\n")
    for note in notes:
        L.append(f"- {note}")
    L.append("")
    L.append("> 这是**机械计算**的草稿分。最终评分需结合 L2 内容、L3 定位的定性判断，"
             "在诊断报告中由人工调整并附证据。")
    L.append("")

    return "\n".join(L)


def shorten(text, limit=44):
    t = (text or "").replace("\n", " ").strip()
    return (t[:limit] + "…") if len(t) > limit else (t or "（无文本）")


# ---------------------------------------------------------------- 样例数据

def demo_dataset():
    base = datetime(2026, 9, 1, 9, 0)
    raw_posts = [
        ("大部分人做 X 都做反了：粉丝数不是资产，关系才是。断更一周，你和所有人的关系强度掉一半。",
         9, 5200, 96, 41, 18, 12, 26, 7, "opinion"),
        ("我用 3 个月把互动率从 0.4% 提到 2.1%，只改了三个地方：1) 首行换钩子 2) 砍掉所有外链 3) 每天回 5 条评论。",
         9, 3100, 58, 22, 31, 24, 19, 5, "list"),
        ("算法给回复 13.5 分，给点赞只有 0.5 分。所以一条 20 赞 8 回复的帖子，比 200 赞 0 回复的值钱得多。",
         10, 2400, 71, 33, 14, 9, 21, 4, "opinion"),
        ("新号头 30 天的目标不是涨粉，是让算法学会你是谁。",
         10, 1800, 44, 15, 8, 5, 12, 3, "opinion"),
        ("整理了 7 个免费的数据分析工具，做增长必备：",
         11, 950, 31, 4, 9, 22, 6, 1, "list"),
        ("今天试了一个新的写作流程，效果还行。",
         11, 620, 12, 1, 0, 1, 2, 0, "daily"),
        ("最近在读《 positioning 》，有点感想。",
         12, 480, 8, 0, 0, 1, 1, 0, "daily"),
        ("我的完整增长方法论，新文章发布 → 链接在评论区",
         12, 210, 3, 0, 1, 0, 0, 0, "link"),
        ("转发一条行业新闻。",
         13, 180, 2, 0, 0, 0, 0, 0, "retweet"),
        ("周末去哪玩？",
         13, 340, 5, 1, 0, 0, 1, 0, "daily"),
        ("Thread：拆解一条 10 万曝光的帖子，它做对了什么？1/8",
         14, 12400, 318, 86, 152, 128, 74, 19, "thread"),
        ("很多人问我怎么选赛道。答案很简单：选你能连续写 100 条的那个。",
         14, 2100, 63, 24, 11, 8, 17, 4, "opinion"),
        ("数据：X 平台互动率 2023→2024 跌了 48%，但 2025 反弹了 19%。",
         15, 1600, 39, 9, 16, 14, 9, 2, "list"),
        ("别买粉。僵尸号没有粉丝，点赞传播链直接断，白买。",
         15, 2700, 88, 36, 21, 11, 25, 5, "opinion"),
        ("新做了一个 landing page，欢迎提意见 → 链接",
         16, 190, 4, 1, 0, 0, 1, 0, "link"),
    ]
    posts = []
    for i, (text, day, imp, likes, replies, rt, bm, pc, fl, typ) in enumerate(raw_posts):
        posts.append({
            "text": text,
            "date": (base + timedelta(days=day - 9, hours=(i % 5) * 2)).isoformat(),
            "impressions": imp, "likes": likes, "replies": replies,
            "retweets": rt, "bookmarks": bm, "profile_clicks": pc,
            "follows": fl, "type": typ,
        })
    return {
        "account": {"handle": "@demo_creator", "followers": 1240, "following": 610,
                    "created": "2024-06-01", "premium": True},
        "window_days": 28,
        "profile_visits": 386,
        "new_follows": 52,
        "posts": posts,
    }


# ---------------------------------------------------------------- 主流程

def main():
    ap = argparse.ArgumentParser(
        description="X 账号数据体检器",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=__doc__,
    )
    src = ap.add_mutually_exclusive_group()
    src.add_argument("--json", metavar="FILE", help="JSON 数据文件（- 表示 stdin）")
    src.add_argument("--csv", metavar="FILE", help="CSV 帖子数据文件（- 表示 stdin）")
    src.add_argument("--demo", action="store_true", help="使用内置样例数据")
    ap.add_argument("--followers", type=float, help="粉丝数（CSV 模式下必填）")
    ap.add_argument("--following", type=float, help="关注数")
    ap.add_argument("--format", choices=["markdown", "json"], default="markdown",
                    help="输出格式（默认 markdown）")
    ap.add_argument("--out", metavar="FILE", help="写入文件而非打印")
    args = ap.parse_args()

    if args.demo:
        dataset = demo_dataset()
    elif args.json:
        text = sys.stdin.read() if args.json == "-" else open(args.json, encoding="utf-8").read()
        dataset = load_json(text)
    elif args.csv:
        text = sys.stdin.read() if args.csv == "-" else open(args.csv, encoding="utf-8").read()
        dataset = load_csv(text, args.followers, args.following)
    else:
        if sys.stdin.isatty():
            ap.print_help()
            return 1
        text = sys.stdin.read()
        dataset = load_json(text) if text.lstrip().startswith("{") else load_csv(
            text, args.followers, args.following)

    if args.followers is not None:
        dataset["account"]["followers"] = args.followers
    if args.following is not None:
        dataset["account"]["following"] = args.following

    result = analyze(dataset)
    if "error" in result:
        print(f"错误：{result['error']}", file=sys.stderr)
        return 1

    score, notes = score_l1(result)
    quad = diagnose_quadrant(result)
    flags = compute_flags(result)

    if args.format == "json":
        payload = {
            "summary": {k: v for k, v in result.items()
                        if k not in ("top", "bottom", "by_type", "by_hour", "account")},
            "quadrant": quad,
            "flags": [{"level": f[0], "title": f[1], "reason": f[2], "action": f[3]} for f in flags],
            "l1_score": score,
            "l1_notes": notes,
            "top": [{k: v for k, v in p.items() if not k.startswith("_")} for p in result["top"]],
            "bottom": [{k: v for k, v in p.items() if not k.startswith("_")} for p in result["bottom"]],
            "by_type": result["by_type"],
            "by_hour": result["by_hour"],
        }
        output = json.dumps(payload, ensure_ascii=False, indent=2)
    else:
        output = render_markdown(result, score, notes, quad, flags)

    if args.out:
        with open(args.out, "w", encoding="utf-8") as f:
            f.write(output)
        print(f"已写入 {args.out}", file=sys.stderr)
    else:
        print(output)
    return 0


if __name__ == "__main__":
    sys.exit(main())
