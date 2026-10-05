# X Self-Media Audit · X 自媒体账号诊断

> 对**个人 X（Twitter）账号**做端到端体检：账号数据、内容表现、人设定位、平台算法与合规规则 —— 然后给出**方向性建议 + 内容体系 + 30/60/90 天实操计划**。

[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](LICENSE)
![Language](https://img.shields.io/badge/lang-中文%20%7C%20English-blue)
![Python](https://img.shields.io/badge/python-3.8%2B-blue)

---

## 🚀 一键安装

复制下面这一行，粘到终端回车即可：

```bash
curl -fsSL https://raw.githubusercontent.com/marslwc/x-selfmedia-audit/main/install.sh | bash
```

脚本会自动完成：检测技能目录 → 下载文件 → 校验 Python 环境 → 跑通自检 → 打印下一步。

**自定义安装位置：**

```bash
curl -fsSL https://raw.githubusercontent.com/marslwc/x-selfmedia-audit/main/install.sh | SKILLS_DIR=~/my-skills bash
```

**用 git 安装**（想随时 `git pull` 更新的话）：

```bash
git clone https://github.com/marslwc/x-selfmedia-audit.git \
  ~/.workbuddy-ai/skills/x-selfmedia-audit
```

> 重复执行安装命令是安全的：检测到已有安装时会自动走 `git pull` 更新，不会重复下载。
>
> **无需 X API key，无需 pip install** —— 两个脚本只用 Python 标准库。

---

## ⚡ 30 秒看效果（不用安装，不用给数据）

```bash
git clone --depth 1 https://github.com/marslwc/x-selfmedia-audit.git /tmp/xsa && \
python3 /tmp/xsa/scripts/x_audit.py --demo
```

会打印一份完整的模拟账号体检表，包含互动率、基准对比、四象限判定和预警清单。

---

## ✅ 运行测试

仓库带一套回归测试，覆盖三个已修复的真实误诊 bug：

```bash
python3 tests/test_regressions.py
```

只用标准库，不需要装 pytest。当前 **22 项全部通过**。

测试覆盖的关键场景：

| 场景 | 期望行为 |
|---|---|
| 单条爆量帖把均值拉高 20 倍 | 四象限**不得**判定为「分发正常」，须切换中位数口径 |
| 零互动帖占比 ≥50% | 触发分发侧预警，且**不开**「多发帖」处方 |
| 数据健康的账号 | 偏度保护**不得**误触发，仍走均值口径 |
| 变现资格数据全缺 | 输出「无法判定」，**不得**输出「已满足条件」 |
| 变现硬门槛缺口 | 阻断路径 A 并标注硬门槛 |
| 内置样例数据 | 两个脚本 `--demo` 仍可正常运行 |

---

## 它解决什么问题

大多数创作者卡住的时候，得到的建议是"多发帖""提升内容质量""多互动"——这些都不是可执行的建议。

这个技能试图回答三个具体问题：

1. **我的账号到底哪里出了问题？** 是内容不行，还是分发不行，还是主页接不住流量？
2. **我该往哪个方向走？** 涨粉、变现、接单、引流——不同目标对应完全不同的打法。
3. **明天开始具体做什么？** 发什么、什么时候发、怎么写钩子、什么时候复盘。

它特别擅长识别一种最常见的误诊：**数据看着不错，但账号其实不健康**。比如互动率很高，但全部来自一条爆款，其余内容在浪费产能。

---

## 它输出什么

一份 Markdown 诊断报告，包含：

| 模块 | 内容 |
|---|---|
| **一句话结论** | 最核心的问题 + 最该先做的事 |
| **9 维评分卡** | 定位 / 主页转化 / 内容结构 / 钩子 / 分发节奏 / 互动经营 / 数据健康 / 变现就绪度 / 合规风险，共 100 分 |
| **L1 数据健康** | 指标 vs 基准对比、四象限排除法（判定是内容问题还是分发问题） |
| **L2 内容结构** | 内容类型配比、Top 3 爆款解剖、Bottom 3 失败解剖 |
| **L3 人设定位** | 定位公式、5 秒测试、主页逐项体检、信任资产盘点 |
| **L4 平台适配** | 算法契合度、限流自查、变现资格逐项差距表 |
| **方向性建议** | 2–3 个可选战略方向，各自说明适合谁 / 代价 / 预期效果，并明确推荐一个 |
| **内容体系** | 3–5 个内容支柱 + 15 条以上具体选题 + 定制钩子库 + 格式模板 |
| **30/60/90 天计划** | 按周拆解到每日清单 |
| **指标看板** | 只看 5 个指标，附目标值与频率 |
| **风险红线** | 针对该账号的具体禁忌 |

见 [`examples/sample-report-zh.md`](examples/sample-report-zh.md) 查看完整样例。

---

## 诊断框架

核心是**五层诊断模型**，必须按顺序做：

```
L1 数据健康   → 数字层面发生了什么（指标、基准、漏斗、四象限）
L2 内容结构   → 哪些内容有效、哪些在浪费产能
L3 人设定位   → 陌生人凭什么记住你、关注你
L4 平台适配   → 算法规则、限流风险、变现资格
L5 结论策略   → 交叉验证 + 优先级排序 + 行动
```

**最关键的一步是 L1 的四象限排除法**，它决定后面所有结论的方向：

| 曝光 | 互动率 | 诊断 | 处方方向 |
|---|---|---|---|
| 低 | 正常/高 | **分发问题** | 账号权重、发布时段、关键词、社群 |
| 正常/高 | 低 | **内容问题** | 钩子、受众错配、格式、表达 |
| 正常/高 | 正常/高 | **转化问题** | 简介、置顶帖、头像、CTA |
| 全低，持续数周 | | **先查限流** | 走安全标签自查流程 |

---

## 使用方式

### 对话式使用（主要方式）

安装后直接对 agent 说：

```
帮我诊断一下我的 X 账号
```

或更具体：

```
我的 X 账号是 @yourhandle，最近半年涨粉停滞，帮我做个完整诊断
帮我看看我的账号为什么互动越来越差
我想知道我现在够不够格开通 X 变现
帮我重新定位一下我的 X 账号，现在感觉内容太杂了
```

Agent 会先问你拿数据（见下一节），然后跑诊断流程，最后产出报告。

### 数据准备（三档，按你能拿到的选）

**A 档 — 最低可跑（约 3 分钟）**

只要这几项就能出诊断：
- 账号 handle、粉丝数、关注数、账号创建时间
- 最近 10–20 条帖子的**原文** + 各自的点赞 / 回复 / 转推 / 浏览量
- 一句话：你想靠这个号得到什么（涨粉 / 变现 / 接单 / 引流 / 影响力）

**B 档 — 推荐（约 10 分钟，诊断质量显著提升）**

在 A 档基础上加：
- X Analytics 后台截图或导出（近 28 天）：曝光、互动率、主页访问、新增关注、Top posts
- 头像 / 横幅 / 简介 / 置顶帖的完整信息
- 3–5 个同领域对标账号

**C 档 — 深度（可选）**
- X API v2 token，或公开数据抓取
- 竞品账号横向对标

> 数据越少，报告里的措辞会越保守，并明确标注哪些结论置信度低、补什么数据能提高精度。

---

## 脚本详解

两个脚本负责**所有数值计算**（避免模型心算出错），技能会调用它们，你也可以单独使用。

### `scripts/x_audit.py` — 数据体检器

读取账号与帖子数据，输出互动率、基准对比、四象限判定、预警清单、L1 评分草稿。

**最快的方式：看内置样例**

```bash
python3 scripts/x_audit.py --demo
```

**用你自己的数据（JSON）**

```bash
python3 scripts/x_audit.py --json my-data.json
```

JSON 结构（可直接复制 [`assets/sample-input.json`](assets/sample-input.json) 修改）：

```json
{
  "account": {
    "handle": "@you",
    "followers": 1240,
    "following": 610,
    "created": "2024-06-01",
    "premium": true
  },
  "window_days": 28,
  "profile_visits": 386,
  "new_follows": 52,
  "posts": [
    {
      "text": "帖子原文",
      "date": "2026-09-01T09:00",
      "impressions": 5200,
      "likes": 96,
      "replies": 41,
      "retweets": 18,
      "bookmarks": 12,
      "profile_clicks": 3,
      "follows": 1,
      "type": "opinion"
    }
  ]
}
```

**用 CSV（更省事）**

```bash
python3 scripts/x_audit.py --csv posts.csv --followers 1240 --following 610
```

CSV 表头（大小写不敏感）：

```
text,date,impressions,likes,replies,retweets,bookmarks,profile_clicks,follows,type
```

`type` 建议取值：`opinion` / `list` / `thread` / `story` / `link` / `retweet` / `daily`。

**输出 JSON 供二次处理**

```bash
python3 scripts/x_audit.py --json my-data.json --format json --out audit.json
```

**它会输出什么**

```
## 一、核心指标
| 互动率（曝光口径）   | 4.76%  | 主判据 |
| 回复/点赞比         | 0.324  | 算法：回复 +13.5 vs 点赞 +0.5 |
| 主页访问/曝光        | 1.13%  | 在参考区间内 |

## 三、四象限排除法
- 分发判断：分发正常（单帖曝光 ≥ 粉丝数的 50%）
- **结论：分发与内容均正常**
- **处方方向：转向转化层：检查简介、置顶帖、头像、CTA**

## 四、预警清单
**[高] 外链帖占比 33%**
- 依据：免费账号的外链帖子自 2025-03 起近乎零分发，会拖累整体曝光
- 动作：立即停止在帖子里放外链；链接改放评论区首条或简介
```

### `scripts/monetization_check.py` — 变现资格自检

逐项核对 2026 年 X 的变现门槛，**区分硬门槛**（内容解决不了，如地区/收款）**与软门槛**（可以涨，如粉丝/曝光）。

```bash
# 看样例
python3 scripts/monetization_check.py --demo

# 用你的实际情况
python3 scripts/monetization_check.py \
  --country US --premium yes \
  --verified-followers 320 --followers 8000 \
  --impressions-90d 1200000 --age-months 14 --age 25 \
  --email-verified yes --twofa yes --avatar yes --banner no --bio yes \
  --good-standing yes --original-content yes --active-30d yes
```

也可以走 JSON：

```bash
python3 scripts/monetization_check.py --json profile.json
```

**输出包含**：逐项通过/未达标表、硬软门槛标注、结论（当前可申请哪条路径）、时间预期、受众地理对收益的影响。

> ⚠️ 重要提醒：**Creator Revenue Sharing 已于 2026-09-07 退役**，曝光计酬由 **Original Content Rewards** 接替。网上大量中文教程仍在讲旧规则。脚本已按新规实现，但最终请以 `x.com/settings/monetization` 显示的实时条件为准。

两个脚本都支持 `--help`。

---

## 知识底座与准确性说明

这个技能的知识不是模型凭印象写的，而是基于可查证的来源。**但请务必了解每一项的时效性和口径限制**：

### X 推荐算法

来源：X 官方开源的 [`twitter/the-algorithm`](https://github.com/twitter/the-algorithm)（最新提交 2025-09-03）。

**关键限制**：2025 版代码中模型权重改为**线上动态下发**（代码默认值为 0）。技能中引用的权重数值来自 X **最后一次公开的权重表（2023-04）**，量级关系仍被官方 README 引用，但应视为**量级参考而非精确值**。

技能中保留的可查证规则包括：互动权重排序（回复 +13.5 vs 点赞 +0.5）、负反馈惩罚（"不感兴趣" −74、举报 −369）、乘法系数（关注外 ×0.75、同作者衰减）、七个时间常数（30 分钟 / 24–48 小时 / 7 天 / 100 天 / 140 天）、TweepCred 信誉机制、限流标签清单。

### 互动率基准

**⚠️ 口径警告**：公开的 X 互动率基准极其混乱——同一份报告里既有"全行业中位数 0.015%"（粉丝口径）又有"Nano 层均值 5%–8%"，相差数百倍。

技能的处理方式：
- 脚本**主判据为曝光口径**（总互动 ÷ 曝光），平台均值约 1.5%
- 粉丝口径仅用于**同量级账号之间的相对比较**，并明确标注口径存疑
- 粉丝口径必须用**单帖平均互动 ÷ 粉丝数**，不能用 N 条帖子的互动总和除以粉丝数（会虚高约 N 倍）

### 变现规则

基于 2026 年 8–9 月的公开信息整理。**X 的变现规则变动频繁**，脚本中的门槛可能过时，使用前请核对官方页面。

### 一句话总结

> 这个技能在**方法论和诊断逻辑**上是可靠的；在**具体数字**上请把它当作方向性参考，涉及真金白银的决策（变现、投放）请核对官方来源。

---

## 适用范围与限制

**适用**
- 个人 X 账号的自我诊断、复盘、定位调整
- 涨粉停滞 / 互动下滑 / 掉粉的原因排查
- 变现资格评估与准备
- 内容体系搭建

**不适用**
- 品牌号 / 企业号代运营
- 非 X 平台（本技能的知识库是 X 专属的）
- 单纯的帖子撰写（这是另一个环节，技能会提示衔接）

**已知限制**
- 不直接访问 X API —— 需要你提供数据（截图 / 导出 / 手填）
- 数据档位越低，结论越偏方向性而非精确性
- 变现门槛数字有时效性

---

## 目录结构

```
x-selfmedia-audit/
├── SKILL.md                          # 技能入口：工作流、原则、交付规范
├── README.md                         # 本文件
├── install.sh                        # 一键安装脚本
├── LICENSE
├── references/                       # 知识底座（按需加载）
│   ├── algorithm-rules.md            # 算法权重、时间常数、限流标签、四类账号打法
│   ├── benchmarks.md                 # 互动率基准（含口径警告）、漏斗、发布时段
│   ├── monetization.md               # 2026 变现资格与收益系数
│   ├── diagnosis-framework.md        # 五层方法论、提问清单、四象限、9 维评分卡
│   └── content-playbook.md           # 定位公式、内容支柱、钩子库、格式模板、计划范式
├── scripts/
│   ├── x_audit.py                    # 数据体检器
│   └── monetization_check.py         # 变现资格自检
├── assets/
│   ├── audit-report-template.md      # 报告结构模板
│   └── sample-input.json             # 输入数据模板
├── tests/
│   └── test_regressions.py           # 回归测试（22 项，标准库，无需 pytest）
└── examples/
    └── sample-report-zh.md           # 完整样例诊断报告
```

---

## English TL;DR

**X Self-Media Audit** is an agent skill that audits a personal X (Twitter) account end-to-end — account metrics, content performance, personal-brand positioning, and platform/algorithm fit — then delivers strategic direction, a content system, and a concrete 30/60/90-day action playbook.

Unlike a metrics dashboard, it **translates metrics into decisions**. A failed audit says "your engagement rate is 0.8%". A good audit says "your engagement rate is fine, but 62% of your impressions come from the wrong audience — that's why you're not growing."

**Install:**

```bash
curl -fsSL https://raw.githubusercontent.com/marslwc/x-selfmedia-audit/main/install.sh | bash
```

**What it does**

- **Input**: your handle + recent posts with metrics (or X Analytics screenshots/exports)
- **Output**: a diagnostic report with scorecard, root-cause analysis, 2–3 strategic options, content pillars, 15+ topic ideas, and a week-by-week plan
- **Built on**: X's open-source recommendation algorithm (`twitter/the-algorithm`), 2026 monetization rules, and published engagement benchmarks
- **Includes**: two Python scripts for deterministic metric computation and monetization eligibility checks (stdlib only, no `pip install`, no API key required)

**Quick try (no data needed):**

```bash
git clone --depth 1 https://github.com/marslwc/x-selfmedia-audit.git /tmp/xsa && \
python3 /tmp/xsa/scripts/x_audit.py --demo
```

> Note: the skill's knowledge base and report output are primarily in Chinese. The methodology, scripts, and data structures are language-agnostic.

---

## Contributing

欢迎提 Issue 和 PR，尤其是这几类：

- **规则更新**：X 算法或变现规则变了 —— 附上官方来源链接
- **基准数据**：更好的互动率基准（请注明口径和样本量）
- **误诊案例**：技能给出错误结论的实际案例，这类最有价值

修改 `references/` 下的规则文件时，请**在文件内注明数据来源和时效日期**，保持可查证性。

---

## License

[MIT](LICENSE)

---

## 免责声明

本项目提供的算法规则、基准数据与变现门槛均来自公开来源，**可能存在时效性偏差**。涉及商业决策（尤其是变现、投放）请以 X 官方页面为准。本项目不保证任何运营效果。
