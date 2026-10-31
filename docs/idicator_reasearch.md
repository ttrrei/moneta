"""# Indicator Research Draft 1

**状态：** Draft 1 — 待按阶段实施  
**日期：** 2026-10-31  
**实施进度：** P1 及后续 50 个想法的首版实现、测试与开发集验证已完成。
详见 [50 个想法实测报告](indicator_catalogue_results_20261031.md)；43 个未达到晋级标准，
7 个需要修订，尚无想法通过完整复现门槛。本文件保留原始 Draft 设计。
**范围：** Indicator / Feature Library（仅指标与特征层）  
**目标：** 建立一套可重复、无前视偏差、适合 CFD 市场的指标研究与实测流程。

---

## 1. 本阶段要解决什么问题

当前项目已经有相当数量的基础指标和衍生特征。下一步不应继续无目标地增加 RSI、EMA、MACD 等传统指标的参数变体，而应围绕明确的市场行为假设，补充能表达不同市场状态和价格行为的特征，并先验证这些特征是否包含可利用的信息。

本 Draft 的目标不是直接产出一批可交易策略，而是：

1. 盘点并复用现有 Feature，避免重复造轮子。
2. 定义第一批值得研究的 Feature。
3. 明确计算公式、输入、输出、参数、warm-up 和因果性要求。
4. 为新增 Feature 建立质量测试门槛。
5. 在进入 Strategy Generation 前，先研究 Feature 与未来收益之间的关系。
6. 保留完整实验记录，避免因大量参数试验而误判偶然结果为 Alpha。

**本 Draft 只覆盖指标库和 Feature Research。** 暂不要求重构 Backtest Engine、Strategy API、Portfolio、Position Sizing 或 ML 模块。

## 2. 基本概念：不要混淆四个层次

| 层次 | 定义 | 示例 |
|---|---|---|
| Indicator | 对原始行情进行确定性计算的数学变换 | ATR、Swing High、Wick Ratio |
| Feature | 可供研究或策略使用的指标输出，通常带有明确的经济含义 | ATR Percentile、Failed Breakout Event |
| Alpha Hypothesis | 关于某种市场行为可能带来条件收益的可检验假设 | 低波动压缩后，顺突破方向的收益分布可能改善 |
| Strategy | 将多个 Feature、入场/出场规则、成本和风险约束组合成可交易规则 | 压缩状态 + 突破确认 + ATR Exit |

Exit、Trailing Stop、Time Stop 和仓位管理属于交易规则/风险管理研究，不应为了方便而全部称为 Indicator。

**原则：** 先证明某个 Feature 有稳定、可解释的条件信息，再考虑把它组合成 Strategy。

## 3. 现有基础与复用原则

当前项目已有 5m 和 1h Feature Table，规模分别约为 305 列和 270 列。已有指标/特征类别包括 Trend、Momentum、Volatility、Regime、Candle、Volume 和 Derived；已有实现涉及 ATR、EMA、ADX/DI、ER、CHOP、Donchian、Aroon、PSAR、Supertrend、Squeeze 等。

开发前必须先检查当前分支中的真实列名和公式。上述清单用于定位复用对象，不代表这些列的命名、参数或实现已经完全满足本 Draft。

### 3.1 优先复用，不重复实现

| 研究需要 | 优先检查已有 Feature |
|---|---|
| 波动水平 | ATR、ATR Normalisation |
| 趋势强弱/效率 | ADX、DI、ER、CHOP |
| 区间边界 | Donchian High/Low、既有 Range Feature |
| 趋势方向 | EMA Spread、Aroon、Supertrend、PSAR |
| 波动压缩 | Bollinger Width、Squeeze |
| K 线位置与形态 | CLV、已有 Candle Feature |
| 交易量变化 | OBV、VPT 等已有 Volume Feature |

如果已有 Feature 的公式、时间对齐和质量测试合格，就直接复用。若公式不同，应以不同名称表达不同定义，不要静默修改旧列的语义。

### 3.2 新增 Feature 的必要条件

新增前至少回答：

- 它描述了哪一种现有 Feature 没有充分表达的市场行为？
- 它是否只是已有列的简单重命名或重复计算？
- 它的输出能否被清楚解释？
- 它是否只使用当前时点及之前已经可获得的数据？
- 它是否有明确的验证方法和淘汰条件？

不能回答以上问题的指标，不进入第一批实现。

## 4. 参数规则

### 4.1 CFD 时间窗口参数

时间窗口参数优先采用以下集合：

**`6, 12, 24, 60, 120`**

这项约束只适用于表达时间长度的参数，例如：

- Rolling lookback
- Indicator period
- Pivot / swing 的左右确认窗口
- Event validity / retest window
- 滚动统计窗口

允许研究有明确理由的双窗口组合，例如：

- `6 / 24`
- `12 / 60`
- `24 / 120`

不要求每个指标都穷举全部窗口。应先选少量有逻辑依据的配置，控制实验数量。

### 4.2 非时间窗口参数不受上述集合限制

以下参数不应被错误地限制为 6、12、24、60、120：

- PSAR acceleration / maximum step
- Supertrend multiplier
- ATR multiplier
- Breakout threshold
- Swing price-distance threshold
- Minimum wick ratio
- Confirmation threshold
- 其他无量纲系数或价格距离系数

这些参数应根据算法含义定义合理范围，并采用小而有解释的搜索空间。不要因为“参数必须是 6/12/24/60/120”而扭曲指标公式。

### 4.3 参数探索纪律

- 首轮先固定少量参数配置，不做大规模笛卡尔积。
- 对每一次运行记录 Feature 名称、定义版本、参数、代码版本、数据范围和实验 ID。
- 不允许看到测试结果后再反复扩展参数，且不记录此前尝试。
- 同一组经济假设下的相近参数配置，视为同一研究族，评估多重试验带来的偶然发现风险。

## 5. 第一批研究方向与优先级

<details>
</details>

| 优先级 | 方向 | 要回答的问题 | 首轮建议 |
|---|---|---|---|
| P1 | Market Structure | 价格是否正在形成更高/更低的结构？结构突破是否有后续延续？ | Swing、HH/HL/LH/LL、Structure Break、Breakout Retest |
| P1 | Volatility Regime | 市场处于压缩、正常还是扩张状态？ | ATR Percentile、Volatility Expansion Ratio |
| P1 | Failed Breakout / Rejection | 突破是否迅速失败？影线拒绝是否具有条件信息？ | Wick Rejection、Range Re-entry、Failed Breakout |
| P2 | Multi-Timeframe Context | 高周期状态是否改善低周期信号的条件分布？ | HTF Regime Alignment |
| P2 | Exit / Payoff Research | 哪类退出方式能改善收益分布和尾部风险？ | ATR Trailing、Time Stop、Trend Exhaustion（属于交易规则，不是 Indicator） |
| P3 | Statistical / Session Effects | 不同状态、时段和资产是否呈现可重复的收益差异？ | Autocorrelation、Volatility Clustering、Session Conditional Returns |

第一轮只实现 P1。P2 的 HTF Feature 可在 P1 质量测试稳定后进入下一批；Exit / Payoff 与 P3 不纳入本次指标库实现范围。

---

## 6. 第一批 Feature 规格

以下为研究规格和建议输出名，不要求与项目现有命名强行一致。实现前先做 Feature Inventory，确认无重复列，再决定最终命名。

### 6.1 Market Structure

#### MS-01 — Confirmed Swing High / Low

**目的：** 识别已经确认的局部高点与低点，为结构判断、突破和回测提供因果性的参考价位。

**输入：** OHLC、时间戳、品种及周期。

**定义：**

在确认窗口 `L` 和 `R` 下，时点 `p` 是 Swing High 的条件为：

\[
High_p > \max(High_{p-L},\ldots,High_{p-1})
\]

且

\[
High_p \geq \max(High_{p+1},\ldots,High_{p+R})
\]

Swing Low 反向定义。若遇到相同高点/低点，必须固定 tie-break 规则，并在测试中覆盖。

**关键因果要求：**

- Swing 位于 `p`，但直到 `p + R` 收盘后才算确认。
- Feature 只能从确认时点开始可用，不得回填成在 `p` 时已经知道。
- 输出至少区分 `pivot_time` 与 `confirmed_time`，或以等价方式保留确认延迟。
- 回测和策略读取时只能读取 `confirmed_time <= current_time` 的结构信息。

**建议输出：**

- `swing_high_confirmed`
- `swing_low_confirmed`
- `last_confirmed_swing_high`
- `last_confirmed_swing_low`
- 可选：`bars_since_last_swing_high/low`

**参数：** 首轮优先测试少量左右窗口组合，例如 `L/R = 6/6`、`12/12`。左右窗口是时间窗口参数，遵循 6/12/24/60/120 规则。

**边界：** 不足窗口时输出 Null；不得用未来数据补齐；同一价位重复出现时按固定规则处理。

#### MS-02 — HH / HL / LH / LL Structure State

**目的：** 把连续确认的 Swing 转化为可解释的结构状态。

**定义：**

新确认的 Swing High 与上一个已确认 Swing High 比较：

- Higher High（HH）：新高点高于前一个 Swing High。
- Lower High（LH）：新高点低于前一个 Swing High。

新确认的 Swing Low 与上一个已确认 Swing Low 比较：

- Higher Low（HL）：新低点高于前一个 Swing Low。
- Lower Low（LL）：新低点低于前一个 Swing Low。

**建议输出：**

- `structure_hh`
- `structure_lh`
- `structure_hl`
- `structure_ll`
- `structure_state`（可选；必须有明确状态机定义）

**要求：**

- 只能基于已经确认的 Swing。
- 比较关系在新 Swing 确认时才更新。
- 不能简单用当前 K 线 High/Low 与过去 rolling high/low 比较来冒充 Swing Structure。
- 若加入最小价格差阈值，必须使用独立的无量纲或 ATR-normalised 参数，不能与时间窗口规则混为一谈。

#### MS-03 — Structure Break Strength

**目的：** 衡量价格突破最近已确认结构位的方向和幅度，而不仅仅生成一个布尔信号。

**建议定义：**

向上结构突破：

\[
BreakUp_t = Close_t > LastConfirmedSwingHigh_t
\]

向下结构突破：

\[
BreakDown_t = Close_t < LastConfirmedSwingLow_t
\]

突破强度采用 ATR 归一化距离：

\[
BreakStrengthUp_t =
\frac{Close_t - LastConfirmedSwingHigh_t}{ATR_t}
\]

\[
BreakStrengthDown_t =
\frac{LastConfirmedSwingLow_t - Close_t}{ATR_t}
\]

没有有效结构位或 ATR 无效时输出 Null。

**建议输出：**

- `structure_break_up`
- `structure_break_down`
- `structure_break_strength_up`
- `structure_break_strength_down`

**注意：** 突破使用当前已收盘 K 线确认；不能以当前 K 线尚未收盘的价格生成最终信号。

#### MS-04 — Breakout Retest

**目的：** 研究突破后回踩原结构位并重新获得方向性确认的价格行为。

**事件定义建议：**

1. 已发生 MS-03 定义的有效突破。
2. 在后续 `W` 根 K 线内，价格回到突破位附近。
3. 回踩后收盘重新位于突破方向一侧，视为 Retest Confirmed。

**建议输出：**

- `breakout_retest_up`
- `breakout_retest_down`
- `breakout_retest_distance_atr`
- `bars_since_breakout`

**参数：**

- Retest validity window：首轮 `6` 或 `12`。
- “接近突破位”的距离阈值属于非时间参数，可用 ATR 倍数定义，不受 6/12/24/60/120 限制。

**防止未来信息：**

- 在回踩确认之前，不能提前标记 Retest 成功。
- 事件输出时间为确认时点。
- 记录原始突破时间与突破价位，便于审计延迟和事件归因。

### 6.2 Volatility Regime

#### VR-01 — ATR Percentile

**目的：** 衡量当前波动率相对于近期自身历史处于什么位置，减少不同品种价格尺度差异。

**定义建议：**

先复用已有 ATR，再在过去 `N` 个有效观测中计算当前 ATR 的经验百分位：

\[
ATRPercentile_t =
\frac{\#\{i \in Window_t : ATR_i \leq ATR_t\}}
{Count(Window_t)}
\]

输出范围为 `[0, 1]` 或 `[0, 100]`，整个项目必须统一单位。

**建议参数：** `N = 60`、`120`。底层 ATR period 优先复用项目已有、已验证的配置，不在本 Feature 中顺便扩展 ATR 参数网格。

**建议输出：**

- `atr_percentile_60`
- `atr_percentile_120`

**实现要求：**

- 只使用截至当前已收盘时点的数据。
- 对有效样本数设置最低门槛；不足时输出 Null。
- 百分位算法必须固定，处理相同值的规则必须一致。
- 该 Feature 表示“相对自身历史的波动位置”，不直接代表未来波动方向。

#### VR-02 — Volatility Expansion Ratio

**目的：** 识别当前波动正在扩张还是收缩。

**定义建议：**

\[
VolExpansionRatio_t =
\frac{ATR_{fast,t}}{ATR_{slow,t}}
\]

建议先测试少量组合：

- `ATR(6) / ATR(24)`
- `ATR(12) / ATR(60)`
- `ATR(24) / ATR(120)`

如果项目已有相同 ATR 列，直接引用。若已有 ATR period 与本组合不一致，应明确新增计算的理由。

**建议输出：**

- `vol_expansion_ratio_6_24`
- `vol_expansion_ratio_12_60`
- `vol_expansion_ratio_24_120`

**解释：**

- 比值大于 1：短期波动高于较长周期基准。
- 比值小于 1：短期波动低于较长周期基准。

不应把某个固定比值直接宣称为通用买卖阈值；阈值需要在 Feature Analysis 中验证其跨品种稳定性。

### 6.3 Failed Breakout / Rejection

#### FR-01 — Wick Rejection Strength

**目的：** 衡量 K 线收盘前价格从高位或低位回撤的程度，作为价格拒绝行为的代理特征。

**定义：**

\[
Range_t = High_t - Low_t
\]

\[
UpperWick_t = High_t - \max(Open_t, Close_t)
\]

\[
LowerWick_t = \min(Open_t, Close_t) - Low_t
\]

\[
UpperWickRatio_t = \frac{UpperWick_t}{Range_t}
\]

\[
LowerWickRatio_t = \frac{LowerWick_t}{Range_t}
\]

同时建议复用或核对 CLV：

\[
CLV_t = \frac{2Close_t - High_t - Low_t}{High_t - Low_t}
\]

**建议输出：**

- `upper_wick_ratio`
- `lower_wick_ratio`
- `close_location_value`（若已有则复用）
- 可选：按方向组合的 rejection score，但必须明确公式，不要仅凭名称暗示预测能力。

**边界：** `High = Low` 时输出 Null 或按项目统一的安全约定处理，不得出现除零或无穷值。

**解释限制：** Wick Rejection 仅描述 OHLC 价格行为，不等同于真实订单簿流动性或机构行为。

#### FR-02 — Range Re-entry

**目的：** 识别价格短暂越过既定区间边界后，收盘重新回到区间内的事件。

**定义建议：**

以当前 K 线之前已经形成的区间边界为基准：

- 上方越界后回到区间：前序价格曾收于上边界外，当前收盘重新低于当时有效的上边界。
- 下方越界后回到区间：前序价格曾收于下边界外，当前收盘重新高于当时有效的下边界。

区间边界可优先复用 Donchian 或项目已有 Range Feature，但必须确认边界计算不包含当前 K 线，避免把当前 High/Low 反过来改变本次判定基准。

**建议输出：**

- `range_reentry_from_above`
- `range_reentry_from_below`
- `range_reentry_distance_atr`

**参数：** Range lookback 属于时间窗口参数，使用 6/12/24/60/120 的小范围组合。首轮不必全部组合。

#### FR-03 — Failed Breakout Event

**目的：** 将突破与后续回到区间内的行为定义为一个可审计的事件，用于研究失败突破后的条件收益。

**事件定义建议：**

1. 在 `t0` 出现有效的向上或向下突破（参考已冻结的区间/结构边界）。
2. 在后续 `W` 根 K 线内，收盘重新回到原区间内部。
3. 在重新进入区间的那根 K 线收盘后，事件才确认。

**建议输出：**

- `failed_breakout_up`
- `failed_breakout_down`
- `failed_breakout_age_bars`
- `failed_breakout_excursion_atr`
- `failed_breakout_reentry_distance_atr`

**参数：** `W` 首轮测试 6 或 12；价格距离阈值为非时间参数，可采用 ATR 倍数。

**实现要求：**

- 保留突破发生时间、参考边界、重新进入时间。
- 一个突破事件只能按确定的状态机规则被确认一次。
- 超过有效窗口仍未重新进入区间，则事件过期，不应事后回写为失败突破。
- 避免 FR-02 与 FR-03 重复计算：FR-02 是单次重新进入区间的原子事件；FR-03 是“先发生突破、再在窗口内重新进入”的完整事件。

**术语限制：** 这里的 Failed Breakout 是基于价格数据的操作性定义，不代表能够直接观测真实市场流动性或识别机构 Stop Hunt。

### 6.4 P2 — Multi-Timeframe Regime Alignment（暂缓实现）

该方向值得研究，但不进入首轮 P1 实现。

**研究目标：** 判断高周期趋势/波动状态是否能够改善低周期 Feature 的条件收益分布。

建议先复用 1h 的 EMA Spread、ADX/DI、ER、CHOP 等已有列，与 5m 的 Pullback Distance、Candle Structure 或 Momentum Feature 组合研究。

**核心要求：**

- 5m 时点只能使用当时已经完成的 1h K 线。
- 不能将当前尚未收盘的 1h K 线的最终 High、Low、Close 或指标值映射到该小时内部的 5m K 线上。
- 使用 backward as-of 对齐时，必须验证时间戳、时区、bar close 语义和缺失数据处理。
- 明确高周期信号的可用时间，而不是只看数据行的时间标签。

---

## 7. 第一轮实现范围

### 7.1 P1 首批建议清单

| ID | Feature | 优先级 | 备注 |
|---|---|---|---|
| MS-01 | Confirmed Swing High / Low | P1 | 必须显式处理右侧确认延迟 |
| MS-02 | HH / HL / LH / LL | P1 | 仅基于已确认 Swing |
| MS-03 | Structure Break Strength | P1 | ATR-normalised |
| MS-04 | Breakout Retest | P1 | 事件只能在确认后输出 |
| VR-01 | ATR Percentile | P1 | 复用已有 ATR |
| VR-02 | Volatility Expansion Ratio | P1 | 复用已有 ATR |
| FR-01 | Wick Rejection Strength | P1 | OHLC 原子特征 |
| FR-02 | Range Re-entry | P1 | 复用既有区间边界 |
| FR-03 | Failed Breakout Event | P1 | 明确事件状态机 |

**不要一次性把所有参数组合展开。** 第一轮只用少量有解释的参数配置，先确认逻辑、质量与特征分布正确。

### 7.2 本轮不做的事

- 不新增一套重复的 RSI / MACD / EMA / CCI 指标族。
- 不为所有 Feature 自动生成大量 Strategy。
- 不把 Exit、Trailing Stop、Time Stop 混入 Indicator Library。
- 不在本阶段重构 Backtest Engine 或数据存储架构。
- 不因为一个 Feature 在单一品种或单一时期表现好，就直接将其认定为 Alpha。
- 不为追求更多列而增加没有明确假设的 Feature。

---

## 8. Feature Library 工程要求

### 8.1 统一实现约定

新增 Feature 应遵循项目现有模块组织和接口风格，不为本 Draft 另建一套互不兼容的计算框架。

每个 Feature 至少要有：

- 唯一、稳定的列名。
- 明确的公式和参数。
- 明确的输入列、输出类型和单位。
- 明确的 warm-up 长度与 Null 语义。
- 明确的时间戳与 bar-close 语义。
- 确定性计算：相同输入和参数必须产生相同结果。
- 可单独测试的实现。
- 文档或 Feature Registry 记录。

### 8.2 数值与缺失值

- 不允许输出未处理的 `NaN`、`+Inf`、`-Inf`，除非项目数据契约明确允许且下游能安全处理。
- Rolling warm-up 不足时优先输出 Null，不要用 0 假装指标已经有效。
- 分母为 0、价格区间为 0、ATR 不可用时必须有显式处理。
- 对 `[0,1]`、`[-1,1]` 等理论范围进行断言或边界测试。
- 归一化 Feature 必须说明所用尺度，例如 ATR、价格或百分位。

### 8.3 输出语义

- 布尔事件列只表示事件是否在当前时点确认，不表示未来结果。
- 连续值列应说明正负方向、单位和解释。
- 若 Feature 需要记录事件起点、确认时间和参考价位，应使用足够的辅助字段，不要只留下一个无法审计的布尔值。
- 不要用同一列名承载不同公式或不同参数定义。

---

## 9. Quality Gates：新增 Feature 的必过测试

下列测试是新增指标进入研究分析前的最低要求。

### Gate 1 — Formula / Boundary Correctness

- 使用小型手工 OHLC 样本，验证公式结果。
- 覆盖平盘、连续相同高低点、跳空、大幅波动、零区间、零分母。
- 测试输入排序、重复时间戳和缺失值的处理方式。
- 对输出范围、单位和方向做断言。

### Gate 2 — Warm-up / Start-point Independence

目标是确保 Feature 不会因为数据加载起点改变而产生不合理差异。

- 用完整数据计算一次。
- 再从更晚的起点截取相同的目标区间重新计算。
- 在共同有效区间比较结果。
- 对滚动计算的预期 warm-up 影响给出明确容差或解释。
- 不允许静默使用截取数据起点以前不存在的状态。

### Gate 3 — Causality / No Look-ahead

这是 Market Structure 和事件型 Feature 的关键门槛。

- **Prefix invariance：** 对任意时点 `t`，只给计算器输入截至 `t` 的数据，所得 `t` 时点 Feature 必须与全量数据计算后在 `t` 时点的结果一致。
- **Future perturbation：** 任意修改 `t` 之后的数据，不得改变 `t` 或之前已经可用的 Feature。
- Swing 必须在右侧确认窗口结束后才可用。
- Retest / Failed Breakout 必须在事件确认时点才可输出。
- MTF Feature 必须只使用已完成的高周期 bar。

### Gate 4 — Data Alignment / Multi-Asset Isolation

- 每个品种独立计算，不得让一个品种的数据状态串入另一个品种。
- 按时间排序、分组边界和重启计算均要有测试。
- 5m 与 1h 数据必须按明确的时区和 bar close 语义对齐。
- 缺失 K 线不能被默认为连续有效的 bar；事件窗口按有效 bar 还是日历时间计算，必须明确。

### Gate 5 — Implementation Parity

若同一 Feature 存在两个实现、两种计算路径或不同运行环境，应建立 parity test。

- 对同一输入和参数比较结果。
- 对连续值设置基于算法与精度的容差。
- 对事件列要求完全一致。
- 当前项目的双库 parity 覆盖仍需逐步补足；本 Draft 不假设所有现有列都已经有完整 parity。

### Gate 6 — Determinism / Regression

- 固定样本重复运行结果一致。
- 新增 Feature 不得意外改变旧 Feature 的数值与语义。
- 保存少量稳定 fixture，后续修改必须通过回归测试。
- 任何有意修改旧公式的行为都应有版本或变更说明。

**质量门槛原则：** 未通过相关 Gate 的 Feature 可以留在开发分支，但不能进入正式 Feature Analysis，更不能用于 Strategy Generation。

---

## 10. Feature 实测方案：先测信息，再生成策略

首轮实验应验证“Feature 是否包含信息”，而不是立即寻找能让回测收益最高的参数。

### 10.1 基础实测问题

每个连续型 Feature 至少回答：

1. 不同 Feature 分位区间的未来收益分布是否有差异？
2. 收益差异是否有稳定方向，还是仅有少量极端样本贡献？
3. Long 与 Short 是否具有明显不对称性？
4. 关系是否跨品种、跨市场类别和不同时段重复出现？
5. 在成本假设下，观察到的差异是否仍有实际意义？
6. 结果是否依赖某一个参数、品种或时间段？

对事件型 Feature，重点看事件发生后的条件收益、最大有利/不利波动（MFE/MAE）、事件频率和有效样本数量。

### 10.2 Forward Return Horizon

首轮使用以下未来 bar 窗口作为统一分析尺度：

**`6, 12, 24, 60, 120` bars**

对时点 `t`，可先计算：

\[
ForwardReturn_{t,h} = \frac{Mid_{t+h}}{Mid_t} - 1
\]

如果项目已有统一收益定义，应复用项目定义。需要明确该计算是 mid-price 研究收益，不等于真实可执行收益。

- 5m 数据的 horizon 以 5m bar 数量表示。
- 1h 数据的 horizon 以 1h bar 数量表示。
- 不得把不同 timeframe 的相同 bar 数误称为相同钟表时间。
- 对事件型 Feature，起点使用事件确认时点，不能回溯到尚未确认的发生时点来制造提前可知的收益。

### 10.3 分析方法

建议按以下顺序执行：

1. **Distribution：** Feature 的分布、Null 比例、极值、跨品种差异。
2. **Conditional Returns：** 按预先固定的分位组或事件状态比较未来收益。
3. **Long / Short Asymmetry：** 分方向研究，不以多空合并均值掩盖差异。
4. **MFE / MAE：** 评估事件之后的有利与不利价格路径。
5. **Cross-Asset：** 分品种、分资产类别查看结果，不只报告汇总值。
6. **Stability：** 用多个非重叠 In-Sample 时间切片或 Walk-forward 检查稳定性。
7. **Cost Sensitivity：** 在统一研究成本情景下复核，并尽可能使用品种实际 bid/ask、commission、financing 等成本数据。

结果至少同时报告样本数、均值、中位数、分位数、胜率或正收益比例、波动和置信区间。仅报告平均收益或 Sharpe 不足以判断 Feature 是否值得保留。

### 10.4 成本处理

可先保留 `0 / 2 / 5 bps` 作为一致的敏感性对照情景，但它们不能替代 CFD 实际交易成本。

正式成本归因应尽可能使用：

- Bid / Ask spread；
- Commission；
- Financing / swap（持仓跨日时）；
- 其他与品种和交易时段相关的费用或执行假设。

Mid-price forward return 用于初步研究条件关系；只有在可执行价格和成本下仍有意义，才值得推进为交易策略假设。

### 10.5 时间切分与 OOS 纪律

- Feature 开发与参数研究只使用允许的 In-Sample 数据。
- 在 In-Sample 内预先定义非重叠时间切片或 Walk-forward。
- 不要把 `Full` 与 `Last 12m` 当成两份独立验证数据；若区间重叠，就不能视为独立证据。
- Holdout / OOS 不用于反复调参、挑选阈值或决定继续尝试哪个 Feature。
- OOS 应维持现有一次性消费和 provenance 机制。只有研究假设、Feature 定义、参数及实验方案冻结后，才考虑按项目既定流程使用 OOS。
- 每次实验保留所有尝试，包括失败结果，不能只保存表现最好的配置。

### 10.6 多重试验与过拟合控制

首轮优先少量、有理论依据的 Feature 和参数组合。报告中应：

- 记录总试验数及参数组合数；
- 标记同一研究假设下的相关试验；
- 使用时间切片稳定性、跨品种重复性和置信区间判断证据强弱；
- 对大量并行假设的统计检验，考虑使用适当的多重比较控制；
- 不因单一最佳分组或最佳品种的结果直接宣布成功。

---

## 11. 建议的实施顺序

### Phase 0 — Feature Inventory

1. 导出现有 5m / 1h Feature 名称、参数和公式来源。
2. 将每个候选 Feature 标记为：已有且可复用、已有但需修正、缺失、暂不需要。
3. 先确认 Donchian、ATR、CLV、CHOP、ER、ADX/DI 等可复用列的准确语义。
4. 明确需要新增的列名，避免重复列。

**完成标准：** 有一份明确的 Feature Inventory，第一批每个候选 Feature 都有新增理由。

### Phase 1 — P1 Feature Implementation

建议按依赖顺序实现：

1. Wick Rejection Strength（原子 OHLC 特征，依赖少）。
2. ATR Percentile 与 Volatility Expansion Ratio（复用 ATR）。
3. Confirmed Swing High / Low。
4. HH / HL / LH / LL。
5. Structure Break Strength。
6. Range Re-entry。
7. Failed Breakout Event。
8. Breakout Retest。

不要求一次提交全部完成。每一组实现后立即通过对应质量测试。

**完成标准：** 每个 Feature 有定义、代码、测试、文档、稳定列名和质量 Gate 结果。

### Phase 2 — Feature Analysis

1. 固定首轮 Feature 与参数配置。
2. 运行分布和 forward-return 分析。
3. 对事件型 Feature 做 event study、MFE / MAE。
4. 比较 Long / Short、品种、资产类别和非重叠时间切片。
5. 形成保留、修改或淘汰结论。

**完成标准：** 每个 Feature 都有实验记录和明确结论；没有证据的 Feature 可以被淘汰。

### Phase 3 — Hypothesis Promotion

只有通过 Feature Analysis 的少数 Feature 才进入下一步：

- 写出明确 Alpha Hypothesis；
- 固定 Feature 定义和参数；
- 再进入 Strategy Generation；
- 采用现有策略回测、成本归因和验证流程。

本 Draft 不要求现在实施 Phase 3。

---

## 12. Feature 研究记录模板

每个新增 Feature 或研究假设都应保存以下信息：

```yaml
research_id: ""
feature_id: ""
feature_name: ""
definition_version: "1"

hypothesis:
  market_behaviour: ""
  expected_relationship: ""
  expected_direction: "long | short | both | unknown"

implementation:
  module: ""
  input_columns: []
  output_columns: []
  formula_reference: ""
  timeframe: "5m | 1h"
  parameters: {}
  parameter_type_notes: ""
  warmup: ""
  null_and_boundary_rules: ""
  causality_and_confirmation_delay: ""

quality_gates:
  formula_boundary: "pending"
  warmup_start_independence: "pending"
  causality_no_lookahead: "pending"
  data_alignment: "pending"
  implementation_parity: "pending"
  determinism_regression: "pending"

experiment:
  data_universe: []
  in_sample_range: ""
  non_overlapping_splits: []
  forward_horizons: [6, 12, 24, 60, 120]
  cost_scenarios_bps: [0, 2, 5]
  metrics: []
  total_trials: 0

result:
  sample_size: null
  cross_asset_stability: ""
  time_stability: ""
  long_short_asymmetry: ""
  cost_sensitivity: ""
  decision: "keep | revise | reject | pending"
  decision_reason: ""
```

模板中的 `pending` 是待测试状态，不代表已经通过。实验范围、数据区间和 trial 数必须在运行后填写真实值。

---

## 13. 最终验收标准

第一轮 Indicator Research 完成时，应满足：

- [ ] 已盘点现有 Feature，避免无意义重复。
- [ ] P1 候选 Feature 均有明确公式、参数和经济含义。
- [ ] 时间窗口参数与非时间参数已正确区分。
- [ ] Swing、Breakout、Retest、Failed Breakout 等事件不存在未来数据泄漏。
- [ ] warm-up、边界、分组、对齐、确定性测试通过。
- [ ] 对适用的双实现建立 parity 测试。
- [ ] Feature 的分布、forward returns、Long/Short、MFE/MAE 已分析。
- [ ] 结果按品种、资产类别和非重叠时间切片检查过稳定性。
- [ ] 成本敏感性已报告，且没有把 mid-price 结果误称为真实可执行收益。
- [ ] 所有试验均有记录，OOS 未被用于调参。
- [ ] 每个 Feature 都有 Keep / Revise / Reject 的明确结论。

**一个 Feature 通过工程测试，不代表它有 Alpha；一个 Feature 在某个回测中表现好，也不代表它有可重复的 Alpha。** 工程质量和研究证据必须分开验收。

## 14. Draft 1 的明确结论

当前最值得推进的不是继续扩充传统指标，而是优先完成三组彼此有区别的市场行为表达：

1. **Market Structure：** Swing → HH/HL/LH/LL → Structure Break / Retest。
2. **Volatility Regime：** ATR Percentile → Volatility Expansion。
3. **Failed Breakout / Rejection：** Wick Rejection → Range Re-entry → Failed Breakout。

先让这些 Feature 的定义、时间可用性和质量测试正确，再用统一的 forward-return / event-study 流程验证它们是否有信息价值。

**不要为了完成指标数量而实现所有候选项，也不要为了产生策略数量而把每个 Feature 直接做笛卡尔积。** 研究目标是找到少量、可解释、跨时间和跨品种相对稳定、扣除成本后仍值得继续验证的市场行为特征。
