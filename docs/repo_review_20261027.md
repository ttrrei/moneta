# Moneta 行动清单（合并自 review1–4 + repo_review_20261027）

> 生成日期：2026-10-27。每条均对照 main 分支代码核实过位置。
> 用法：从上往下做，P0 全部完成前不启动 P2/P3。
> 取代：`docs/repo_review_20261027.md`、`legacy/review1.md`、`review2.md`、`review3.md`、`review4.md`
> （本文件定稿后，上述文件建议移入 `legacy/archive/` 或直接删除——git 历史保留内容）。

---

## 0. 五份 review 的质量评估（先回答你的两个问题）

| 文件 | 质量判断 | 依据 |
|---|---|---|
| `review4.md` | **最高质量**，可直接作为行动依据 | 每条有 file:line + 探针实测（span_years 两种 bar_seconds 结果相同、rule 被调 20 次等均已在本仓库复验属实）；"不要做什么"清单克制、不造轮子 |
| `review1.md` | 高质量，独有发现最有价值 | **DST 按整月算错**（已复验：`_eu_dst_active` 是 3–9 月一刀切，3/5 对 NY 锚点错 1 小时）和 `is_near_market_close` 并集变 3 小时（已复验：`in_window(winter) | in_window(summer)`）这两条只有它抓到 |
| `review2.md` | 合格，是四份中文 review 里最凝练的 | 结论与其他三份一致；P0–P3 排序合理；没有明显错误主张 |
| `review3.md` | 合格，独有贡献是空头成本公式 | 已复验 `strategy/engine.py:241`：`px_entry*(1+cost)/(px_exit*(1-cost))-1` —— 成本越大空头收益越高，方向确实反了 |
| `docs/repo_review_20261027.md` | **不合格，建议删除** | 只做了表面扫描就下"highly stable and disciplined"结论：漏掉 OOS 窗口重叠、空头成本方向、rule 双调用、DST 全部四个 P0/P1；"建 Dockerfile"在 Linux 上无必要；"新建 CONTRIBUTING.md"被另外三份 review 以充分理由反对（已有三份等价物）。仅两条有效点（B6 统一、timeframe guard 上提）已被本清单 §1.5/§1.7 吸收 |

**过度工程检查结论**：review1–4 的"该做的"都是修复和最小门禁，没有造轮子；真正的过度工程候选（DSL、walk-forward、代理框架、第四份 CONTRIBUTING、真实数据 fixture）四份 review 一致建议**不做**，本清单照单采纳。唯一需要裁量的是 §1.9 Sharpe 口径——那是"换个口径"而不是"加系统"，工作量一天内，可以现在做也可以先只改文档声明，二选一。

---

## 1. P0 — 会算错数字 / OOS 已污染（先修这些，其他都排在后面）

### 1.1 OOS holdout 被样本内窗口吃掉了 ⭐ 全局最高优先
**证据**（`config/strategies.yml` 原文）：`windows.full.since: null`、`windows.last_12m.since: 2025-10-27`、`oos.holdout_start: 2025-08-01`。今天=2026-10-27 → `last_12m` **完全落在 holdout 内**，`full` 也包含它。`load_bars` 只有 `since` 没有 `until`，`run_matrix --windows` 只有 `full/last_12m` 两个可选值，`--windows oos` 会报 Unknown window。**每次矩阵回测都在 holdout 上调参，"只跑一次"纪律已实质失效。**
**修法**（约半天）：
1. `strategies.yml`：`windows.full.until: "2025-07-31"`、`windows.last_12m` 保留 since、`until: "2025-07-31"`（两个都截到 holdout 前）；`windows` 下新增 `oos: {since: "2025-08-01", until: null}`。
2. `strategy_rsi_lib.load_bars` / `run_rsi` 加 `until` 参数（SQL 加 `time <= ?`）。
3. `run_matrix.py` 的 windows 选择器改为读 `strategies.yml` 的 windows 键（含 `oos`）；`--windows oos` 时检查 `strategy/trial_log.md` 已有该策略 oos 行则拒绝再跑（一次性锁）。
4. **附带决策**：S-01 此前所有在 holdout 区间内的数字都不能再当 OOS 证据引用；报告里标注"该结果产生于 OOS 门禁就位之前"。

### 1.2 空头成本公式方向反了
**证据**：`strategy/engine.py:241`（long 分支 :240 正确）。`cost` 越大空头收益越高，0/2/5 bps 成本敏感性对任何未来双向策略都会给出**方向错误**的结论。`tests/test_metrics.py` 空头对称性用零成本，测不出来。
**修法**（30 分钟）：空头净收益统一为"买入价 = px_entry*(1-cost)、卖出(平仓)收益按 px_exit*(1-cost) 口径"——即 short ret = px_entry*(1-cost)/(px_exit*(1+cost)) - 1；加一个非零成本空头 golden 测试。

### 1.3 会话锚点的 DST 按整月算错（review1 独有发现，已复验）
**证据**：`pipeline/indicators.py` `_eu_dst_active(month)` = `3 <= month < 10`，套用到 **NY 锚点**（FX、US 指数）。美国 DST 切换日（3 月第 2 个周日 / 11 月第 1 个周日）与欧洲不同，每年 ~2–3 周内 UTC 锚点错 1 小时 → `session_reset_index`、session VWAP 派生特征错。
**修法**（半天，含重建）：改用 `zoneinfo`（`America/New_York`、`Europe/Berlin` 等按锚点所属时区）对**具体日期**算 offset；改完**必须重建 5m/1h 特征 parquet**。S-01 只用 `rsi_24` 不受影响，可作重建前后的回归对照（改前先用真实数据跑一遍 S-01 留基线，见 §3.6）。

### 1.4 `is_near_market_close` 是 3 小时不是 2 小时（已复验）
**证据**：`pipeline/indicators.py` `is_near_market_close_series` 对 winter/summer 两个 offset 各算一个 2h 窗口再取**并集** → 实际 3 个 UTC 小时被标记。
**修法**（30 分钟）：按 §1.3 的 per-date offset 只选**当月生效**的那个窗口；顺带修正文档"2 小时"与代码的矛盾（修完后自然一致）。

### 1.5 entry guard 默认值四处不一致（已复验）
**证据**：`strategy_rsi_lib.run_rsi(..., entry_guard=True)` 与 `make_bars(..., entry_guard=True)` 默认**开**；`strategy/code/strategy_rsi.py` CLI 只有 `--entry-guard`（默认**关**）且 docstring 写"default ON … `--no-entry-guard`"（**两个都错**）；`run_matrix.py:253` 默认**关**；S-01 官方报告按"关"记录。直接调库和走 CLI 结果不同。
**修法**（1 小时）：定死 S-01 官方基准 = **关**（与已发布报告一致）；库函数默认改为与 CLI 相同；docstring 改为实际参数；`run_matrix` 输出的 matrix.md 每格已记录 entry_guard 列（现状 OK），报告里显式写基准值。

### 1.6 `long_only=True` 时 rule 每根 bar 被调两次（已复验）
**证据**：`strategy/engine.py:232-233`：`0 if (long_only and rule.desired_position(i) < 0) else rule.desired_position(i)` —— 返回值 ≥0 时第二次又调。RsiState 恰好幂等才没出事；任何有副作用的 rule 会静默错。
**修法**（30 分钟）：
```python
raw = np.array([rule.desired_position(i) for i in range(n)], dtype=np.int8)
desired = np.maximum(raw, 0) if long_only else raw
```
加测试：stub rule 计数，断言恰好 n 次。

### 1.7 timeframe guard 只防了一半
**证据**：`detect_bar_seconds` 只校验"parquet 与 --timeframe 参数一致"，不校验"策略自己该跑哪个周期"。`run_matrix --timeframe` 默认 5m；S-02（注册表声明 1h）忘传参会在 5m 上**一致地**跑完不报错。
**修法**（半天）：`strategies.yml` 每个策略条目加 `timeframe` 字段；`run_matrix` 启动时校验 `--timeframe == registry[strategy].timeframe`，不一致直接 exit（而不是靠每个 lib 自觉调 guard）。

### 1.8 `_span_years` fallback 忽略 `bar_seconds`（已复验）
**证据**：`strategy/engine.py:151-163` 写死 300s；`BarFrame.bar_seconds` 只被写、从未被读。1h 策略 `time=None` 时 Sharpe 虚高 ~3.5 倍。现有测试固定 300s 所以测不出。
**修法**（30 分钟）：`_span_years` 增加 `bar_seconds` 参数并用它；加 `time=None, bar_seconds=3600` 的测试。

### 1.9 Sharpe 口径会系统性奖励过度交易（裁量项，一天内）
**证据**：`annualised_sharpe = mean(tr)/std(tr)*sqrt(n_trades/span_years)`——同样边际、60 笔/年比 1 笔/年 Sharpe 高 ~7 倍；且持仓重叠的 per-trade 收益被当独立样本。与 S-01 的结论"频率×成本不可持续"方向相反。
**修法（二选一）**：a) 主指标改为按 bar 收益序列重采样到日频算 Sharpe，现指标改名 `sharpe_trade_rate` 保留作参考；b) 暂不改代码，但在所有报告模板中加 caveat 且禁止跨策略比 Sharpe。**建议 a**，工作量约 1 天含测试。

### 1.10 `run_matrix` 部分失败仍产出"完整"总结
**证据**：单格异常被捕获后继续，只要 1/18 成功也会写 matrix.md/summary.csv，进程不一定非零退出。
**修法**（1 小时）：默认模式要求全部单元成功才写总结 + 退出码 0；否则退出码非 0，输出文件加 `PARTIAL` 标记（或干脆不写），调试模式 `--allow-partial` 显式开启。加一个注入失败单格测试。

---

## 2. P1 — trial_log 与结果可追溯（修完 P0 后，约一天）

### 2.1 trial_log 写入四个问题（已复验）
`strategy/run_matrix.py:235-236`：
- `strategy.upper()` → 写 `S01`，registry/trial_log 规范是 `S-01`；
- outcome 恒为 `<TBD>`；
- 写入时机在 Step 4（矩阵跑完即写），门禁判定（Step 6/7）之前；
- `n_tried_before = 行号 - 1`，同一策略多行时"best-of-N"分母错。
**修法**：ID 原样透传不 upper；`--trial-row` 拆成"记录运行"与"定案"两个动作（或定案时必填 `--outcome`）；`n_tried_before` 按 distinct strategy_id 计数；`results/<strategy>` 目录名保留 upper 用于路径（无碍）。

### 2.2 per-cell JSON 无数据指纹
数据重建后重跑会静默覆盖旧结果且无法区分。**修法**：每格 JSON 加 `data_fingerprint`（parquet 路径 + mtime + 行数 + 列数）。约 30 分钟。

### 2.3 results/ 被 gitignore → 注册表/报告死链
clone 后 `results/S01/matrix.md` 404，外部无法核验任何结论。**修法**：`strategy/results/*/*.md` 和 `*.csv` 加 `.gitignore` 例外（提交摘要），per-cell JSON 仍忽略。约 15 分钟。

---

## 3. P2 — 文档与一致性收尾（半天，可与 P1 并行）

1. **测试数量**：README:31 与 :217 写 61，tests/README:11 写 80，实际以 `pytest --collect-only` 为准（review4 数出 66 函数/75 case）。统一为实测数字并写死在 README。
2. **死链 `docs/legacy_full.md`**：docs/README.md:31、legacy/README.md:9、tests/test_indicators.py:22 三处引用已改名的文件 → 全部指向 `docs/repo_review_20261026.md`（或按 §4 归档后指向归档位置）。
3. **SuperTrend 门槛**：`tests/test_indicators.py:470` 断言 `agree > 0.95`，文档宣称 >99.8%。二选一：把测试提到 0.99 或把文档降到"smoke 级 95%"。**建议改文档措辞**（smoke 测试不该背 99.8% 的承诺）。
4. **PSAR 校验不一致**：`library/utils.py:30` 允许 `maximum >= 1`，`library/psar.py:36` 要求 `< 1`。统一到 `< 1`（Wilder 惯例），utils 里加注释指向 psar 为权威。
5. **文档陈旧事实**：`config/indicators.yml` 头部引用 `indicators/` 包（已改名 `library/`）和不存在的 `.legacy.bak`；SAD "last 25 cols" 实际 35；`docs/data_profile.md` 与 STRATEGY_BACKGROUND 数据事实矛盾（6.6M vs 48.6M 行）——逐条对照真实 parquet 修订。
6. **`strategies.yml` 头部**仍写"nothing loads it at runtime yet"——§1.1/§1.7 落地后即过时，改文案。
7. **依赖 pin**：`requirement.txt` 无版本约束（TA-Lib/duckdb/pandas 漂移风险）。用 `pip freeze` 生成 `requirements.lock`，README 说明用 lock 装。

---

## 4. P3 — 基础设施（P0 全部验收后再做，各约一天）

1. **最小 CI**（GitHub Actions）：`pytest` + 一个 `check_registry.py`（机检 registry 表格列数、ID 格式 `S-\d\d`、usage map 一致、trial_log 行格式）。这是把 G0–G7 从"散文门禁"变成硬约束的唯一现实路径，但不必全建——只机检**可机检**的三条，其余留散文。
2. **Gate 2 起点无关性测试**：轻量合成数据——同一序列从 t=0 与 t=100 起算，断言 `psar_*`/`st_*` 在重叠区一致（或明确文档化"WARMUP_DROP=360 不保证路径收敛"并删除 `supertrend.py` docstring 里"由全局 360 行预热消除起点差异"这句**错误**声明）。
3. **端到端验收**（review3 第 6 步，强烈建议）：选一个简单新策略（如 MA 交叉）完整走一遍 注册→实现→测试→矩阵→OOS→定案。这一步同时验证 P0/P1 所有修复真的生效，是整个闭环的唯一真实证明。**做这个之前不要再加指标**。

---

## 5. 明确不做（四份 review 一致结论，防回头）

| 不做 | 理由 |
|---|---|
| 新建 CONTRIBUTING.md / MAINTENANCE.md | docs/README 维护规则、SAD §10、library/README 已是三份等价物；防漂移靠 CI 断言不靠第四份散文 |
| Dockerfile / environment.yml | Linux 上 `pip install TA-Lib` 直接可用；用 requirements.lock 即可 |
| Walk-forward 框架 | 先有严格的一次性 OOS（P0）；策略通过样本内的数量还是 0，walk-forward 无意义 |
| 策略 DSL / AI 代理框架 / DuckDB 向量化引擎 | 策略数 <10，独立 Python 模块更易审查；瓶颈在正确性不在吞吐 |
| 大批量新增指标 | 226→305 列特征 + best-of-N 无校正的 trial_log，挖掘面已够大 |
| 真实行情 parity fixture | 合成数据已覆盖目标风险；许可/体积/维护成本不成比例 |
| `required_columns`（死代码） | 1 抽象 + 7 实现全仓库无人读——**删**，比"用起来"便宜 |
| `GROUPS[:5]` 位置切片 | 重排即静默丢列——换成显式依赖声明（约 1 小时，属 P2.5 顺手项） |
| `STRATEGY_BACKGROUND` §8 checklist | 与 WORKFLOW Step 0–7 重复——缩成一行指针 |
| `profile_check.py` naive-vs-safe join 演示 | Gate 6 单测已覆盖，降为小脚本 |

---

## 6. 执行顺序（按依赖排序，总工作量 ~6 个工作日）

```
[0.5天] 1.1 OOS until + oos 窗口 + 一次性锁        ← 先冻结数据边界
[0.5天] 1.2/1.6/1.8 引擎三修（空头成本/双调用/span）
[1天]   1.3 + 1.4 DST 修复 + 重建 parquet + S-01 回归对照
[0.5天] 1.5/1.7 guard 统一 + timeframe 绑定 + 1.10 全成功门禁
[1天]   2.1–2.3 trial_log/指纹/结果入库 + 3 文档一致性
[1天]   1.9 Sharpe 口径（可选）
[1天]   4.1 CI + check_registry.py
[1天]   4.3 新策略端到端验收（做完它，闭环才算真正跑通第二次）
```

**验收标准（全部满足才算闭环成立）**：
- `run_matrix --windows oos` 是合法命令，且同策略第二次执行被拒绝；
- 任意策略在错误 timeframe 上启动会直接失败，而不是跑完；
- 18 格矩阵出现 1 格失败时，退出码非 0 且无未标记的总结文件；
- 新策略走完整流程 ≤1 天，trial_log 无需手工改任何字段；
- 全部测试（含新增 5 个回归测试）在干净 venv 通过。
