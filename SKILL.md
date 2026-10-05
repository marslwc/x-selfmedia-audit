---
name: x-selfmedia-audit
description: "End-to-end self-audit of a personal X (Twitter) account. Diagnoses account metrics, content performance, personal-brand positioning, and platform/algorithm fit, then delivers strategic direction, a content system, and a concrete 30/60/90-day action playbook. This skill should be used when a creator wants a health check on their own X account, asks why growth stalled or engagement dropped, wants to know whether they qualify for X monetization, wants a positioning/niche review, or wants an actionable X content plan. Triggers include X 账号诊断, 账号体检, 复盘, 涨粉方案, 定位分析, 内容策略, 变现资格, 限流自查. Not for managing a brand/official account, not for other platforms, and not for pure post-writing (use us-social-voice or humanizer-zh instead)."
agent_created: true
version: 1.0.0
display_name: "X 自媒体账号诊断"
display_name_en: "X Self-Media Account Audit"
---

# X 自媒体账号诊断

对**个人 X 账号**做一次完整的自我体检，输出三样东西：**诊断结论**（问题在哪）、**方向性建议**（该往哪走）、**实操指南**（明天开始做什么）。

这个技能的价值不在于罗列指标，而在于**把指标翻译成决策**。一个只报告"你的互动率是 0.8%"的审计是失败的；成功的审计会说"你的互动率不算差，但 62% 的曝光来自非目标人群，这就是你涨粉慢的真正原因"。

## 何时使用

- 用户想做自己 X 账号的体检 / 诊断 / 复盘
- 用户问"为什么我涨粉慢 / 掉粉 / 互动变差 / 是不是被限流了"
- 用户想确认自己够不够格开通 X 变现
- 用户想重新定位、换赛道、或搭一套内容体系
- 用户拿到一份后台数据但不知道怎么看

**不适用**：代运营别人的品牌号、非 X 平台、单纯写帖（那种情况直接走 `us-social-voice` / `humanizer-zh`）。

## 核心原则

1. **没有数据不做诊断，只有数据不做安慰。** 缺数据就先要数据；数据到手就直说问题，不用"整体还不错"开头。
2. **一切结论必须落到一个可执行动作。** 每条诊断后面跟一句"所以你要做什么"。
3. **区分"内容问题"和"分发问题"。** 这是最容易误诊的地方。判断方法见 `references/diagnosis-framework.md` 的排除法。
4. **不编造数字。** 用户没给的数据就标"缺失"，不要用行业均值假装是他的数据。
5. **结论带置信度。** 数据越少，措辞越保守，并明确告诉用户补什么数据能提高准确度。

## 工作流

### 第 0 步：数据采集

先判断用户已经给了什么。**不要一次性问 20 个问题**，按下面三档递进，能跑就跑。

**A 档 — 最低可跑（用户什么都没给时，只要这几项）**
- 账号 handle、当前粉丝数、关注数、账号创建时间
- 最近 10–20 条帖子的**原文** + 各自的点赞 / 回复 / 转推 / 浏览量
- 一句话：**你想靠这个号得到什么**（涨粉 / 变现 / 接单 / 引流到产品 / 建立行业影响力）
- 简介原文 + 置顶帖内容

**B 档 — 推荐（诊断质量显著提升）**
- X Analytics 后台截图或导出（近 28 天）：曝光量、互动率、主页访问数、新增关注、Top posts
- 近 30–90 天的发帖频次与时段
- 头像 / 横幅 / 简介 / 置顶帖的完整信息
- 3–5 个同领域对标账号

**C 档 — 深度（可选）**
- X API v2 访问权限（用户自己的 token），或公开数据抓取（可调用 `agent-browser` 技能）
- 竞品账号的公开数据做横向对标
- 私信/评论区的真实用户反馈

采集时**明确告诉用户当前处于哪一档、结论置信度如何**。只有 A 档数据时，开头必须写一句："本次为轻量诊断，结论基于 N 条帖子的样本，方向性可靠、精确度有限。"

数据落到本地后，用 `scripts/x_audit.py` 做机械计算（互动率、基准对比、异常帖识别），**不要心算**。

### 第 1 步：五层诊断

按顺序做，每层都要产出结论。详细方法论、提问清单和排除法见 `references/diagnosis-framework.md`。

| 层 | 看什么 | 关键问题 |
|---|---|---|
| **L1 数据健康** | 曝光、互动率、粉丝增长、转化漏斗 | 数据是好是坏？和同量级比在哪一档？漏斗哪一环断了？ |
| **L2 内容结构** | 内容类型分布、爆款解剖、钩子、格式、节奏 | 什么内容有效？什么在浪费产能？爆款是偶然还是可复制？ |
| **L3 人设定位** | 定位清晰度、观点、差异化、信任资产 | 陌生人 5 秒内能不能说出你是干什么的？凭什么关注你而不是别人？ |
| **L4 平台适配** | 算法契合度、限流风险、变现资格 | 你的打法符合算法奖励的方向吗？有没有踩红线？够不够变现门槛？ |
| **L5 结论与策略** | 交叉验证、优先级排序 | 最致命的 1–2 个问题是什么？先修哪个？ |

**L1 和 L4 的规则细节**：算法权重、时间常数、限流标签见 `references/algorithm-rules.md`；互动率与格式基准见 `references/benchmarks.md`；变现资格见 `references/monetization.md`。

**L1 必做的排除法**（决定后面所有结论的方向）：
- 曝光低 + 互动率正常 → **分发问题**（账号权重、内容不被推荐、时段错）
- 曝光正常 + 互动率低 → **内容问题**（钩子、受众错配、格式）
- 曝光正常 + 互动率正常 + 粉丝不涨 → **主页转化问题**（简介、置顶、头像）
- 全都很低且持续数周 → 先查**限流/安全标签**，再查内容

### 第 2 步：评分卡

按 9 个维度打分，输出总分。评分标准和档位定义见 `references/diagnosis-framework.md`。

维度（权重）：定位清晰度 15 · 主页转化力 10 · 内容结构 15 · 钩子与表达 12 · 分发节奏 10 · 互动经营 12 · 数据健康 12 · 变现就绪度 8 · 合规风险 6。

评分必须**引用具体证据**，不能凭感觉。例如不能写"定位 7 分"，要写"定位 7 分——简介写清了'帮 SaaS 做增长'，但近 20 条里 6 条是生活内容，稀释了信号"。

### 第 3 步：产出交付物

**默认交付一份 Markdown 诊断报告**，用 `assets/audit-report-template.md` 的结构，写入工作区文件。报告必须包含：

1. **一句话结论**（最重要的 1 个问题 + 最该做的 1 件事）
2. **评分卡与雷达概览**
3. **L1–L4 四层诊断**，每层：现状数据 → 对比基准 → 问题 → 归因
4. **方向性建议**：给出 2–3 个可选战略方向，各自说明「适合谁 / 代价是什么 / 预期效果」，并推荐一个
5. **内容体系**：3–5 个内容支柱 + 选题库（≥15 条具体选题）+ 钩子库 + 格式模板，方法见 `references/content-playbook.md`
6. **30/60/90 天实操计划**：按周拆到具体动作和每日清单
7. **指标看板**：只看 5 个指标，附目标值和检查频率
8. **风险与红线清单**：结合账号实际情况列出具体禁忌

用户如果明确要 PPT / 网页版，再转成对应格式（走 `tencent-pptx` 或直接生成 HTML）。

### 第 4 步：后续衔接

诊断完通常会接着做内容。主动提示可用的下一步：
- 写帖 / 改帖 → `us-social-voice`（英文口语化）、`humanizer-zh`（中文去 AI 味）
- 拆解竞品爆款 thread → `xurl`
- 长文发布到 X Articles → `html-to-x-article`

## 工具

- `scripts/x_audit.py` — 输入帖子数据（JSON/CSV），输出互动率、基准对比、预警清单、L1 评分草稿。**所有数值计算走这个脚本。**
  - 快速验证：`python3 scripts/x_audit.py --demo`
- `scripts/monetization_check.py` — 输入账号现状，输出 X 变现资格逐项自检结果。
  - 快速验证：`python3 scripts/monetization_check.py --demo`
- `assets/sample-input.json` — 输入数据模板，可直接改字段后喂给 `x_audit.py`。
- `assets/audit-report-template.md` — 最终报告的结构模板。

两个脚本都支持 `--help`。脚本输出是诊断的**输入**，不是最终报告——最终报告需要结合 L2/L3 的定性判断。

## 语气

像一位做过增长的老朋友，不像咨询公司。直接、具体、给判断。可以说"这条内容我建议直接砍掉"，不要写"该内容类型或存在优化空间"。

但**不要为了显得犀利而否定用户**。数据说好就是好，说差就是差，判断标准是基准数字，不是态度。

## 参考文件索引

| 文件 | 内容 |
|---|---|
| `references/algorithm-rules.md` | X 推荐算法权重表、乘法系数、七个时间常数、限流标签与自查 |
| `references/benchmarks.md` | 互动率基准（按粉丝量级/行业/格式）、漏斗基准、发布时段 |
| `references/monetization.md` | 2026 变现资格（Original Content Rewards / 订阅）、收益系数、地区差异 |
| `references/diagnosis-framework.md` | 五层诊断方法论、提问清单、排除法、9 维评分卡标准 |
| `references/content-playbook.md` | 定位公式、内容支柱设计、钩子库、格式模板、30/60/90 计划范式 |
