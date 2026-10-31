# moneta / Nova 重构路线（R0–R6）

> **一句话结论**：代码不是病根，**搜索几何**才是。仓库里已经存在正确的架构
> （S-113..S-132 的声明式 `RuleSpec`），但它只覆盖了 20/132 个策略，其余
> 112 个仍是手写复制粘贴的旧方言。本次重构的方向不是"发明新架构"，而是
> **把已经存在的正确架构推成唯一架构**，同时把一次迭代的成本降一个数量级。

---

## 一、诊断：三组数字

### 1. 三代研究，零幸存者

| 研究批次 | 规模 | 结果 | 幸存 |
| --- | --- | --- | --- |
| 旧方言家族（S-01..S-112） | 132 个策略 × 806 个变体槽 | 130 rejected / 2 parked | **0** |
| 指标目录（CATALOGUE-50） | 50 个指标 / 2250 次比较 | 43 reject / 7 revise | **0** |
| 两轮策略研究（SR-20261031-200） | 200 条可执行规则 / 9000 个回测格 | 199 revise / 1 reject | **0** |

三代研究、约 **380 个假设**，通过率 0%。这不是"运气不好"，是**采样方式**的问题。

### 2. 仓库里有三种方言讲同一件事

```
方言 A（手写复制粘贴）  strategy/strategy_roc_lib.py, strategy_mfi60_lib.py, ...
                        → 132 个文件，每个 ~150 行，同一副骨架换阈值
方言 B（同骨架多旋钮）  strategy_quadosc_lib / strategy_triosc_lib / ...
方言 C（声明式 spec）   strategy/strategy_diverse_lib.py 里的 RuleSpec
                        → 20 个 spec，条件表 + 假设 + 预期交易数 + 差异说明
```

量化方言 A 的重复度：**132 个文件只有 72 种结构形态**，其中一种形态覆盖 23 个文件；
112 个文件各写各的 `desired_position` 状态机。

### 3. 迭代菜单只有一维

`strategy/variants.py` 里有 **806 个变体槽**（105 个策略 × 平均 7.7 个变体）。
按出现频次排：

```
105  base          105  entry_guard       97  1h           95  ema_gate
 71  combo          70  wide_exit        64  looser       58  stronger
 15  ema_guard      14  1h_ema   14  1h_guard  14  1h_ema_guard   7  slower  ...
（其余 48 个名字，每个出现 ≤ 7 次，全是手写的一次性旋钮）
```

**`entry_guard` 出现在 105/105 个策略上——它不是迭代维度，它是一个全局常量。**
真正被反复使用的只有 `ema_gate` 和 `1h` 两个轴，再加上每个策略自己临时发明的
一个旋钮。也就是说：**名义上 806 次迭代，实际搜索维度约为 2**。

在一条二维流形上采样 806 次，找到 edge 的概率不会随采样次数上升——只会在同一个
位置反复命中。这就是 130 个 rejected 的结构性原因。

---

## 二、根因：搜索空间退化成了"参数网格"

132 个策略看起来像 132 个假设，其实只有约 12 个假设 × 窗口后缀。
每个假设的"下一个迭代"不是从**失败的诊断**里长出来的，而是从一个**固定的旋钮菜单**里挑的：

```
base / ema_gate / slower / 1h / entry_guard / band_wide
```

这个菜单和诊断没有任何关系。所以：

- 迭代**没有针对性**——`ema_gate` 是在不知道"为什么这个策略亏钱"的情况下被施加的；
- 分布**不广**——菜单本身只有一条轴；
- 130 次 rejected 没有留下任何可迁移的知识，只留下 130 行注册表。

对比之下，`research/` 层（`strategy/research_rules.py`、`research_cohort.py`、
`catalogue_research.py`）已经具备正确形状：**hypothesis → role → model → episode
→ semantic_hash → cohort → matched inference → bootstrap**。它是**有方向的**，
但它住在一个孤岛里，没有接进注册表；旧方言仍然占据仓库绝大部分的质量。

> **"失去重心"是字面意义上的：仓库里有两个引擎，没有脊柱。**

---

## 三、答案已经在仓库里了

方言 C（`RuleSpec`）已经具备旧方言没有的三个字段：

```python
@dataclass(frozen=True)
class RuleSpec:
    hypothesis: str        # 可证伪的主张
    expected_trades: str   # 机会频率的先验（如 "20–180"）
    difference: str        # 与已试过 idea 的区别 —— 人类可读的去重理由
```

这三个字段正好对应你要的三件事：

- `hypothesis` + `role` → **迭代有针对性**（下一版针对父版的失败模式生成）
- `family` + `side` + `horizon` → **分布更广**（按假设空间轴配额分配，而不是让热门指标自然垄断）
- `difference` + `semantic_hash` → **去重前置**（重复的想法在烧掉一次回测之前就死掉）

所以重构不是推倒重来，而是**把 S-113 已经证明可行的架构推广到全部策略**。

---

## 四、重构路线

每个阶段独立可交付、可验收、可回滚。**R1 / R2 已在本 PR 落地**。

### R0 · 止血：把死重量降下来（0.5 天）

| 动作 | 现状 | 目标 |
| --- | --- | --- |
| 删除 12 个 `_gen_batch*.py` 代码生成器 | 它们是复制粘贴机器的源码 | git 历史里有，不必留在树上 |
| `research/**/source_snapshot` + `prior_snapshot` → git SHA | 919 个受版本控制的文件 / 28k LOC；10 个 `source_snapshot` 目录、5 层嵌套 `prior_snapshot` | 快照是冗余的——git 已记录 SHA；嵌套让体积按 2ⁿ 增长 |
| 60 份 `strategy/docs/strategy_*_report.md`（已 rejected） | 混在活跃目录里 | 归档或 git tag |

验收：`git ls-files | wc -l` 从 1650 降到 ~450。

### R1 · 统一规范语言（**已完成**）

新增 `strategy/rule_spec.py`：

- `RuleSpec` 升为全仓唯一规范，条件词汇**封闭**（`above` / `below` /
  `cross_up` / `cross_down` / `cross_above` / `cross_below`）；
- 新增方向性字段：`family`（momentum / reversion / breakout / volatility / flow /
  seasonal / microstructure）、`role`（这个 idea 是为哪种状态准备的）、
  `side`、`horizon`；
- 新增血缘字段：`parent` / `mutation` / `rationale`——**迭代链**从这里开始可审计；
- `signal_identity()`：OOS `config_hash` 只取**信号字段**，给策略重新贴标签
  绝不会改变一个已 pin / 已裁决运行的身份。

`config/strategy_specs.yml`：S-113..S-132 从 Python 字面量迁成数据。
迁移用 golden digest 锁死（`tests/test_rule_engine.py`），任何漂移直接红。

### R2 · 引擎：空间换时间（**已完成**）

三条独立收益：

1. **信号只算一次，跨成本档复用。**
   旧路径每个成本档重建一次 rule → 同一个信号被算 3 遍。现在
   `run_backtest(..., positions=...)` 接受预计算的位置数组，
   `strategy/strategy_spec_runner.run_spec_costs()` 加载一次、算一次、复用三次。

2. **向量化求值。**
   `strategy/rule_engine.py`，靠两个观察：
   (a) 仓位只可能在某个条件组触发的 bar 上变化，其余 bar 只是"持有"；
   (b) 内层循环应访问 Python 对象而不是 NumPy 标量（0.5µs → 0.03µs）。
   实测（120k bars × 5 个 spec）：

   | | 每 bar oracle | 新实现 | 加速 |
   | --- | --- | --- | --- |
   | 密集事件（iid 噪声，最坏情况） | 8.86 s | 198 ms | **×44.7** |
   | 真实分布（随机游走） | 7.50 s | 26 ms | **×285** |

   结果与逐 bar oracle **逐位相同**（不是近似）。三种实现两两互验：
   逐 bar oracle / 向量化快路径 / 可读事件路径。

3. **列式缓存**（R2 第三步，尚未落地）：`cache_bars` 目前按 `feature_cols`
   做 key，两个读不同列的策略永远不共享同一帧 → 每个策略各扫一次 parquet。
   改为按 (instrument, window, not_null_cols) 缓存**宽帧**再切片，
   一次扫描服务全部策略。8GB 内存约束下按 instrument 逐个加载即可。

### R3 · 定向变异算子（核心，目标 2–3 天）

把固定旋钮菜单换成**诊断驱动的算子**。每个算子是 spec 上的纯函数
`mutate(spec, diagnosis) -> new_spec`，拟合只在训练段进行（现有 OOS 纪律不变）：

| 父版的诊断 | 算子 | 作用 |
| --- | --- | --- |
| 交易集中在 < 4 个日历月 | `SeasonalMask` / `SeasonalAvoid` | 拆掉季节性混淆 |
| 胜率正常、盈亏比差 | `AtrTrailingExit` / `PartialTakeProfit` | 修退出腿 |
| 交易次数太少 | `RelaxThreshold`（用**拟合**出的切点） | 提覆盖度 |
| 交易多但 2bps 后净亏 | `CostFilter` / `WidenTarget` | 砍摩擦 |
| 只在高波动状态亏 | `RegimeGate`（训练段拟合） | 打到有效状态 |
| 想法本身对称但只做多 | `AddShortSide` | 假设空间直接翻倍 |
| gross > 0 但 net < 0 | `CostAwareEntry`（要求位移 > k×成本） | 成本感知 |

每个变体记录 **parent + mutation + rationale**，`trial_log.md` 从自由文本变成
**血缘图**——这才是"迭代有针对性"的可审计形态。

### R4 · 分布控制（目标 1–2 天）

维护 (family × side × regime × horizon) 的**配额**，下一个候选必须填补**欠代表**的格子。
复用 `research/research_cohort.py` 已有的分层机制。

当前分布快照（问题确实存在）：

| | 方言 A（旧，112 个） | 方言 C（新，20 个） |
| --- | --- | --- |
| 只做多 | **110 / 132** | 0 / 20 |
| 单指标 | 绝大多数 | 全部多指标（2–5 个列） |
| family 覆盖 | 无从统计 | breakout 7 / momentum 5 / reversion 5 / flow 2 / volatility 1 / **seasonal 0 / microstructure 0** |
| side | long 为主 | both 20/20 |

### R5 · 准入闸门（目标 2 天）

当前准入线是"跑赢 buy-and-hold"。在 380 次尝试、**没有多重检验控制**的前提下，
这条线约等于 50% 噪声。要加：

1. **预注册**：运行前写下假设、预期方向、预期效应量与判定规则。
2. **行为去重前置**：`semantic_hash` + 位置数组重叠度（Jaccard）对照注册表。
   重复的想法在 Stage 0 就死掉，不烧回测。
   现有的 X15 饱和检查是**词法**的（按指标名归族）、且**事后**的；这个是
   **行为**的、**事前**的。
3. **漏斗**：Stage 0 去重 → 单标的单窗口 → 3 标的 × 2 窗口 → 成本档 → OOS。
   把算力集中到有信号的地方。
4. **统计闸门**：复用 `research/research_statistics.py` 已有的 bootstrap /
   combine_tests，要求净收益对 BH 的置信区间与最小交易数，而不是"跑赢"。

### R6 · 注册表即数据（目标 1 天）

`STRATEGY_REGISTRY.md`（150KB）和 `trial_log.md`（76KB）目前被两个地方用正则解析
（`strategy/registry.py`、`scripts/check_results.py`）。改成 YAML / JSONL 为准，
Markdown 由它生成。之后去重、血缘、配额查询就是 SQL，而不是正则。

---

## 五、本 PR 已落地

| 文件 | 作用 |
| --- | --- |
| `strategy/rule_spec.py` | 规范语言：`RuleSpec`、封闭条件词汇、YAML 加载器、`signal_identity` |
| `strategy/rule_engine.py` | 向量化求值 + 逐 bar oracle（互为校验） |
| `strategy/strategy_spec_runner.py` | spec → 结果的统一执行入口（加载一次 / 算一次 / 复用成本档） |
| `config/strategy_specs.yml` | S-113..S-132 迁移为数据，并补齐方向性元数据 |
| `strategy/strategy_diverse_lib.py` | 瘦身为兼容 façade（`RULES` / `run_rule` / `cli_main` 签名不变） |
| `strategy/engine.py` | 新增 `positions=` 快路径；既有行为逐位不变 |
| `strategy/strategy_lib.py` | `run_strategy(..., positions=...)` |
| `tests/test_rule_engine.py` | 95 个测试：迁移保真、等价性、因果性、闸门 |

兼容性：`strategy/code/*.py`（20 个 CLI）、`strategy/strategy_*_lib.py`（20 个薄适配器）、
`strategy/run_matrix.py`、`strategy/variants.py`、`scripts/*` 的导入路径与行为全部不变。

---

## 六、度量与回归基线

| 门禁 | 结果 |
| --- | --- |
| `pytest tests/ -q` | **852 passed**（重构前 757） |
| `scripts/check_results.py` | `PASS — 0 failure(s), 22 warning(s), 288 note(s)` |
| `scripts/test_check_results.py` | `40/40 mutation cases passed` |
| `python -m compileall -q pipeline library strategy scripts tests` | OK |

其中 OOS `config_hash` **逐策略未变**（已用 `signal_identity` 锁定），
所以已 pin / 已裁决的运行不会被这次重构影响。

---

## 七、不要做的事

- **不要**再加一个 `strategy_XXX_lib.py`。新策略 = `config/strategy_specs.yml` 里加一行。
- **不要**在旧方言上加变体。旧方言的唯一出路是迁到 spec。
- **不要**把 `research/**/source_snapshot` 当成归档手段。git SHA 已经做了这件事。
- **不要**用"跑赢 buy-and-hold"当唯一准入线。380 次尝试下它约等于噪声。
- **不要**在没有多重检验控制的情况下扩大批量。分布要广，但每次尝试都要能解释。

---

## 八、下一步建议顺序

```
R0 止血（半天，把仓库变轻）
  ↓
R3 定向变异算子（这是"迭代有针对性"的真正落地，优先于迁完 112 个旧文件）
  ↓
R5 准入闸门（行为去重 + 漏斗 + 统计闸门）
  ↓
R4 分布配额（依赖 R3 的 family/role 元数据）
  ↓
方言 A 批量迁移（112 个文件 → spec 行；此时已有工具，边际成本低）
  ↓
R2.3 列式缓存
  ↓
R6 注册表即数据
```

**注意顺序**：先有"针对性"和"闸门"，再迁旧策略。否则只是把 112 份
无方向的参数网格换成 112 行 YAML——省了代码，没省方向。
