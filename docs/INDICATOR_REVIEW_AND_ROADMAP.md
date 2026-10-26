# Review：策略生成闭环状态 & 指标补充路线（PSAR / SuperTrend 等）

> 生成日期：2026-10-27　对象仓库：`ttrrei/moneta` (main)
> 依据材料：`docs/`（BRD / SAD / indicators.md / data_profile.md）、`strategy/`（WORKFLOW.md / STRATEGY_BACKGROUND.md / STRATEGY_REGISTRY.md / generated_strategy.md）、`config/indicators.yml`、`pipeline/indicators.py`

---

## 1. 闭环状态评估

**结论：逻辑已闭环，但当前环境无法端到端运行。**

### 1.1 已具备的闭环要素 ✅

| 环节 | 对应产物 | 状态 |
|---|---|---|
| 前置检查 | `WORKFLOW.md` Gate G0–G3 | 定义完整，与 `config/indicators.yml` 列数/白名单同步 |
| 选题与查重 | `STRATEGY_REGISTRY.md` + `STRATEGY_BACKGROUND.md` 特征表 | 契约一致 |
| 注册 | Registry 状态机（candidate → implemented → tested → …） | 可追溯 |
| 编码 | `strategy/code/` + 列名/窗口硬约束 | 规范明确 |
| 运行 / 报告 / 评估 | 3×3×2 结果表（instrument × cost × window），含 buy-hold 基线 | 阈值成文（≥2/3 品种、双窗口跑赢 2bps） |
| 收尾 | Registry 回写 + 文档同步清单 | 存在 |

关键配置（列数 `ohlcv_5m_features: 259 = 234 + 25`、成本双边、warm-up 丢弃 `360 = 3×max(N)`）在代码与文档间完全同步。

### 1.2 阻碍实际运行的缺口 ⚠️

1. **数据与环境缺失**：`data/ohlcv_5m_features.parquet` 未入库，`.venv` / `talib` 不在本环境 —— Gate G0 会直接停止，无法执行任何回测。
2. **Registry 预登记占用**：S-02 / S-03 / S-04 为预登记候选，占用了部分指标组合，压缩了新策略的自由选题空间。
3. **缺少指标回归保护**：没有针对 `indicators.py` 六重质量门禁的自动化校验脚本（如 `verify_indicator_parity.py`），新增指标时缺乏数值对拍与防漂移手段。

---

## 2. PSAR 与 SuperTrend 确认

**结论：两者均缺失，且都应当加入。**

- 全库检索（`*.py` / `*.md` / `*.yml`，大小写不敏感）对 `psar`、`supertrend` **零命中**。
- 现有趋势族仅为平滑均线类（MA/EMA 及其派生），**缺少"止损反转 / 持有期跟踪"维度**——即随行情推进动态抬高（或压低）的跟踪位，以及由该跟踪位触发的翻转信号。

### 2.1 PSAR（Parabolic SAR）

- **用途**：低频反转出场逻辑；SAR 上穿价格 → 转多，下穿 → 转平/转空。
- **实现注意**：
  - 递归状态机（极值点 EP 与加速因子 AF 依赖上一根 bar 的状态），**不能向量化为一行 rolling**；需按 instrument 分组迭代。
  - Warm-up 收敛问题：初始 AF/EP 的选取会影响前若干根 SAR 值，必须保证丢弃窗口内状态收敛后再出信号（与现有 `warmup_drop` 机制对齐）。
  - 输出建议同时给出 `psar`（价位）与 `psar_bull`（0/1 方向位），后者尺度无关，供策略层直接使用。

### 2.2 SuperTrend

- **用途**：Regime-gate 型入场/出场；价格在 `st_line` 上方持多、跌破翻转。
- **实现注意**：
  - 基于 ATR band + 轨道收窄递推（band 只收紧不放宽），同样是分组递推逻辑。
  - 输出建议：`st_line`（价位，ATR 归一化后可跨品种比较）与 `st_dir`（+1/−1）。
  - 若引入 `pandas_ta_classic` 等外部实现，必须先用自研参考实现对拍，通过后才可作为权威来源。

---

## 3. 额外推荐补充的指标

按填补维度空白的优先级排序：

| 优先级 | 指标 | 维度空白 | 理由 |
|---|---|---|---|
| 1 | **KST** (Know Sure Thing) | 多尺度动量合成 | 信号稀疏，契合低交易频率目标；四组 ROC+ SMA 天然覆盖多个回看尺度 |
| 2 | **TRIX + Signal** | 三重 EMA 去噪动量 | 适合作为 1h 背景层的慢速触发器，与现有 MACD 家族形成快慢分层 |
| 3 | **Vortex (vi+ / vi−)** | 独立方向强度度量 | 与既有基于价差/成交量的方向指标相关性低，提供正交信息 |
| 4 | **PVO** (Percentage Volume Oscillator) | 成交量活跃度背离 | 现有量能族缺百分比差形式的振荡器；无量纲，跨品种可比 |

### 3.1 不建议添加

| 指标 | 拒绝理由 |
|---|---|
| Ichimoku 迟行带 (Chikou Span) | 位移到未来的画法在特征表中引入**未来函数风险** |
| Zigzag / Fractals | **重绘**（repaint）：分形确认依赖后续 bar，回测不可复现 |
| OBV / PV 原始累计值 | **非平稳、跨品种不可比**；如需应改为 PVO 等归一化形式 |

---

## 4. 参数约束规则（重要澄清）

> 本节回应审阅中提出的约束边界问题，是新增 PSAR / SuperTrend 等指标时的硬性规范。

### 4.1 白名单只约束"时间窗口"参数

`config/indicators.yml` 中的网格：

```yaml
parameter_grid:
  windows_n: [6, 12, 24, 60, 120]   # every rolling-window indicator
```

**适用范围**：所有以"回看多少根 bar"为语义的参数——即 `{n}` 占位符所代表的 rolling 周期（MA/EMA/RSI/MACD span/Stoch %K%R period/KST 各 ROC 周期/TRIX 周期/Vortex period/PVO fast-slow 等）。这些参数**只能取 6 / 12 / 24 / 60 / 120**，不得发明新窗口（`indicators.yml` 第 12 行注释已声明这是硬白名单）。

### 4.2 非窗口参数不受白名单限制

以下类型的参数**不属于时间窗口**，允许按指标自身惯例取值，不受 `[6,12,24,60,120]` 约束：

| 指标 | 受限参数（窗口） | 不受限参数（非窗口） |
|---|---|---|
| PSAR | —（无回看窗口） | `af_start`（默认 0.02）、`af_step`/`increment`（默认 0.02）、`af_max`（默认 0.2） |
| SuperTrend | `atr_period` ∈ {6,12,24,60,120}（建议 24） | `multiplier`（默认 3.0，可取 1.0–5.0 连续值） |
| KST | 四组 ROC/SMA 周期全部 ∈ 白名单 | signal SMA 周期同样属窗口，须用白名单值 |
| TRIX | roc_period、trix_smooth、signal_period 均属窗口 | — |
| Vortex | period ∈ 白名单 | — |
| PVO | fast/slow/signal 均属窗口 | — |

**判定准则**：参数单位若是"bar 数 / 周期数"→ 受白名单约束；若是"倍率 / 步长 / 系数 / 阈值"→ 不受约束，但必须在 `config/indicators.yml` 中显式登记其取值（或取值网格），并计入 warm-up 长度估算。

### 4.3 新增指标的同步修改顺序（缺一不可）

1. `pipeline/indicators.py` — 实现计算逻辑（分组递推、无未来函数）
2. `config/indicators.yml` — 登记列名、列数计数（如 `259 → 2xx`）、非窗口参数取值
3. `docs/indicators.md` — 更新目录表（名称 / 公式 / 参数 / 尺度说明）
4. `strategy/STRATEGY_BACKGROUND.md` — 更新特征表，使策略选题可见
5. `strategy/STRATEGY_REGISTRY.md` — 登记使用新指标的策略 ID（candidate 起步）

另建议补第 6 步：新增 `tests/test_indicators_<name>.py`，用独立参考实现（或 TA-Lib）做数值对拍，作为六重质量门禁之外的回归保护。

---

## 5. 下一步行动清单

- [ ] 落地 `psar` / `psar_bull`（递推实现 + warm-up 收敛测试）
- [ ] 落地 `st_line` / `st_dir`（ATR 递推轨道 + 与参考实现对拍）
- [ ] 视优先级追加 KST → TRIX → Vortex → PVO
- [ ] 编写 `verify_indicator_parity.py`（或 pytest 等价物）覆盖全部指标
- [ ] 补齐本地运行条件：生成/放入 `ohlcv_5m_features.parquet`、建立 `.venv` + `talib`，使 Gate G0 可通过
- [ ] 每加一组指标后同步更新 §4.3 五处文档/配置，保持列数计数一致
