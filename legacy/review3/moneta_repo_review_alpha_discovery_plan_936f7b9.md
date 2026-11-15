# Moneta Repo Review & Alpha Discovery 方向计划

**Review 基准：** `936f7b9`  
**仓库：** https://github.com/ttrrei/moneta  
**范围：** 代码问题、效率、可精简部分、策略分类、Alpha 探索方向与后续路线图。

> 本文是本次 review 的整理稿。CI 状态在本次检查中未能取得可核验的状态，因此不将 CI 描述为通过。

## 1. 执行摘要

Moneta 已逐步从回测脚本集合发展为包含策略注册、批量运行、结果汇总、检查工具和研究文档的策略探索框架。近期值得保留的进展包括：

- `strategy/strategy_diverse_lib.py` 用 `RuleSpec` 和共享执行逻辑统一 S-113 至 S-132 的多样化策略。
- 策略设计文档、运行记录和每策略 summary CSV 逐步完善。
- 开始引入 HTF 特征，并探索结构、突破和成交活动等不同信号来源。
- 报告生成和结果检查正在标准化。

但当前瓶颈不是策略数量不足，而是研究方法仍偏向 **Strategy Enumeration**，尚未充分进入 **Alpha Discovery**。不少策略仍是单指标阈值，或两到三个指标做 AND 组合，再叠加 EMA / ADX 过滤。相关指标可能重复表达同一种市场信息，增加组合数量不等于增加独立 Alpha。

**建议暂停以增加 Strategy ID 为主要进展指标，先建立分类体系、Feature Research 和高效实验底座。**

## 2. 当前策略与代码状态

### 2.1 值得保留的改进

| 领域 | 进展 | 评价 |
|---|---|---|
| 共享策略执行 | `strategy_diverse_lib.py` 统一 S-113 至 S-132 | 方向正确，减少重复执行逻辑 |
| 策略设计文档 | 设计文档先于运行 | 有助于减少事后解释和规则漂移 |
| HTF 特征 | 开始引入高周期上下文 | 是从简单指标组合走向多尺度研究的一步 |
| 结果汇总 | 每个策略独立 summary CSV | 有利于审查交易数、收益、回撤和成本敏感性 |
| 报告与检查 | 统一报告生成、`check_results.py` | 应继续增强完整性和一致性检查 |

不建议推倒重来。应在现有基础上整理接口和流程，而不是大规模重写回测引擎。

### 2.2 核心研究问题：指标组合多，独立 Alpha 来源少

需要区分四个概念：

- **Feature：** 市场数据的描述，例如 ATR percentile、EMA distance / ATR。
- **Signal：** 特征或结构触发的交易判断。
- **Strategy：** 完整的入场、退出、仓位和风险规则。
- **Alpha Hypothesis：** 为什么某种信息在特定条件下可能对未来收益有预测能力。

后续研究重点应从“还能组合什么指标”转向：

> 在什么市场状态下，哪一种市场行为或统计特征，对未来哪个持有期限的收益有稳定的条件预测能力？扣除交易成本后是否仍然成立？

### 2.3 高换手策略需要先筛选

S-113 至 S-132 的部分策略交易数非常高：

| 策略 | 标的 | Full trades（约） | 年化交易数（约） |
|---|---|---:|---:|
| S-114 | EUR_USD | 14,657 | 2,655 |
| S-115 | BTC_USD | 6,997 | 1,268 |
| S-117 | EUR_USD | 17,014 | 3,082 |
| S-127 | EUR_USD | 27,824 | 5,041 |
| S-131 | XAU_USD | 12,502 | 2,266 |

这提示部分策略可能在阈值附近频繁进出，噪声与成本侵蚀风险较高。完整矩阵回测前建议进行轻量预筛选：

- 信号触发次数、每日/每小时交易频率；
- 平均持仓时间、信号最小间隔；
- Long / Short 比例；
- 初步毛收益、单笔收益分布；
- 合理成本下的净收益敏感性。

高换手不是自动淘汰条件，但必须证明扣除 spread、commission、slippage 后仍有价值。

参考结果：[S-114](https://github.com/ttrrei/moneta/blob/936f7b9/strategy/results/S114/summary.csv) · [S-117](https://github.com/ttrrei/moneta/blob/936f7b9/strategy/results/S117/summary.csv) · [S-127](https://github.com/ttrrei/moneta/blob/936f7b9/strategy/results/S127/summary.csv)

### 2.4 Benchmark 需要改进

Buy & Hold 单独作为 Benchmark 不足，尤其 BTC 的长期方向性漂移，以及 Long-Short 策略与 Long-only Buy & Hold 之间的敞口差异。

S-130 的汇总示例：

| 标的 | 策略 Full Return | Buy & Hold Return |
|---|---:|---:|
| BTC_USD | +72.55% | +1,288.41% |
| XAU_USD | +8.04% | +110.29% |
| EUR_USD | -9.83% | +3.07% |

建议增加：
1. Cash / Flat（不交易）；
2. Buy & Hold（保留，但标明 Long-only 性质）；
3. Exposure-matched Benchmark；
4. Volatility-matched Benchmark；
5. Long-only / Short-only 对照；
6. 成本后的净收益比较。

建议统一报告 CAGR、Sharpe、Sortino、Max Drawdown、Calmar、Return / Drawdown、Profit Factor、平均/中位数单笔收益、持仓时间、Turnover、Long / Short 独立结果及成本前后表现。

参考：[S-130 summary](https://github.com/ttrrei/moneta/blob/936f7b9/strategy/results/S130/summary.csv)

## 3. 多维策略分类体系

不要将策略强行放入一个互斥类别。同一策略可能同时属于“市场结构 + 波动率扩张 + 多周期 + 非对称退出”。建议用多轴标签。

### 3.1 Alpha Source（Alpha 来源）

| 分类 | 研究内容 / 示例 |
|---|---|
| A. Traditional Indicators | RSI、EMA、ADX、MACD、Stochastic |
| B. Derived / Generated Features | ATR/Close、ATR percentile、EMA distance / ATR、效率比率、收益加速度 |
| C. Market Structure | Swing High/Low、HH/HL、BOS、CHoCH、Failed Breakout、Liquidity Sweep |
| D. Volatility / Compression / Expansion | ATR percentile、HV percentile、波动率压缩、扩张速度 |
| E. Asymmetric Payoff / Trade Management | 动态止损、Trailing Stop、Partial Exit、Time Stop、利润延伸 |
| F. Volume / Activity / Flow | Tick Volume、量价背离、CMF/MFI 衍生特征 |
| G. Time / Session / Calendar | London / New York session、Session breakout、星期和时段效应 |
| H. Statistical / Quant Alpha | Autocorrelation、Residual Mean Reversion、Rolling Skewness、Conditional Expectancy |
| I. Cross-market / Relative Value | BTC/ETH 相对强弱、黄金与美元关系、指数相对动量 |
| J. Microstructure / Execution | Bid-Ask Spread、Gap、Liquidity、Slippage-aware Entry |

### 3.2 Regime（市场状态）

Trending、Ranging、High Volatility、Low Volatility、Compression、Expansion、Reversal / Exhaustion、Unclassified。

### 3.3 Entry / Exit / Payoff 维度

| 维度 | 标签示例 |
|---|---|
| Entry Type | Breakout、Pullback、Reversal、Reclaim、Continuation、Sweep |
| Direction | Long、Short、Long-Short |
| Exit Type | Indicator、Structure、ATR Stop、Trailing、Time Stop、Signal Reversal |
| Payoff | Symmetric、Asymmetric、Partial Exit、Profit Extension |
| Holding Period | Intraday、Short Swing、Swing |
| Timeframe | Single TF、MTF |
| Risk Model | Fixed Risk、ATR-based、Volatility-targeted |

### 3.4 现有策略编号的初步归类

| 策略区间 | 初步归类 |
|---|---|
| S-01 至 S-27 | 传统指标趋势 / 均值回归 |
| S-28 至 S-42 | K 线、波动率、价格衍生 |
| S-43 至 S-57 | 衍生指标 / 结构组合 |
| S-58 至 S-102 | 长周期指标、趋势、波动率 |
| S-103 至 S-112 | 较慢周期指标、波动率、动量 |
| S-113 至 S-132 | HTF 过滤、结构、突破、成交活动等 |

此区间仅作迁移起点，最终必须逐个检查真实 entry / exit 逻辑并支持多标签。

### 3.5 元数据建议

```yaml
strategy_id: S-133
name: example_strategy

alpha_source:
  - market_structure
  - volatility

regime:
  - compression
  - expansion

entry:
  type: breakout
  direction: long_short

exit:
  type:
    - atr_stop
    - trailing

payoff:
  profile: asymmetric

timeframe:
  signal: M5
  context: H1

research_status: hypothesis
```

元数据负责分类、筛选和追踪；复杂规则留在 Python。不要把复杂逻辑塞进 YAML，也不要让 Registry 和代码分别维护容易漂移的参数副本。

## 4. 实验效率：分层与缓存

### 4.1 当前可能的重复计算

`strategy_variants.py` 对 Variant、Instrument、Window、Cost Tier 分别运行。例如 8 variants × 3 instruments × 2 windows × 3 cost tiers = 144 次运行。相同历史数据、特征和信号可能被重复读取或计算。

### 4.2 建议分层架构

```text
Market Data
   |
   v
Data Layer
  - 按 instrument / timeframe / window 加载
  - 数据质量检查、标准化、缓存
   |
   v
Feature Layer
  - 预计算通用指标和衍生特征
  - 记录 feature version
   |
   v
Signal Layer
  - 按策略参数生成 entry / exit / direction
  - 输出可缓存信号数组
   |
   v
Execution Layer
  - 生成标准 Trade Ledger
   |
   v
Cost Replay
  - 0 bps / 常规成本 / 压力成本
   |
   v
Metrics & Reports
  - 绩效、回撤、换手、稳定性、Benchmark
```

### 4.3 缓存键

缓存键不能只按策略 ID。建议包含：

- 数据 fingerprint；
- Instrument、timeframe、window；
- Feature version；
- Strategy ID 和参数 hash；
- Signal configuration；
- 必要时的 execution model version。

示意：

```text
feature_cache/{data_fingerprint}/{instrument}/{timeframe}/{window}/{feature_version}.parquet

signal_cache/{data_fingerprint}/{strategy_id}/{parameter_hash}/{instrument}_{timeframe}_{window}.parquet
```

### 4.4 Cost Replay 的边界

如果交易成本不会影响信号生成或交易状态，可以生成一次信号和基础 Trade Ledger，再用不同成本模型重放。

但若滑点、成交可用性、仓位或止损触发会影响后续状态，就不能简单在最终收益上扣常数，必须在 Execution Replay 中按成本模型重新模拟。

### 4.5 先 Profiling，再增加并行度

记录 Data Load、Feature Calculation、Signal Generation、Execution、Cost Replay、Metrics、Report Writing 的耗时。先识别瓶颈，再决定进程池、线程池、NumPy 向量化或 Parquet 缓存。单纯增加 worker 未必能解决重复读取和重复计算。

## 5. 代码精简与维护成本

### 5.1 薄 Wrapper 与通用 Runner

`strategy_diverse_lib.py` 已统一 S-113 至 S-132 的主要逻辑，但外围仍有多个薄适配器和 CLI wrapper，主要传递固定 Strategy ID。

长期可以演进为：

```bash
python -m strategy.run_rule --strategy S-113
python -m strategy.run_rule --strategy S-127
```

**不要立即删除旧 wrapper。** 先确认：
- Runner 能从 Registry 找到正确策略；
- 参数和默认值能完整复现；
- Checker 能识别新旧入口；
- 报告和运行记录不依赖旧文件名；
- 老策略仍可重跑；
- 新旧执行结果一致性测试通过。

### 5.2 配置统一

`strategy_variants.py` 中长篇 `STRATEGIES` / `VARIANTS` 映射，可以逐步迁入 Registry / YAML 元数据。适合配置化的是策略 ID、标签、参数默认值和变体列表；复杂信号逻辑仍留在 Python。

应更新过时描述，例如脚本顶部仍提到 “6-iteration improvement harness for S-08 .. S-27” 等旧范围说明。

### 5.3 批次生成脚本

需要盘点以下类型的一次性或批次脚本：

- `_gen_batch8.py`
- `_gen_cli_batch8.py`
- `generate_diverse_batch_wrappers.py`
- `write_diverse_batch_reports.py`

分类为长期工具、迁移工具或可归档脚本。不是为了减少文件数量而删除，而是减少重复入口、重复配置和无法验证的生成流程。

### 5.4 目标结构（渐进式，不要求一次重构）

```text
strategy/
  registry / metadata
  rules/
    traditional/
    derived_features/
    market_structure/
    volatility/
    asymmetric_payoff/
    statistical/
  engine/
    data
    features
    signals
    execution
    metrics
  research/
    feature_analysis
    experiment_sweeps
    validation
  reports/
  docs/
```

## 6. 从 Strategy Enumeration 转向 Feature Research

### 6.1 建议的新流程

```text
提出 Alpha 假设
   -> 产生 Feature
   -> 分析 Feature 与未来收益的关系
   -> 按市场状态分组
   -> 检查 Long / Short 不对称
   -> 检查不同 Forward Horizon
   -> 验证成本后是否仍有价值
   -> 有证据的 Feature 才进入策略开发
```

### 6.2 Feature Research 应回答的问题

1. 该特征测量什么市场行为？
2. 与未来 6 / 12 / 24 / 60 / 120 bars 的收益是否有关？
3. 是否只在某些 Regime 下有效？
4. Long / Short 是否对称？
5. 不同 Instrument 是否一致？
6. 不同年份和验证窗口是否稳定？
7. 是否只是个别参数点或单一标的的偶然结果？
8. 扣除合理成本后是否仍有利用空间？

报告应明确 forward horizon、采样频率、持有期是否重叠、缺失值处理、样本数量和成本假设。

### 6.3 第一批 Feature Research 主题

| Feature 主题 | 研究特征 | 主要问题 |
|---|---|---|
| 波动率位置 | ATR percentile、HV percentile | 高 / 低波动下未来收益分布是否不同？ |
| 波动率变化 | 短 / 长 ATR 比率、扩张速度 | 扩张是否提供方向或择时信息？ |
| 价格位移 | EMA distance / ATR、rolling displacement | 偏离是否预示回归或延续？ |
| 趋势效率 | Efficiency Ratio、连续同向收益比例 | 效率高时延续概率是否提升？ |
| K 线形态 | Wick ratio、body / range、收盘位置 | 拒绝价格是否有条件预测力？ |
| 突破行为 | 突破幅度、follow-through、failed breakout | 突破是否延续，失败是否反转？ |
| 结构事件 | Swing break、BOS、CHoCH、liquidity sweep | 事件后收益分布是否改变？ |
| 收益分布 | Rolling skewness、kurtosis、tail ratio | 极端收益风险是否随状态变化？ |
| 统计特征 | Autocorrelation、residual、z-score | 是否存在短期延续或均值回归？ |
| 活动特征 | Tick-volume percentile、量价背离 | 活跃度是否增强信号质量？ |

### 6.4 用分位数减少参数爆炸

不建议一开始就扫描几十个 RSI、ATR、EMA 阈值。先使用粗粒度分位数：

- 0–20%
- 20–40%
- 40–60%
- 60–80%
- 80–100%

先比较每组的未来收益均值、中位数、分布和样本数，再决定是否深入局部区域。这能减少参数爆炸并提高解释性。

## 7. 多方向研究计划

多方向并行值得做，但前提是方向代表不同的信息来源，而不是把同一种指标换名字重复测试。

### 7.1 初始资源分配建议

| 方向 | 建议资源 | 目标 |
|---|---:|---|
| Market Structure | 25% | 突破、失败突破、流动性扫荡、结构延续 |
| Volatility | 20% | 压缩、扩张、波动状态变化 |
| Asymmetric Payoff | 20% | 区分入场无效与退出不佳，探索正向偏斜收益 |
| Statistical Alpha | 20% | 自相关、残差回归、条件期望 |
| Multi-timeframe | 10% | 高周期状态与低周期触发 / 执行的关系 |
| Traditional Indicators | 5% | 作为基线和对照，不再作为主要扩张方向 |

这些比例是建议的初始研究资源分配，不是历史绩效结论。第一轮 Feature Research 后应根据证据调整。

### 7.2 Market Structure

优先研究 Swing High/Low、HH/HL、BOS、CHoCH、Failed Breakout、Liquidity Sweep、Breakout Follow-through、Breakout Retest。

关键问题：
- 突破后未来 6 / 12 / 24 / 60 bars 是否有收益偏移？
- 突破幅度相对 ATR 是否重要？
- 是否需要收盘确认？
- 假突破是否比普通反转信号更有预测力？
- 高 / 低波动状态下是否不同？

### 7.3 Volatility Regime

研究 ATR percentile、Historical Volatility percentile、Short / Long Volatility Ratio、Compression Duration、Volatility Expansion Acceleration。

核心假设：波动率状态可能决定某类入场方式是否有优势，但波动率本身不必然提供方向。

### 7.4 Asymmetric Payoff / Trade Management

固定同一组 Entry Signal，只改变退出管理：

- 固定 ATR Stop；
- Swing Structure Stop；
- Trailing Stop；
- Time Stop；
- Partial Exit；
- Profit Extension；
- 波动率动态止损。

比较平均盈利 / 亏损、最大单笔盈利、右尾收益贡献、平均持仓时间、胜率、Profit Factor、Max Drawdown、Return / Drawdown 和成本敏感性。

该研究能区分 Alpha 来自更好的入场，还是更好的持仓和退出。注意每轮只改变少数因素，防止退出参数搜索本身过拟合。

### 7.5 Statistical Alpha

优先研究 Return Autocorrelation、Rolling Skewness、Conditional Mean Reversion、Price Displacement、Residual Mean Reversion、Volatility-adjusted Momentum。重点是找简单、稳定、可重复的条件关系，而不是堆复杂模型。

### 7.6 Multi-timeframe

建议研究不同周期承担不同角色：

```text
H1：定义 Regime / 方向背景
  |
M15：识别结构、回调或突破 Setup
  |
M5：确认 Entry / Execution
  |
Exit：结构或波动率驱动的非对称退出
```

这比简单给 M5 信号加一个 H1 EMA 过滤器更有研究价值。必须确保低周期决策只使用当时已经完成、真实可得的 HTF 数据，避免 look-ahead bias。

## 8. 验证体系与 OOS 保护

多方向探索会增加 Multiple Testing 和过拟合风险，因此必须加强验证纪律。

### 8.1 验证原则

- 实验前登记假设、特征、方向、期限和评价标准。
- 不根据最终测试集反复调整策略。
- Full 与 Last 12m 若时间范围重叠，不能视为两份独立验证。
- 时间序列按时间切分，不随机打乱。
- 使用 Walk-forward 检查跨时间段稳定性。
- 跨 Instrument 验证，同时注意标的之间并非独立样本。
- 记录全部尝试，不只记录成功策略。
- 记录参数搜索和筛选次数。
- 高换手策略增加成本和执行压力测试。

### 8.2 研究与验证阶段

| 阶段 | 目的 | 输出 |
|---|---|---|
| P0 Hypothesis | 明确 Alpha 假设 | 研究说明 |
| P1 Feature Analysis | 验证特征与未来收益的关系 | 分位数、条件收益、样本数 |
| P2 Prototype | 最小策略验证假设 | 策略与交易账本 |
| P3 Robustness | 参数、年份、标的、成本稳定性 | 稳健性报告 |
| P4 Walk-forward | 按时间滚动验证 | 分段结果 |
| P5 Nomination | 提名少量正式候选 | 冻结配置与提名记录 |
| P6 Protected OOS | 审批后独立评估 | 最终 OOS 结果 |

### 8.3 OOS 保护要求

**不得为了让更多策略通过而提前使用 OOS。**

正式提名前冻结：
- Strategy ID 和规则版本；
- 完整参数；
- Instrument / timeframe；
- Entry / Exit / Position sizing；
- 成本和执行模型；
- 数据版本 / fingerprint；
- 代码 commit；
- 提名原因和验证证据。

OOS pin / config hash 必须绑定候选策略完整配置，不能用空参数或默认参数计算。若配置未绑定，应视为保护机制尚未生效，不能因没有报错就认定 OOS 已保护。

OOS ledger 维持受控状态。本文不建议改变现有 OOS 消费政策。

## 9. 工程整改 Backlog

### P0：研究结果可信度和实验完整性

| 项目 | 风险 / 问题 | 动作 | 验收标准 |
|---|---|---|---|
| 运行日期一致性 | `iterations_2026-11-07.csv` 与 Registry / Trial Log 执行日期需核对；有未来日期命名或执行日期不清晰问题 | 统一执行时间、数据截止时间、报告生成时间、commit | 每次运行可追溯时间、数据和 commit |
| 报告完整性 | 需确认预期矩阵是否完整、是否重复 | 校验 expected / missing / duplicate cells | 缺失或重复单元明确报错或告警 |
| Benchmark | Buy & Hold 单一基准不足 | 增加 Cash、Long-only、Exposure-matched 等 | 方向和市场敞口可区分 |
| 验证窗口 | Full 与 Last 12m 重叠 | 报告窗口关系与独立性 | 重叠窗口不被当成独立验证 |
| OOS 配置绑定 | 参数是否完整传入 pin / hash 需要核验 | 完整核对参数链路 | 参数不完整时 fail closed |

### P1：效率与研究质量

| 项目 | 风险 / 问题 | 动作 | 验收标准 |
|---|---|---|---|
| 重复加载数据 | Variant / Cost Tier 可能重复读取 | Data Cache | 同一批次可复用数据 |
| 重复生成信号 | 成本变体重复计算信号 | Signal Cache + Trade Ledger | 信号不变时复用基础账本 |
| 高换手预筛选 | 交易频率过高 | 信号频率、持仓时间、成本敏感性筛选 | 完整回测前发现明显异常 |
| Feature Research | 策略生成多于特征验证 | Forward-return / conditional distribution | 可按分位数、Regime、Horizon 分析 |
| 交易指标 | 指标需统一 | 补 Return/DD、Calmar、Sortino、Turnover | 所有策略统一 Metrics Schema |

### P2：结构精简和维护

| 项目 | 风险 / 问题 | 动作 | 验收标准 |
|---|---|---|---|
| 薄 Wrapper | 多个入口仅传递固定 Strategy ID | 先实现通用 Runner，再迁移 | 新旧入口一致，Checker 支持 |
| 配置重复 | variants / registry / 文档重复维护 | 统一元数据来源 | 参数不再多处独立维护 |
| 批次生成脚本 | 一次性脚本长期留在主目录 | 分类长期工具、迁移工具、归档脚本 | 每个保留脚本用途清晰 |
| 过时文档 | 注释仍描述旧范围 | 清理 stale comments / docstrings | 文档和行为一致 |
| 目录结构 | 职责逐渐增多 | 渐进式整理目录 | 不引入大规模无价值重构 |

### 9.1 报告生成器应检查

- 实际结果行数是否等于预期矩阵；
- Strategy / Instrument / Window / Cost Tier 是否唯一；
- 是否有重复、缺失、失败或跳过结果；
- 代码 commit 和数据版本是否一致；
- 指标为空是否有合理解释；
- 汇总是否跨 window 重复计数。

特别注意：如 `win_instr` 在 Full 和 Last 12m 两个重叠窗口重复累计，可能导致显示超过实际 Instrument 数量。应明确统计粒度，不能把窗口行数误当成独立标的数。

### 9.2 历史策略逻辑的定向复核

以下是早期 review 提出的疑点，需要针对 `936f7b9` 当前代码逐项复核；不应未经核对就当成最新 commit 已确认的缺陷：

- **S-08 CCI：** `enter_below=100`、`exit_above=-100` 是否符合预期的超卖反转逻辑；检查状态机是否会不合理地快速退出。
- **S-18 VWAP Stretch：** 曾有 `d[j-1] / atr[j]` 使用当前 ATR 而非对应历史 ATR 的索引错配疑点。
- **S-21 Squeeze：** 曾有在 squeeze 仍成立时入场、解除时退出的疑点；确认其是否真正交易压缩后的扩张。
- **NaN Guard：** EMA / ADX / SuperTrend gate 在 NaN 时是否 fail-open，缺失特征是否会意外允许交易。
- **Buy & Hold Metrics：** 引擎已有 Benchmark 指标是否完整传递到 CSV 和报告。
- **报告汇总：** 跨 window 计算赢利 Instrument 数时是否重复累计。

若仍存在，应先修复并增加测试，再扩大策略搜索。

## 10. 实施路线图

### Phase 1：Strategy Taxonomy

任务：
1. 梳理所有 Strategy ID。
2. 增加 Alpha Source、Regime、Entry、Exit、Payoff、Timeframe 标签。
3. 统一 Registry / YAML / Trial Log 元数据。
4. 生成按 Alpha Source 汇总的历史表现。
5. 识别高度相似策略、重复逻辑和缺乏假设的策略。
6. 保留现有 Strategy ID，避免历史结果断链。

交付物：
- `strategy/docs/strategy_taxonomy.md`
- 更新后的 Registry / metadata
- `strategy/reports/alpha_family_summary.csv` 或等价报告

验收：所有策略均可分类；允许多标签；历史结果可按类别汇总；不影响复现。

### Phase 2：Research Engine Efficiency

任务：
1. 对 `strategy_variants.py` 和批量入口 profiling。
2. 明确 Data / Feature / Signal / Execution / Cost Replay / Metrics 边界。
3. 实现 Data Cache、Feature Cache。
4. 建立标准 Trade Ledger。
5. 在适用场景实现多 Cost Tier Replay。
6. 加入 fingerprint、版本失效机制和耗时统计。

验收：同一批次避免无意义重复加载；成本变体可复用信号/账本；缓存不会错误复用；固定测试数据新旧结果一致；有量化效率改善证据。

### Phase 3：Feature Research

任务：
1. 建立标准 Feature Dataset。
2. 计算 6 / 12 / 24 / 60 / 120 bars forward return。
3. 做 Quantile / Percentile Buckets。
4. 按 Regime 分组。
5. 拆分 Long / Short。
6. 输出样本数、均值、中位数、波动率和分布。
7. 做时间切分，检查稳定性。
8. 明确重叠持有期，避免错误解释统计显著性。

交付物：
- `strategy/research/feature_analysis.py` 或等价模块；
- Feature Research 报告模板；
- 可复现的实验记录。

验收：不同标的、期限、Regime 可统一分析；无需先构建完整策略；报告显示样本量和时间范围。

### Phase 4：Alpha Family Exploration

首轮按 Market Structure 25%、Volatility 20%、Asymmetric Payoff 20%、Statistical Alpha 20%、Multi-timeframe 10%、Traditional Indicators 5% 分配研究资源。

执行方式：
1. 每个方向提出有限且可解释的假设。
2. 用 Feature Research 先筛选证据。
3. 仅将有条件预测力的特征做成 Prototype。
4. 每次只改变少数因素。
5. 保留统一基线和全部实验记录。

验收：每个策略能说明 Alpha 来源；不同方向代表不同信息源；不是简单叠加相关指标；结果能跨时间或市场复现。

### Phase 5：Robustness & Walk-forward

任务：明确时间边界；Walk-forward；参数邻域稳定性；跨年份 / Instrument / Regime；成本与执行压力测试；适当 Benchmark；记录全部搜索尝试。

验收：不依赖单一参数尖峰、单一 Instrument 或短暂行情；成本后仍合理；重叠窗口不被误判为独立 OOS。

### Phase 6：Nomination & Protected OOS

正式提名后冻结 commit、数据、参数和执行假设；核验 OOS config hash；按现有治理要求审批；保持 ledger 和访问规则受控。

验收：OOS 仅在正式提名后使用；每次运行可追溯冻结配置；不根据 OOS 反复调参后仍称其为未使用数据。

## 11. 建议执行顺序

| 顺序 | 工作 | 优先级 | 原因 |
|---:|---|---|---|
| 1 | 核对日期、矩阵完整性、Benchmark、验证窗口 | P0 | 先确保已有结论可信 |
| 2 | 完成策略多维 Taxonomy | P1 | 研究可分类、可统计 |
| 3 | Variant Runner Profiling | P1 | 确定效率瓶颈 |
| 4 | Data / Feature Cache 和 Trade Ledger | P1 | 减少重复计算 |
| 5 | Feature Research 第一版 | P1 | 从策略枚举转向 Alpha 发现 |
| 6 | 首轮探索不同 Alpha Family | P1 | 扩展独立研究方向 |
| 7 | 候选收敛和 Walk-forward | P1 | 控制过拟合 |
| 8 | Nomination 与受保护 OOS | 受控 | 只评估少量候选 |

### 第一轮 MVP

先实现：
1. 全部策略的 taxonomy metadata；
2. ATR percentile、EMA distance / ATR、wick ratio、breakout / failed breakout 的 Feature Research；
3. 未来 6 / 12 / 24 / 60 / 120 bar 收益分析；
4. Quantile + Regime + Long / Short 分组；
5. 统一研究报告；
6. Variant Runner 耗时 profiling；
7. Data Cache / Signal Cache 的设计与验证。

第一轮的核心问题是：**哪些市场特征真的值得继续投入策略开发？**

## 12. 最终建议

Moneta 下一阶段不应以“增加了多少 Strategy ID、跑了多少 Variant、生成多少结果文件”作为主要进展指标，而应关注：

- 验证了多少个独立 Alpha 假设；
- 多少特征有可重复的条件预测力；
- 多少策略在不同 Instrument / 时间段 / Regime 下稳定；
- 扣除合理成本后是否仍有净 Alpha；
- 每次研究消耗多少计算资源；
- 从假设到结论的周期是否缩短。

建议下一份设计文档为：

`docs/alpha_discovery_architecture_draft.md`

只覆盖 Strategy Taxonomy、Feature Research 数据模型、Experiment Workflow、Data / Feature / Signal Cache、Trade Ledger 与 Cost Replay、Validation / Walk-forward，以及现有 Moneta 代码的迁移边界。

在架构草案完成前，不建议大规模重写核心引擎，也不建议继续单纯以新增策略数量作为主要开发目标。

## 附录：本次 Review 参考位置

- Latest commit：https://github.com/ttrrei/moneta/commit/936f7b91a1f8f30f80a348763cd9d76452aabc1c
- Diverse strategy library：https://github.com/ttrrei/moneta/blob/936f7b9/strategy/strategy_diverse_lib.py
- Variant runner：https://github.com/ttrrei/moneta/blob/936f7b9/scripts/strategy_variants.py
- Results checker：https://github.com/ttrrei/moneta/blob/936f7b9/scripts/check_results.py
- Matrix runner：https://github.com/ttrrei/moneta/blob/936f7b9/strategy/run_matrix.py
- Diverse batch design：https://github.com/ttrrei/moneta/blob/936f7b9/strategy/docs/strategy_batch_20261030_design.md
- Follow-up verification：https://github.com/ttrrei/moneta/blob/936f7b9/docs/repo_review_20261030_followup_verification.md
- Trial log：https://github.com/ttrrei/moneta/blob/936f7b9/strategy/trial_log.md
- Strategy registry：https://github.com/ttrrei/moneta/blob/936f7b9/strategy/STRATEGY_REGISTRY.md
