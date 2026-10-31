> **Verification completed — 2026-10-31.** The engineering findings were
> confirmed and repaired; the proposed master plan contains material errors.
> Read [the verification and implementation decisions](repo_review_20261031_verification.md)
> and [the versioned replay](../strategy/recomputations/20261031/README.md).
> In particular, the “66.4% made money” and “646% BTC loss” interpretations are
> incorrect; §6.6's holdout-inspection proposal was rejected. Proposed owner
> decisions below remain proposals. Original reviewer text follows as evidence.

这次不是单纯增加策略：改动重点包括把 strategy_variants.py 的大量实现迁移到新的 strategy/variants.py、修改 run_matrix.py 的变体执行和 OOS pin 逻辑，以及新增回归测试和因果性测试。方向上，已经开始落实上次提出的“减少重复入口、明确变体配置、加强 OOS 保护和防止未来数据泄漏”。但我还需要核对实现细节，不能仅凭新增测试就认定这些风险已经彻底解决。
总体评价
工程质量明显提升
 仍有几个需要修复的边界问题


我认为这次 cc63ac0 是一次比较有价值的 Engineering Hardening Commit。相比 936f7b9，它在配置管理、OOS 保护、因果性测试、运行记录和数据读取效率方面都有实质进步。

但需要区分两件事：
- 工程方面： 已经明显更扎实，开始具备可重复、可审计的研究流程。
- Alpha 研究方面： 还没有实质性突破。没有新增 Feature Research、策略分类或新的 Alpha 来源研究，也没有证明当前策略找到了可持续的净 Alpha。
另外，我检查时发现一个日期边界问题，建议优先修正。

1. 上次 Review 的问题，这次解决得怎么样？
上次提出的问题	当前状态	我的评价
Variant 配置分散	已改善	统一迁移到 strategy/variants.py
Matrix Runner 不支持统一的 Variant	已改善	支持 --variant，配置解析统一
OOS 配置 Hash 不完整	已改善	现在包括完整默认参数和 RuleSpec
OOS Variant 未绑定	已修复	必须同时匹配 Variant 和 Hash
OOS 不完整矩阵	已改善	禁止 partial OOS，要求完整标的和成本矩阵
报告矩阵缺失、重复	已改善	增加统一的 grid validation
跨窗口赢利标的重复统计	已修复	分别统计窗口，并计算 distinct instruments
NaN Gate 放行问题	已改善	启用的 Gate 遇到无效输入会 fail closed
S-18 ATR 索引问题	已修复	使用上一根 Bar 对应的 ATR
First Bar 状态问题	已修复	修复 S-33、S-37、S-39 等规则
重复读取 Parquet	已改善	增加有容量限制的内存缓存
运行结果缺少环境信息	已改善	增加 manifest.yml
实验日期不准确	已改善	修正日期，并说明只能追溯到证据首次提交时间
历史策略性能结果	尚未完成	代码修复了，但受影响的历史收益尚未重新计算
OOS 绑定代码版本	仍需加强	Hash 目前没有绑定代码版本和干净工作区

相关实现：
- strategy/variants.py
- strategy/run_matrix.py
- strategy/schema.py
整体来说，上次提的工程问题大部分已经有明确的实现，不只是增加文档说明。

2. 我发现一个需要优先修复的问题：日期边界
P1 — 建议下一次优先修复
位置：
- config/strategies.yml
- strategy/oos_token.py
- strategy/strategy_lib.py
- strategy/strategy_rsi_lib.py
现在配置是：
windows:
  full:
    since: null
    until: "2025-07-31"

  last_12m:
    since: "2024-08-01"
    until: "2025-07-31"


normalize_bound() 对日期字符串的处理是：
2025-07-31
    ↓
2025-07-31T00:00:00+00:00


而普通 In-Sample 查询使用：
WHERE time <= ?


这意味着查询截止在 2025-07-31 00:00 UTC，而不是 7 月 31 日结束。

如果设计意图是把 7 月 31 日作为最后一个完整交易日，那么当前实现会漏掉这一天绝大部分数据。

还有一个容易忽略的地方：run_matrix.py 的 _data_fingerprint() 也使用了这个日期边界，所以目前数据指纹与实际错误的查询范围是一致的，却不代表它们符合预期的研究窗口。
建议怎么修
把日期和时间两种边界分开处理：
输入	建议语义
since: 2025-07-31	从 7 月 31 日 00:00 UTC 开始
In-Sample until: 2025-07-31	包含 7 月 31 日整天，实际使用 < 2025-08-01 00:00 UTC
until 为具体时间	保留精确时间边界语义
OOS until: 2026-10-23	继续使用 < 2026-10-23 00:00 UTC，不包含 23 日

不要简单地把 normalize_bound() 全局改成加一天，否则可能破坏 since 和 OOS 的原有语义。

必须补充的测试：

使用合成数据包含：
- 2025-07-31 00:00；
- 2025-07-31 12:00；
- 2025-07-31 23:55；
- 2025-08-01 00:00。
确认普通 In-Sample 查询包含前三条，不包含第四条。并且同时测试两个 Loader 和 _data_fingerprint()。

这不是 OOS 泄漏问题，但它会导致研究窗口定义和实际数据范围不一致，应该在重新计算历史策略结果之前修好。

3. OOS 保护：比之前可靠，但还有一个重要缺口
目前 config_hash() 覆盖：
- Timeframe；
- Entry Guard；
- 完整 Rule Parameters；
- 多样化策略的 RuleSpec。
这比之前使用空参数 Hash 的做法好很多。

但它没有绑定：
- 策略代码版本；
- Backtest Engine 版本；
- 特征计算代码版本；
- 是否存在未提交的代码修改。
虽然 manifest.yml 记录了 Git Commit 和 dirty 状态，但 OOS Hash 本身并没有验证这些内容。

举个例子：
1. 某个策略通过 In-Sample；
2. 你用 pin_finalist.py 生成 Hash；
3. 随后修改策略代码或 Engine；
4. 参数没变，Hash 仍然相同；
5. 新代码仍可能通过 OOS 配置检查。
这样就没有真正冻结最终提名时所使用的实现。

建议在第一次 OOS 提名前补齐：
字段	作用
oos_code_commit	冻结策略和引擎对应的 Git Commit
oos_config_hash	保留当前完整参数 Hash
oos_variant	保留当前 Variant 绑定
oos_dirty	必须为 false
oos_data_fingerprint	明确冻结最终使用的数据版本

也可以考虑将完整 Git Commit 加入最终配置 Hash。

pin_finalist.py 应打印完整冻结信息，OOS Runner 必须验证，而不是只记录在 manifest 中。

目前 Registry 没有 Finalist，OOS Ledger 也仍为空，因此还没有发生实际的错误消费。这个问题不需要为了修复而提前运行 OOS，但应当在提名之前解决。

4. 性能优化：方向正确，但还有空间
这次增加的缓存是合理的。

策略数据缓存实现

主要特点：
- 默认最大缓存 128 MB；
- LRU 管理；
- 缓存仅存在于当前执行 Scope；
- 通过文件路径、inode、大小和时间戳检测文件变化；
- 返回 Deep Copy，避免不同策略之间互相修改数据；
- 每次读取仍执行 Holdout Guard；
- OOS 数据不缓存；
- 不同 Cost Tier 仍然创建新的 Rule State，避免状态污染。
实际测试结果
Commit 的 Review 文档给出的一个 Profiling 案例：
项目	无缓存	有缓存
三个成本等级总时间	1.6531 秒	0.9884 秒
load_bars 时间	0.6446 秒	0.2921 秒

单次案例大约节省 40% 总时间，但不能直接认为所有策略都能获得相同幅度的提升。

还有一个遗漏：

S-01 RSI 仍然使用自己的 strategy_rsi_lib.load_bars()，没有使用统一的 strategy_lib 缓存。

因此，即使 run_matrix.py 外层包了 cache_bars()，S-01 的三个 Cost Tier 仍会分别读取 Parquet。

建议下一步让 S-01 也走统一 Loader，并为它增加缓存命中测试。

另外，目前缓存优化的是数据读取，并没有缓存 Signal 或 Trade Ledger。三个 Cost Tier 仍然需要重新执行策略状态和回测。这是当前合理的保守实现，不建议为了更高速度贸然复用有状态的 Rule 对象。

5. 代码精简：已经有改善，但还没有彻底统一
这次最明显的代码整理是：

scripts/strategy_variants.py 减少了约 1,157 行，原先大量 Variant 配置迁入了：

strategy/variants.py

这是正确的方向：Sweep Runner 不应该保存一套独立的策略配置。

但要注意，这次主要是配置集中管理，而不是这些配置本身被大幅简化。新的 variants.py 仍有约 1,216 行。

目前仍然存在两处策略路由：
- strategy/variants.py：策略模块映射以及 get_runner()；
- strategy/run_matrix.py：仍保留 _STRATEGIES 和部分手工注册函数。
以后增加策略，仍然可能需要修改两个不同位置。

我建议暂时不继续重构，等后续做 Taxonomy 时，再把以下信息统一为一个 Registry：
Strategy Registry
    |
    |-- strategy_id
    |-- module / runner
    |-- timeframe
    |-- default parameters
    |-- variants
    |-- alpha_source
    |-- regime
    |-- entry / exit
    |-- research status


不要再为了减少文件行数而搬来搬去。

6. 研究结果：这次审计给出了一个更准确的现状
这部分我认为是这次 Commit 很重要的收获。

新增的：
- research_audit_20261031.json
- review_verification_20261031.md
让之前的研究结论可以通过已有 CSV 和 Markdown 结果重新核对，而不需要读取市场数据。
当前策略搜索情况
指标	审计结果
已登记策略	132
Rejected	130
Parked	2
Finalist	0
Sweep 原始记录	15,480
不同结果单元	14,400
完全重复记录	1,080
Named Configurations	800
2 bps 下正向 Edge 单元	83
正向结果中交易数不超过 2 次	17

其中 S-113 至 S-132 的固定策略批次：
0 / 120 positive edge cells
也就是说，当前这一批策略在 2 bps 成本下没有一个标的/窗口单元跑赢对应的 Buy & Hold。

目前审计认为在两个重叠窗口都出现跨市场胜出的配置有：
- s55 / looser
- s109 / ema_gate
但要特别注意：
1. Full 和 Last 12m 是重叠窗口，不能算独立验证。
2. S-109 的部分胜出结果只有两到三笔交易，样本非常有限。
3. 这些结果还没有完成新的非重叠验证。
因此目前不能据此提名 Finalist。
我的看法
这里最重要的不是 83 个正向单元，而是目前只有极少数配置有跨标的的初步迹象，并且它们尚未通过独立时间验证。

下一步不能简单地继续增加 RSI、EMA、ADX、CCI 等参数变体。

应该继续按照上一次讨论的方向，做：
- Market Structure；
- Volatility Regime；
- Asymmetric Payoff；
- Statistical Alpha；
- Multi-timeframe。
但这次 Commit 没有真正实现这些方向的研究模块，只是把现有结果审计得更清楚。

另外，审计报告正确指出了一个重要原则：79.625% 的组别没有胜出且交易频率超过每年 54 次，这只是一个描述性分类，不足以证明亏损一定是交易成本造成的。仍然需要对比 Gross Return 和 Net Return。

7. 历史结果还不能直接作为当前代码的有效证据
本次修复涉及策略规则本身，所以历史性能结果需要谨慎处理。

Review 报告给出了：
- S-33 / S-37 / S-39：共比较 144 个已有配置，其中 20 个配置的早期决策发生变化；
- 修复后的状态最晚在第 9 个决策点收敛；
- S-18 的 ATR 修复可能影响整个序列；
- 缺失数据 Gate 的修复也会影响部分交易决策。
注意，状态收敛不代表最终复利收益相同。

目前旧 CSV 的收益结果没有重新计算。因此：

旧结果可以作为历史版本证据，但不能直接代表当前修复代码的表现。

建议对受影响策略重新运行，把结果输出到独立版本目录，例如：
strategy/results/recomputed_20261031/
    S18/
    S33/
    S37/
    S39/


同时保留原始结果，生成差异报告：
- 交易次数变化；
- Entry / Exit 时间变化；
- Return 变化；
- Drawdown 变化；
- 成本后 Edge 变化；
- 是否改变原来的 Rejected / Parked 结论。
不要直接覆盖旧结果，也不要在未复算之前重新提名。

8. 测试质量：有明显进步，但不要误解覆盖范围
Commit 文档报告：
Pytest
652

Checker mutation tests
38/38

Results checker failures
0

Existing warnings
22

以上是 Commit 自带 Review 文档记录的本地验证结果，并非我在当前环境重新运行的结果。

我特别认可新增的 test_rules_causality.py。

它通过扰动未来 Bar 的数据，检查过去决策是否变化。这比仅仅检查有没有 shift(-1) 好得多。

不过有两个边界：

第一，它主要测试规则层。 它不能单独证明整个 Feature Pipeline、HTF Join、所有指标计算都没有未来数据泄漏。

第二，它使用合成 FeatureFrame。 这是很好的规则回归测试，但不是对所有真实市场状态的完整验证。

另外，GitHub 的远程 Commit Status 没有返回可核验的成功状态，Review 文档也明确说这次没有运行 Remote CI。因此我不会把这次描述成远程 CI 已经全部通过。

9. 建议下一步怎么做
我不建议这时再进行大规模重构。建议按这个顺序：
优先级	下一步	原因
P1	修复 In-Sample 日期 until 边界	确保所有研究使用完整且一致的时间窗口
P1	重新计算 S-18、S-33、S-37、S-39 和受 Gate 修复影响的结果	让历史性能重新对应当前代码
P1	OOS Hash 增加代码版本和工作区状态绑定	防止参数相同但代码已经变化
P2	S-01 接入统一缓存	补齐当前缓存覆盖范围
P2	处理 1,080 条重复 Sweep 记录	减少重复实验统计和报告歧义
P2	逐步统一两个 Strategy Registry	降低后续维护成本
P2	审查剩余 22 个 Warning	确定哪些是合理提醒，哪些应该修复

完成这些之后，再开始下一阶段的 Feature Research。

10. 最终结论
我对这次 Commit 的评价是：工程方向走对了，而且比上一版成熟不少。

尤其是 Variant 统一解析、OOS 保护、Causality Regression Test、运行 Manifest 和 Data Cache，这些都是后续可靠研究所需要的基础设施。

但目前仍然有三件事比继续增加策略更加重要：
1. 把日期边界处理正确，保证实验窗口准确。
2. 把已经修复代码的历史结果重新计算，避免旧收益数字误导筛选。
3. 在任何候选策略进入 OOS 前，真正冻结代码、参数和数据版本。
至于 Alpha 本身，我的判断没有改变：目前还没有足够证据说明 Moneta 找到了稳定的可交易 Alpha。

我建议下一次不要增加 S-133、S-134。先把这次的 P1 问题修好，再进入 Feature Research 的第一轮实验。

这比继续生成几十个传统指标组合更有价值。


# moneta — Master Plan & Review (2026-10-31)

> **This is the single document.** It supersedes `docs/strategy_direction_20261031.md`
> and `docs/repo_review_20261030_followup3.md` (both folded in here). Keep it that
> way — one fact, one home.
>
> **For the AI executing this file (VS Code):** §1 reviews the latest commit.
> §3–§8 are the plan. Execute in the order of §9. **Do not run any strategy
> before §4 (the yardstick) and §5 (the protocol) are machine-enforced.**
>
> Baseline: commit `cc63ac0`, 132 registered strategies, 800 distinct
> `(strategy, variant)` configurations, 14,400 distinct cells, OOS holdout
> **never consumed** (`strategy/oos_ledger.json` = `{"version":1,"consumptions":[]}`).
>
> Authoritative evidence: `python scripts/audit_research.py` →
> `docs/research_audit_20261031.json`; independently checked in
> `docs/review_verification_20261031.md`.

---

## 0. TL;DR

| | |
|---|---|
| **1** | The engineering is in good shape. The OOS gate is correct and tested; the commit under review is the strongest yet. |
| **2** | **The failure diagnosis driving the research is wrong.** The repo blames "cost × frequency" for 79.6 % of failures. Split gross-vs-net and it is **23.4 %**. The real bucket is **66.4 % — "made money, underperformed a beta-dominated benchmark"**. |
| **3** | The fix for (2) is **not** "trade less" and **not** "find a better directional signal". It is to judge long-only strategies on **risk-adjusted** terms — and the engine already computes the two comparators needed, while **no criterion uses them**. |
| **4** | The pass bar is still satisfiable by noise: no trade-count floor, no margin floor. `s109/ema_gate` passes today while losing **−646 %** on BTC and winning EUR/XAU by **+2…+5 %**. |
| **5** | 62.5 % of the search budget went to families with **zero** wins. 16 of them are measured deeply enough to close. |
| **6** | Two axes have **never** been searched: asymmetric/market-neutral (110 of 132 strategies are long-only, against a benchmark where BTC is +1,288 % and EUR is +3 %) and position sizing (the engine fixes `UNIT_SIZE = 1.0`). |

**Corrections to my own earlier analysis are in §1.4. Read that before quoting any
number from this file.**

---

## 1. Review of `cc63ac0` — "Add regression tests for strategy variants and rules causality"

### 1.1 My four P0 items are all closed

| P0 | Status | Evidence |
|---|---|---|
| CI `if: always()` so a failing self-test can't mask the results check | ✅ | `.github/workflows/ci.yml` |
| Trial-log dates: 85 real rows were dated in the future | ✅ | 133 rows now dated `2026-10-28/29/30`; **0** future-dated |
| X5 hole: `candidate` + a `rejected` trial row passed silently | ✅ | old pattern gone |
| "Rejected combinations" table: 0 of 101 rejected strategies recorded | ✅ | **7 → 130 rows**, 0 missing; new checker X17 prevents another omission |

### 1.2 The exceptional new work

**a. `scripts/audit_research.py` — machine-readable audit.** SHA-256 per artifact,
`validate_cell_grid` on every sweep CSV, cross-file conflict detection. Its
epistemic framing is exactly right:

> *"Artifact filenames remain identifiers; they are not evidence of execution
> dates. Git introduction dates bound when evidence was recorded, not when a run
> began."*

**b. `docs/review_verification_20261031.md` — an independent verification pass**
that caught **my** error (see §1.4) and corrected the row count to 85.

**c. The scoped parquet cache** (`strategy/strategy_lib.py::cache_bars`) — better
than what I proposed:

- `ContextVar` → **thread-local**; 128 MB cap; **holdout frames bypass it**
  (`cache = ... if not _oos.is_holdout_until(until) else None`);
- **copies returned**, so a rule cannot mutate another cell's inputs;
- file identity + `mtime/ctime` invalidate entries after a data replacement;
- measured 1.6531 s → 0.9884 s on a profiled `s55/looser` cell.

**d. `strategy/variants.py` — one canonical variant registry.** `scripts/strategy_variants.py`
went **1218 → 218 lines**; the sweep and the matrix runner now resolve the same
definitions. The "two execution paths" problem is largely closed.

**e. Real causality bugs found and fixed** (none of which I had flagged):

- **first-bar wraparound** in S-33 / S-37 / S-39 (the review named S-71/S-89 —
  those were already guarded);
- **S-18 previous-bar ATR mismatch**;
- **missing-data gates failing open** — an enabled EMA gate with non-finite
  inputs used to allow entries; now fail-closed via one shared helper;
- **13 generated CLIs had indentation errors**, found by compiling every entry
  point, now repaired with `--help` smoke coverage.

**f. `validate_cell_grid`** (`strategy/schema.py`) — rejects missing,
duplicate, unexpected, errored and non-finite cells before a report can
silently drop them.

**g. Prefix-invariance causality tests** — the strongest causality check
available, applied across **all** strategy rules and to the diverse batch.

**h. `manifest.yml`** for matrix runs — resolved config + hash, bounds, data
fingerprint, source commit + dirty flag, package versions, actual UTC
timestamps. Historical manifests are explicitly **not** invented.

**i. New checks** — X16 (finalist pin), X17 (rejection-record completeness);
plus an OOS output-routing bug fixed (the CLI summary went to the original
directory while the cells went to the OOS directory).

**j. Tests 265 → 493**; checker mutation cases 37 → 38. CI green on runs 15–16.

### 1.3 What is still open

| Item | Status |
|---|---|
| **Pass-criteria floors** (`min_trades` / `min_exposure_pct` / `min_edge_pct`) | ❌ **not implemented** — `config/strategies.yml` and `strategy/schema.py` have zero occurrences |
| **Gross-vs-net decomposition** as a first-class measurement | ❌ not in the audit; the verification doc *asks* for it ("compare gross and net performance to establish that") — see §3.3, this is now answered |
| `class` column in the registry | ❌ absent |
| Pre-registration ledger (`config/strategy_plan.yml`) | ❌ absent — "registered before run" is still a human convention |
| Closed-family guard | ❌ absent — a closed family can still take new IDs |
| `buyhold_sharpe_weekly` / `buyhold_max_drawdown_pct` used by any criterion | ❌ **computed but never used** |

### 1.4 Corrections to my earlier analysis (and to the reviews that preceded me)

The repository's own verification pass found the error independently. Both are
now fixed in this file.

| Claim | Was | Is | Cause |
|---|---|---|---|
| `s109/ema_gate` is a "one-trade" win | yes | **no** — `ema_gate` has 17–94 trades; the one-trade config is the `wide_exit` variant | I conflated two variants of the same family. `docs/review_verification_20261031.md` caught it. |
| Sweep configurations | 720 | **800** | — |
| Distinct 2 bps cells | 4,080 | **4,800** (14,400 across all three cost tiers) | — |
| `(strategy, variant, window)` groups | 1,360 | **1,600** | `iterations_2026-11-04.csv` stores `n_trades` as `'1544.0'`; `int()` raises and **silently drops 720 rows**. Use `float()`. |
| Failure buckets | 1084 / 189 / 62 / 15 / 10 | **1274 / 239 / 62 / 15 / 10** | same parsing bug |
| Zero-win families' share of the budget | 792 groups (58.2 %) | **1,000 groups (62.5 %)** | same |
| Deeply-measured closed families | 13 (42.9 %) | **16 (50.2 %)** | same |
| Future-dated trial rows | 86 | **85** real rows (86 counted the HTML-comment example row) | — |
| `hv` hit rate | 22.9 % (48 groups) | **17.2 % (64 groups)** | same |
| Saturated families (X15) | 6 families, max size 5 | **12 families, max size 7** | My group→family mapping was incomplete. The repo's `docs/repo_review_20261030_followup_verification.md` found this; the implemented X15 guard reports the true count (12 warnings, 0 failures) rather than my stated 6. |

**The repo's audit is authoritative.** Where this file and
`docs/research_audit_20261031.json` disagree, the audit wins.

---

## 2. The failure diagnosis — and why it matters more than anything else here

### 2.1 The repo's current taxonomy

Over all 1,600 `(strategy, variant, window)` groups at 2 bps:

| Failure mode | Count | Share |
|---|---:|---:|
| **Cost × frequency** (`trades_per_year > 54`) | 1,274 | **79.6 %** |
| Signal quality (low frequency, still loses) | 239 | 14.9 % |
| BTC-only (beats buy-hold on 1 instrument) | 62 | 3.9 % |
| Empty signal (0 trades) | 15 | 0.9 % |
| **Pass (≥ 2 instruments)** | **10** | **0.6 %** |

### 2.2 Splitting the loss by *gross* performance — the decisive test

The sweep already runs 0 / 2 / 5 bps, so gross performance is **already in the
committed data**. Comparing the 0 bps cell with the 2 bps cell separates "the
signal had no edge" from "costs ate the edge":

| Bucket | Count | Share of all 1,600 groups |
|---|---:|---:|
| **E. Made money, but underperformed buy-hold** | **1,062** | **66.4 %** |
| **D. Cost-killed** (beat buy-hold gross @0 bps, lost @2 bps) | **374** | **23.4 %** |
| F. Lost money outright | 77 | 4.8 % |
| B. Beat buy-hold on 1 instrument | 62 | 3.9 % |
| C. Empty signal | 15 | 0.9 % |
| A. Pass (≥ 2 instruments) | 10 | 0.6 % |

### 2.3 What this changes

**The repo's headline diagnosis is wrong by roughly two thirds.**

- Only **374 of the 1,294** frequency-blamed groups (29 %) actually had an
  edge that costs destroyed. For those, "trade less" is the right fix.
- **1,062 groups (66.4 %)** made money and simply lost to the benchmark.
- Only **77 groups (4.8 %)** were genuinely bad.

**And the benchmark is the reason.** On this sample buy-hold is
`BTC +1,288 % / EUR +3 % / XAU +113 %`. A long-only rule that returns a modest
positive number is *by construction* behind the benchmark. Judging it on raw
return calls that a failure — but it may be a perfectly good, lower-drawdown
strategy.

**This is the misdiagnosis that has been steering the search for 132
strategies.** The narrative "cost × frequency" implies the fix is *trade less*,
and classes C and D were built on exactly that premise ("low-frequency,
regime-conditioned"). But **66 % of the failures were never a frequency
problem.** Chasing lower frequency on a signal with no edge produces a
lower-frequency signal with no edge — which is what the data shows: the
fewest-trade variants are among the worst (`S-21` 1 h ≈ 15/yr → −253 %,
`S-25` 1 h ≈ 19/yr → −254 %).

### 2.4 The honest caveat — a risk-adjusted bar does **not** manufacture candidates

Applying a risk-adjusted criterion to the fixed `S-113…S-132` batch:

| Criterion | Cells passing (of 120 @2 bps) |
|---|---:|
| raw return > buy-hold | **0** (0.0 %) |
| weekly Sharpe > buy-hold | 1 (0.8 %) |
| max drawdown < buy-hold | 39 (32.5 %) — but a strategy that never trades trivially wins this |
| **combined**: `ret > 0` AND `sharpe_weekly > BH` AND `maxDD ≤ 0.75 × BH maxDD` | **1** (0.8 %) — `S-124` EUR_USD `last_12m`: ret +1.3 vs BH +5.62, Sharpe 0.58 vs 0.56, maxDD 1.60 vs 9.17 |

So the recommendation is **not** "switch the bar and the winners appear". It is:

> **Stop mis-diagnosing the failures.** The wrong diagnosis has been sending the
> search toward the wrong fix for 132 strategies. Measure gross vs net, and
> judge long-only strategies on risk-adjusted terms — then the *diagnosis* is
> right, and the remaining decisions (which classes, which budget) follow from
> correct premises.

---

## 3. The strategy taxonomy

### 3.1 Per-family map

Family key = the registry's *Key indicators* column with the window suffix
stripped (`willr_60` → `willr`, `macd_hist_6_24` → `macd_hist`,
`st_dir_24_3` → `st_dir`).

Both numerator and denominator are **groups** — counting cells in the
denominator while counting groups in the numerator inflates every rate by 3×.

| Family | Groups | Real-win groups | Rate | Verdict |
|---|---:|---:|---:|---|
| `bb_width` | 16 | 6 | **37.5 %** | live, thin evidence (16 groups) |
| `chop` | 16 | 5 | **31.2 %** | live, thin evidence (16 groups) |
| `adx` | 28 | 8 | **28.6 %** | **live** |
| `dow_sin` | 32 | 9 | **28.1 %** | suspicious → placebo test (§6.3) |
| `h1_rsi` | 16 | 4 | **25.0 %** | live — S-55's family |
| `hv` | 64 | 11 | **17.2 %** | **live** (best-measured live family) |
| `macd` | 32 | 4 | 12.5 % | marginal |
| `bb_pctb` | 44 | 3 | 6.8 % | marginal |
| `atr_pct` | 32 | 2 | 6.2 % | marginal |
| `h1_ema_dist` | 16 | 1 | 6.2 % | thin |
| `ema` | 56 | 2 | 3.6 % | dead |
| `dc_pos`, `rsi` | 32 each | 1 each | 3.1 % | dead |
| `willr`, `stoch_d` | 60 each | 1 each | 1.7 % | dead |
| `atr` | 64 | 1 | 1.6 % | dead |
| **39 zero-win families** | **1,000** | **0** | **0.0 %** | **provably dead — 62.5 % of the budget** |

**Note the two axes.** A high rate over few groups (`bb_width`, `chop`,
`h1_rsi` — 16 groups each) is *suggestive*, not established. A low rate over
many groups (`atr` 64 groups → 1 win) is *established dead*. §5.6 closes on
**both** criteria.

### 3.2 The classes

Classify by **the economic claim the strategy makes**, not by indicator name.
The evidence shows indicator name predicts nothing; claim type predicts a lot.

| Class | Economic claim | Representative families | Evidence | Status |
|---|---|---|---|---|
| **A** | Directional trend — price has momentum | `st_dir`, `aroon`, `macd`, `ema_spread`, `psar`, `roc`, `dmi` | 0–3.6 % | **retired** |
| **B** | Directional mean-reversion — price overshoots | `rsi`, `cci`, `willr`, `stoch_k/d`, `bb_pctb` | 1.7–6.8 % | **retired** |
| **C** | Volatility state — vol expansion precedes continuation | `hv`, `bb_width`, `atr_pct`, `sqz_on` | `hv` 17.2 % (11 real, 64 groups) | **open** |
| **D** | Trend-strength regime — trade only when trending | `adx`, `chop` | `adx` 28.6 % (8 real) | **open** |
| **E** | Calendar / session — intraday or weekly effect | `dow_sin`, `hour_sin` | `dow_sin` 28.1 % (9 real) | **open, placebo first** |
| **F** | Volume / flow — volume leads price | `mfi`, `cmf`, `vol_rel`, `vwap` | 0 % | **retired** |
| **G** | Candle structure — wick / CLV patterns predict | `bar_clv`, wick ratios | 0 % | **retired** |
| **H** | Multi-factor + HTF gate — direction confirmed by the 1h | `S-113…S-132` | **0 / 120** | **retired** |
| **I** | **Asymmetric / market-neutral** — the *spread* between instruments | — | **never searched** | **new axis** |
| **J** | **Position sizing / risk overlay** — the edge is *how much* to hold | — | **not implementable today** | **new axis** |

### 3.3 Two structural findings

**Finding 1 — every surviving family is a *state* family, not a *direction*
family.** `hv`, `adx`, `chop`, `bb_width`, `h1_rsi` answer *"when is a trend
likely to persist?"*. **None answers "which way?"** Classes A and B — where 132
strategies went — are exactly the two that fail.

**Finding 2 — the benchmark is the problem.** 110 of 132 strategies are
long-only, and the benchmark is `BTC +1,288 % / EUR +3 %`. Every "winner" so far
(`S-06`, `S-18`, `S-35`, `S-36`, `S-45`, `S-55`, `S-88`, `s109/ema_gate`) is
BTC-only or degenerate. **A large part of the "no edge" conclusion is a
benchmark-composition artifact.** This is why class I exists, and why §4.2
proposes a risk-adjusted bar.

### 3.4 The decisive experiment: multi-factor ≠ multi-direction

`S-113…S-132` are the **cleanest experiment in the repo** — one fixed rule per
strategy, no variant sweep, therefore no selection bias.

> **0 winning cells out of 120 at 2 bps.** Median trade count 1,624; `S-127`
> ran 4,834 trades.

Diversity of *indicator combination* is not diversity of *hypothesis*. Class H
must be retired; classes I and J are where new diversity has to come from.

---

## 4. The yardstick — the single source of truth

**This section is normative.** Direction files, the runner, the checker and the
preregistration ledger all use it. Nothing else may restate it.

### 4.1 The noise problem (two distinct holes)

**Hole A — no trade-count floor.** `oos.pass_criteria` has a **ceiling**
(`max_trades_per_year: 54`) and **no floor**. A strategy that trades *once* in
5.5 years is trivially ≈ buy-hold and "beats" it by a rounding error.

**Hole B — no margin floor.** A config can clear "≥ 2 instruments, both
windows" while losing catastrophically on one of them.

Measured across all 83 winning cells: **17 (20 %) come from ≤ 2-trade
strategies**, and 9 of those have an edge < 1 %.

**Hole A — the correct examples** (17 cells; the family looks like this):

| Config | Instrument | Window | Edge | Trades | Exposure |
|---|---|---|---:|---:|---:|
| `s103 / wide_exit` | EUR_USD | full | +0.23 | **1** | 99.99 % |
| `s103 / wide_exit` | EUR_USD | last_12m | +0.24 | **1** | 99.87 % |
| `s103 / wide_exit` | BTC_USD | last_12m | +4.70 | **1** | 99.75 % |
| `s96 / 1h` | BTC_USD | full | +3.67 | **1** | 100 % |
| `s109 / looser` | XAU_USD | last_12m | +0.15 | **1** | 99.95 % |
| `s35 / base` | BTC_USD | last_12m | +0.53 | **2** | 99.98 % |
| `s35 / ema_gate` | BTC_USD | last_12m | +41.96 | **2** | 99.07 % |

**Hole B — the correct example: `s109 / ema_gate`.** One of only two
configurations in 1,600 groups that clears the bar, and it clears it like this:

| Instrument | Window | Edge | Trades |
|---|---|---:|---:|
| BTC_USD | full | **−646.19 %** | 94 |
| BTC_USD | last_12m | **−21.62 %** | 9 |
| EUR_USD | full | +4.03 | 17 |
| EUR_USD | last_12m | +3.81 | 3 |
| XAU_USD | full | +5.38 | 20 |
| XAU_USD | last_12m | +2.02 | 2 |

It "wins" EUR and XAU by **+2 % to +5.4 %** while losing **646 %** on BTC.

**S-55's margins are thin at one cell too:** `XAU last_12m` **+0.57 % on 4
trades**. Only `BTC full +246.74 %` has real margin.

### 4.2 The corrected criteria (proposed — needs owner sign-off, §8)

```yaml
    # --- floors (close the degenerate-win holes) ---
    # A strategy cannot "beat" buy-hold by barely trading, nor by a rounding
    # error. The ceiling above stops cost x frequency; these floors stop a
    # one-trade strategy from matching buy-hold by rounding error, and stop a
    # config that loses -646 % on one instrument from passing on two near-ties.
    # Evidence: 17 of 83 winning cells (20 %) came from <= 2-trade strategies
    # (s103/wide_exit: 1 trade, 99.75 % exposure, +4.70/+0.24/+0.23);
    # s109/ema_gate wins EUR/XAU by +2..+5 % while losing -646 % on BTC.
    min_trades: 10                # enough trades for the edge to mean anything
    min_exposure_pct: 20         # enough time in the market to be a strategy
    min_edge_pct: 5.0            # a margin that is not a rounding error

    # --- risk-adjusted comparator ---
    # The engine already computes buyhold_sharpe_weekly and
    # buyhold_max_drawdown_pct (commit 4b8ab26) but NO criterion used them.
    # 66.4 % of all failing groups made money and merely underperformed a
    # benchmark dominated by one instrument's beta (BTC +1,288 % vs EUR +3 %).
    # For those, the honest question is not "did you beat the return?" but
    # "did you keep the return and cut the drawdown?".
    # NOTE the `ret > 0` floor: without it, a strategy that never trades wins
    # the drawdown comparison trivially.
    risk_adjusted:
      require_positive_return: true
      min_sharpe_weekly_ratio: 1.0   # strategy sharpe_weekly >= buyhold_sharpe_weekly
      max_drawdown_ratio: 0.75       # strategy maxDD <= 0.75 x buyhold maxDD
```

### 4.3 Gross-vs-net as a first-class measurement

The `scripts/audit_research.py` audit should publish the §2.2 split
(gross-0 bps vs net-2 bps) for every group, so that "cost × frequency" is
never again an *inference from a threshold* but a *measurement*. The data is
already there — the sweep runs 0/2/5 bps.

Add to the audit output, per group:

```
gross_edge_pct        # edge at 0 bps
net_edge_pct          # edge at 2 bps
cost_attributable     # gross_edge > 0 and net_edge <= 0
diagnosis             # "cost-killed" | "beta-relative" | "no-edge" | "empty" | "pass"
```

This is the single highest-value change in the plan: it turns the repo's
central claim from an assumption into a fact, and it directly answers the
critique in `docs/review_verification_20261031.md`.

### 4.4 Where the criteria live in code

`strategy/schema.py::oos_pass_fields(rows, min_instruments, max_trades_per_year)`
is **already** the shared definition used by both the runner and
`check_results.py` (X13). The floors and the risk-adjusted comparator must be
added **there**, so that:

- the in-sample bar (WORKFLOW Step 6) and the OOS bar use **one** definition;
- the checker re-computes the verdict from committed cells with the same code
  the runner used;
- the floors apply to **committed in-sample results** too, which retroactively
  re-labels `s103/wide_exit` and weakens `S-55` — that is the point.

### 4.5 Expected re-evaluation once the floors land

| Config | Before | After (expected) |
|---|---|---|
| `s103 / wide_exit` | "passes both windows" | **fails** — 1 trade < `min_trades: 10` |
| `s109 / ema_gate` | "passes both windows" | **fails** — wins are +2…+5 % < `min_edge_pct: 5.0` on 2 of 4 cells |
| `S-55 / looser` | in-sample finalist candidate | **much weaker** — `XAU last_12m` +0.57 % on 4 trades fails both floors; only `BTC full +246.74 %` survives |

**Verified against the current code** (the floors are absent, so all three
still pass):

```
s109/ema_gate    instruments_beating=2  pass=True
s103/wide_exit   instruments_beating=2  pass=True
s55/looser       instruments_beating=2  pass=True
```

---

## 5. The research protocol

### 5.1 Pre-registration (machine-enforced)

**Nothing may be executed that is not pre-registered.** Today there is no
`registered_at`, no `pre.regist*` and no "registered before the run" check
anywhere in the code.

`config/strategy_plan.yml`:

```yaml
version: 1

# --- the preregistration ledger (APPEND-ONLY) ---
# The checker refuses to run a strategy that has no entry here, and refuses an
# entry whose registered_at is later than the run date (a strategy "registered"
# after it was already run is a protocol violation, not a bookkeeping detail).
preregistrations:
  - id: S-133
    class: C                       # A..J, from §3.2
    registered_at: "2026-10-31"    # the date the hypothesis was fixed, BEFORE any run
    hypothesis: >-
      Long only while hv_120 is in its lowest decile AND close > ema_120;
      exit when hv_120 leaves the decile.
    expected_trade_band: [8, 60]   # trades/yr expected on the primary instrument
    direction: "docs/plan/directions/C_volatility_state.md"
    status: OPEN                   # OPEN | CLOSED | BLOCKED
```

**Enforcement to add to `scripts/check_results.py`:**

- a strategy with a committed results directory must have a `preregistrations`
  entry → else **FAIL**;
- `registered_at` ≤ the trial-log date of its run → else **FAIL**;
- `class` must be a known class → else **FAIL**;
- a `CLOSED` entry may not be executed again → else **FAIL**.

### 5.2 Per-class budget

Each direction has a **hard cap** on how many hypotheses it may register,
enforced by counting `preregistrations` entries with that `class`.

Rationale: 132 strategies and 800 configurations produced **two** defensible
candidates, one of them degenerate. Without a cap, a direction becomes an
unbounded sink — the mechanism that produced 62.5 % waste.

### 5.3 Cadence — a mandatory analysis gate between batches

**All eight batches so far ran in a single session on 2026-10-30.** The
filenames (`iterations_2026-10-30` … `2026-11-07`) are mechanically incremented
labels, not real dates. There was **no analysis gate between batches**: batch
N+1 started immediately after batch N.

**New rule:** a batch may start only when the previous batch has a written
analysis that states, for each open class:

1. the per-family hit rate measured on that batch;
2. which families were **closed** as a result (appended to `closed_families`);
3. the gross-vs-net diagnosis (§4.3) for the batch;
4. what the next batch will test, and why.

**No batch may exceed the remaining budget of its class.**

### 5.4 One pre-registered rule beats an 8-variant sweep

The 8-variant sweep buys 8 *correlated* configurations per hypothesis. The same
budget spent on 8 **distinct** hypotheses buys 8× the evidence.

- **Prefer:** one pre-registered rule, evaluated as-is.
- **Acceptable:** a variant sweep only when the variants are *materially*
  different mechanisms (e.g. `onset_only` vs `hold_through`), not threshold
  retunes — and the primary variant is registered **before** the run.

The `S-109` report already does this correctly for `S-113…S-132` ("Fixed rule;
selected config/variant: … treat its performance as selection-biased"). Make it
the default.

### 5.5 Stop rules

A class is **closed** when either its hypothesis budget is exhausted without a
candidate passing §4, or its measured per-family hit rate is 0 % over ≥ 100
groups (→ `closed_families`). A class is **BLOCKED** when it needs an owner
decision (class I needs a new benchmark; class J needs an engine change).

### 5.6 Closed families (an *additional* guard, keyed on measured deadness)

> **X15 already exists** (family *size*, WARN ≥ 4 / FAIL ≥ 8 — implemented in
> `scripts/check_results.py::check_saturation`, currently reporting **12
> warnings, 0 failures**). It stops a family from growing.
> **This section proposes a different guard**, keyed on **measured deadness**:
> a family that was measured deeply enough and produced *no* real win at all.
> The two are complementary: X15 stops growth by size; this one stops growth by
> *evidence*.

`config/strategy_plan.yml → closed_families`. **Closure rule (both criteria):**
`groups >= 30` **and** `real_win_rate <= 0.05`. The first is a depth
requirement — 16 groups and no wins is *unmeasured*, not dead. The second is the
result. **16 families qualify, holding 804 of 1,600 groups = 50.2 %** of the
search budget.

```yaml
closed_families:
  - {family: "roc",        timeframe: "5m", groups: 80, real_win_rate: 0.000, closed_at: "2026-10-31"}
  - {family: "mfi",        timeframe: "5m", groups: 76, real_win_rate: 0.000, closed_at: "2026-10-31"}
  - {family: "atr",        timeframe: "5m", groups: 64, real_win_rate: 0.016, closed_at: "2026-10-31"}
  - {family: "willr",      timeframe: "5m", groups: 60, real_win_rate: 0.017, closed_at: "2026-10-31"}
  - {family: "stoch_d",    timeframe: "5m", groups: 60, real_win_rate: 0.017, closed_at: "2026-10-31"}
  - {family: "aroon_down", timeframe: "5m", groups: 60, real_win_rate: 0.000, closed_at: "2026-10-31"}
  - {family: "st_dir",     timeframe: "5m", groups: 60, real_win_rate: 0.000, closed_at: "2026-10-31"}
  - {family: "ema",        timeframe: "5m", groups: 56, real_win_rate: 0.036, closed_at: "2026-10-31"}
  - {family: "close",      timeframe: "5m", groups: 48, real_win_rate: 0.000, closed_at: "2026-10-31"}
  - {family: "stoch_k",    timeframe: "5m", groups: 48, real_win_rate: 0.000, closed_at: "2026-10-31"}
  - {family: "bar_clv",    timeframe: "5m", groups: 32, real_win_rate: 0.000, closed_at: "2026-10-31"}
  - {family: "dc_pos",     timeframe: "5m", groups: 32, real_win_rate: 0.031, closed_at: "2026-10-31"}
  - {family: "h1_adx",     timeframe: "5m", groups: 32, real_win_rate: 0.000, closed_at: "2026-10-31"}
  - {family: "bb_upper",   timeframe: "5m", groups: 32, real_win_rate: 0.000, closed_at: "2026-10-31"}
  - {family: "rsi",        timeframe: "5m", groups: 32, real_win_rate: 0.031, closed_at: "2026-10-31"}
  - {family: "er",         timeframe: "5m", groups: 32, real_win_rate: 0.000, closed_at: "2026-10-31"}
```

> `hv` (64 groups, 17.2 %) and `bb_pctb` (44 groups, 6.8 %) are **above** the
> 5 % bar and are therefore **not** closed — they are the live families.
> Re-derive this list with §10.4 rather than trusting the block.

### 5.7 Parallelism — an implementation detail, and a trap

**Compute is not the bottleneck.** One batch = 2,160 cells, 12 workers,
~1,232 s ≈ 21 min; all eight batches ≈ 2–3 h wall time.

**Parallelism in a search problem is not free.** It multiplies the number of
hypotheses tested, which multiplies the number of *chance* winners. Running 10×
more hypotheses in parallel makes the selection-bias problem **10× worse**.

> **Parallelism may only be increased after §5.1–§5.5 are machine-enforced.**

**The legitimate space-for-time trade is memory for I/O** — and it is now
already implemented (§1.2c). The honest payoff was ~40 % on one profiled cell;
**it is a rounding-error optimisation next to releasing the 50.2 % dead
budget.**

**The real lever is the budget, not the CPU.**

---

## 6. The direction files

### 6.1 Template

```markdown
# Class <X> — <name>

## Hypothesis
<the economic claim, in one paragraph>

## Why it is worth trying
<measured evidence: family hit rates, gross-vs-net split, cell counts>

## How it could be falsified
<the explicit condition under which this class is dead>

## Budget
Maximum <N> hypotheses (enforced against `preregistrations` entries with class <X>)

## Criteria
REFER TO §4 of this file — do not restate the bar here.

## Preregistration
Hypotheses live in `config/strategy_plan.yml` (class: <X>). This file does not
list them.

## Status
OPEN / CLOSED (date) / BLOCKED (awaiting owner decision — see §8)
```

### 6.2 The five directions

| File | Class | Hypothesis | Evidence | Falsified when | Budget |
|---|---|---|---|---|---|
| `C_volatility_state.md` | C | Volatility expansion precedes continuation | `hv` 17.2 % (11 real, 64 groups), `bb_width` 37.5 % (6 real) | 20 hypotheses with no candidate passing §4 | 20 |
| `D_trend_strength_regime.md` | D | Only trade when the market is trending | `adx` 28.6 % (8 real, 28 groups), `chop` 31.2 % (5 real) | 20 hypotheses with no candidate passing §4 | 20 |
| `E_calendar_session.md` | E | Intraday / weekly effects exist | `dow_sin` 28.1 % (9 real, 32 groups), **0 degenerate wins** | the placebo test (§6.3) fails | 10 (incl. placebo) |
| `I_asymmetric_neutral.md` | I | The *spread* between instruments, not the direction | never searched; 110/132 strategies are long-only against a BTC-dominated benchmark | 20 hypotheses with no candidate passing §4 | 20 |
| `J_position_sizing.md` | J | The edge is *how much* to hold, not *when* | engine fixes `UNIT_SIZE = 1.0`; no sizing exists | 20 hypotheses with no candidate passing §4 | 20 |

### 6.3 The calendar placebo test (before trusting `dow_sin`)

`dow_sin` shows a 28.1 % real-win rate with **zero** degenerate wins — either a
genuine session effect (well documented in FX) or a fitting artifact.

**The cheap discriminator:** re-run the same rule on a **shifted calendar** —
use `dow_sin` of bar *t−1*, or permute the weekday labels. A real calendar
effect stays attached to the calendar; an artifact moves.

### 6.4 Asymmetric / market-neutral (class I)

The engine already supports shorts (`long_only=False`), but only **22 of 132**
strategies use them, and the long-only benchmark is `BTC +1,288 % / EUR +3 %`.
The natural experiment: **long the instrument with the stronger relative
regime, short the weaker** — a cross-sectional spread that removes the BTC beta
domination from the benchmark.

This attacks the failure mode that produced every "winner" so far. It needs
**no new features** — only a different comparison baseline than the current
per-instrument buy-hold. That baseline change is an owner decision (§8, D-4).

### 6.5 Position sizing (class J)

`strategy/engine.py` fixes `UNIT_SIZE = 1.0`. There is **no position sizing at
all**. Volatility-targeted sizing (size ∝ 1/ATR) is the classic way to convert a
raw-return edge into a risk-adjusted one — and it is exactly what §4.2's
risk-adjusted criterion would reward.

This requires the **only** engine change worth making: a per-bar size instead of
a fixed one, behind a flag, with a test proving that a constant-size run is
bit-identical to today's.

### 6.6 Before any OOS run: is the holdout an *informative* arbiter?

> **Read-only analysis.** It must not run a strategy on the holdout and must
> not write to `strategy/oos_ledger.json`.

**The question.** S-55 is the strongest in-sample candidate (98 % net long,
~11 trades/yr) and the holdout is a one-shot resource. The holdout window is
2025-08-01 → 2026-10-22, immediately after a period in which BTC's buy-hold
returned **+1,288 %** (full) and **+82 %** (last 12 m). **If BTC is strongly
bullish again inside the holdout, a 98 %-long BTC-heavy rule will "beat
buy-hold" there for pure beta reasons** — reproducing the `S-06` / `S-45` /
`S-88` trap at the most expensive possible moment: burning the one-shot
holdout to confirm a false positive.

**The measurement** — buy-hold baseline only, no strategy, over the holdout
window:

```sql
-- per instrument, time >= '2025-08-01' AND time < '2026-10-23'
SELECT instrument, count(*) AS n_bars, min(time) AS t0, max(time) AS t1,
       arg_min(open, time) AS p0, arg_max(close, time) AS p1
FROM read_parquet('data/ohlcv_5m_features/ohlcv_5m_features.parquet')
WHERE time >= '2025-08-01' AND time < '2026-10-23'
GROUP BY instrument;
```

Buy-hold return % = `p1 / p0 * 100 − 100`. Then apply the same two formulas
the engine uses (`sharpe_weekly`, `max_drawdown_pct`) to the buy-hold equity
curve `close / open[0]` — the engine already exposes them as
`buyhold_sharpe_weekly` and `buyhold_max_drawdown_pct`.

**The decision rule:**

| Holdout buy-hold picture | Meaning | Action |
|---|---|---|
| BTC strongly bullish again (e.g. > +50 % over the window) | Another BTC-bull stretch ⇒ a 98 %-long rule passes for **beta**, not skill | **Do NOT promote S-55.** Report and stop (D-5). |
| BTC flat / mixed, XAU and EUR mixed | A *balanced* test ⇒ S-55's edge would have to come from timing | A human may promote it to `finalist`; the one-shot OOS then proceeds under the existing gates. |
| BTC sharply negative | A real test, but a 98 %-long rule will very likely fail it | A human may still promote it (the OOS is a test, not a formality); be aware the prior is poor. |

Whatever is measured, **write the numbers into the final message** and state
which branch applies. Do **not** change `oos.pass_criteria` on your own — if a
risk-adjusted criterion should be added, **propose the exact YAML** and let the
owner sign it off (D-2).

**Also state, for the record:** the number of distinct cells scanned, the
number of configs clearing each bar (**1** config on the both-windows bar,
**62** on the single-instrument bar), and that the OOS ledger was empty before
and after the analysis.

---

## 7. Infrastructure work-list

> Most of §1's items are already done. This is the **remaining** work.

| # | Item | Severity | Why now |
|---|---|---|---|
| **A.1** | **Pass-criteria floors + risk-adjusted comparator** in `strategy/schema.py` and `config/strategies.yml` (§4.2) | 🔴 P0 | Until the bar cannot be met by a one-trade strategy, "which candidate is best" is not a meaningful question |
| **A.2** | **Gross-vs-net split in `audit_research.py`** (§4.3) | 🔴 P0 | Turns "cost × frequency" from an inference into a measurement; answers the verification doc's critique |
| **A.3** | **`class` column in `STRATEGY_REGISTRY.md`** + tags for all 132 rows | 🔴 P0 | The taxonomy is the precondition for the closed-family guard. (X15 size-based saturation already exists; this adds the class axis.) |
| **A.4** | **Pre-registration ledger + enforcement** (§5.1) | 🔴 P0 | "Registered before run" is currently a human convention |
| **A.5** | **Closed-family guard** (§5.6) | 🔴 P0 | Releases 50.2 % of the search budget |
| **A.6** | Per-class budget enforcement (§5.2) | 🟡 P1 | Stops a direction becoming an unbounded sink |
| **A.7** | Batch analysis gate in the protocol (§5.3) | 🟡 P1 | The cadence that produced 62.5 % waste |
| **A.8** | Generic test: a rule's **entry condition must be reachable** | 🟡 P1 | `S-03`'s "never co-occurs" failure passed every structural test; only real data revealed it |
| **A.9** | 20 × 16-line adapter libs → one generic CLI + a registry entry | ⚡ efficiency | 320 lines of boilerplate |
| **A.10** | 112 bespoke `strategy_*_lib.py` → expressible as `RuleSpec` | ⚡ efficiency | The declarative engine already expresses most of them |
| **A.11** | 132 per-strategy report files → generated from one template | ✂️ simplify | The sweep report already holds the numbers |

---

## 8. Owner decision log (`docs/plan/decisions.md`)

Append-only: date, decision, rationale, owner, what it unblocks.

| # | date | decision | rationale | owner | unblocks |
|---|---|---|---|---|---|
| D-1 | 2026-10-31 | Add `min_trades` / `min_exposure_pct` / `min_edge_pct` to `oos.pass_criteria` | 20 % of all wins came from ≤ 2-trade strategies; `s103/wide_exit` passes on 1 trade, `s109/ema_gate` passes while losing −646 % on BTC | ttrrei | §4.2, S-55 re-evaluation |
| D-2 | 2026-10-31 | Adopt the risk-adjusted comparator (`sharpe_weekly` vs BH, `maxDD` ≤ 0.75× BH, `ret > 0`) | 66.4 % of all failing groups made money and merely underperformed a benchmark dominated by one instrument's beta; the engine computes both comparators and no criterion used them | ttrrei | classes C/D |
| D-3 | 2026-10-31 | Close 16 families (groups ≥ 30 AND real-win rate ≤ 5 %) | 50.2 % of the 1,600-group search budget | ttrrei | new-family registration |
| D-4 | 2026-10-31 | *(pending)* Define the class-I benchmark (cross-sectional, not per-instrument buy-hold) | 110/132 strategies are long-only against a BTC-dominated benchmark | ttrrei | class I |
| D-5 | 2026-10-31 | *(pending)* Whether to promote S-55 to `finalist` after D-1/D-2 land | S-55's margins are +0.57 % (4 trades) and +246.74 % | ttrrei | the one-shot OOS |

**Open decisions block work** — they are listed at the top of `decisions.md`
with their status, so the next session does not re-derive them.

---

## 9. Execution order

| Step | Deliverable | Gate before the next step |
|---|---|---|
| **1** | `docs/plan/README.md` — entry point, read-order map, precedence rules, status board | — |
| **2** | `docs/plan/02_taxonomy.md` — §3 + §4 of this file, expanded | the yardstick is stated once, here |
| **3** | `config/strategy_plan.yml` — schema + the 16 closed families + an empty prereg ledger | `check_results.py` parses it |
| **4** | `docs/plan/01_research_protocol.md` — §5 | — |
| **5** | `docs/plan/00_infrastructure.md` — §7 | — |
| **6** | `docs/plan/directions/*.md` — 5 files, §6 template | each references §4, none restates it |
| **7** | `docs/plan/decisions.md` — log + the 5 decisions of §8 | — |
| **8** | **A.2** — gross-vs-net in `audit_research.py` | the audit publishes the §2.2 split |
| **9** | **A.1** — pass-criteria floors + risk-adjusted comparator | S-55 / `s109/ema_gate` / `s103/wide_exit` re-evaluated |
| **10** | **A.3 + A.4** — `class` column, preregistration enforcement | a strategy with no prereg entry is refused |
| **11** | **A.5** — closed-family guard | a new ID in a closed family is refused |
| **12** | First new batch — **class I only**, under the new protocol | a written analysis gate (§5.3) before any batch after it |

**Precedence when sources disagree** (put this in `docs/plan/README.md`):

1. `config/*.yml` (machine-readable) → 2. `config/strategy_plan.yml` →
3. `docs/plan/02_taxonomy.md` → 4. `docs/plan/directions/*.md` →
5. registry + trial log → 6. sweep reports.
*Exception:* if the **code** and `config/` disagree, the code is wrong. A
code-vs-`docs/plan/` disagreement is resolved by the table (a doc records the
decision; the code may simply not have been updated).

**Explicitly out of scope for all twelve steps:** consuming the OOS holdout,
adding strategies to classes A/B/F/G/H, and the deferred items (walk-forward
harness, dedup engine, vectorised engine, YAML strategy schema).

---

## 10. Appendix — reproducing every number

### 10.1 The failure taxonomy and the gross-vs-net split

```python
import csv, glob
from collections import defaultdict

# NOTE 1: the sweep CSVs OVERLAP — batch 2 re-ran s08..s17, so 1,080 rows are
#         duplicates. Deduplicate on (strategy, variant, instrument, window,
#         cost) FIRST.
# NOTE 2: r['n_trades'] is a FLOAT string in some files ('1544.0'). int()
#         raises and silently drops 720 rows -> 1,360 groups instead of 1,600.
seen = {}
for f in glob.glob('strategy/results/iterations_*.csv'):
    for r in csv.DictReader(open(f)):
        try:
            r['edge'] = float(r['edge_vs_bh_pct'])
            r['tpy']  = float(r['trades_per_year'] or 0)
            r['n']    = float(r['n_trades'] or 0)
            r['cost'] = float(r['cost_bps'])
            r['ret']  = float(r['total_return_pct'])
            r['bh']   = float(r['buyhold_return_pct'])
        except ValueError:
            continue
        seen[(r['strategy'], r['variant'], r['instrument'], r['window'], r['cost'])] = r

grp = defaultdict(dict)
for (s, v, i, w, c), r in seen.items():
    grp[(s, v, w)][(i, c)] = r
# -> 1,600 (strategy, variant, window) groups; 4,800 distinct 2 bps cells

cats = defaultdict(int)
for k, cm in grp.items():
    c0 = {i: r for (i, c), r in cm.items() if c == 0.0}
    c2 = {i: r for (i, c), r in cm.items() if c == 2.0}
    if not c0 or not c2:
        continue
    w0 = [i for i, r in c0.items() if r['edge'] > 0]
    w2 = [i for i, r in c2.items() if r['edge'] > 0]
    n = sum(r['n'] for r in c2.values())
    if len(w2) >= 2:
        cats['A. PASS'] += 1
    elif len(w2) == 1:
        cats['B. 1-instrument'] += 1
    elif n == 0:
        cats['C. empty signal'] += 1
    elif w0:
        cats['D. cost-killed (had gross edge)'] += 1
    elif any(r['ret'] > 0 for r in c0.values()):
        cats['E. made money, underperformed buy-hold'] += 1
    else:
        cats['F. lost money outright'] += 1
# -> A 10 (0.6%) | B 62 (3.9%) | C 15 (0.9%) | D 374 (23.4%)
#    E 1062 (66.4%) | F 77 (4.8%)
```

### 10.2 The degenerate-win count (§4.1)

```python
DEGENERATE_MAX_TRADES = 2
wins = [r for r in seen.values() if r['cost'] == 2.0 and r['edge'] > 0]
degenerate = [r for r in wins if r['n'] <= DEGENERATE_MAX_TRADES]
degenerate_and_tiny = [r for r in degenerate if abs(r['edge']) < 1.0]
# -> 83 wins, 17 degenerate (20 %), of which 9 have edge < 1 %
```

### 10.3 The per-family map (§3.1)

```python
import re
fam = {}
for line in open('strategy/STRATEGY_REGISTRY.md'):
    if not re.match(r'^\| S-\d+ \|', line):
        continue
    c = [x.strip() for x in line.split('|')]
    base = sorted({re.sub(r'_\d+(?:_\d+)?$', '', t)
                   for t in re.findall(r'`([a-z0-9_]+)`', c[4])})
    fam['S-' + c[1][2:].zfill(2)] = base[0] if base else '?'

byfam = defaultdict(lambda: [0, 0])
for (s, v, w), cm in grp.items():
    c2 = {i: r for (i, c), r in cm.items() if c == 2.0}
    base = fam.get('S-' + s[1:].zfill(2), '?')
    byfam[base][0] += 1
    if any(r['edge'] > 0 and r['n'] > DEGENERATE_MAX_TRADES for r in c2.values()):
        byfam[base][1] += 1
```

### 10.4 The closed-family list (§5.6)

```python
TOTAL_GROUPS = sum(g[0] for g in byfam.values())
MEAN_GROUPS  = TOTAL_GROUPS / len(byfam)          # 1600 / 55 = 29.1

closed = []
for base, (g, w) in byfam.items():
    rate = w / g if g else 1.0
    if g >= 30 and rate <= 0.05:
        closed.append((base, g, rate))
closed.sort(key=lambda x: -x[1])

for base, g, rate in closed:
    print(f"{base:14} groups={g:4}  rate={rate:6.1%}")
print(f"-> {len(closed)} families, {sum(g for _, g, _ in closed)} groups = "
      f"{100 * sum(g for _, g, _ in closed) / TOTAL_GROUPS:.1f}% of the budget")
# -> 16 families, 804 groups = 50.2 % of the budget
```

### 10.5 The current pass bar is not yet fail-closed

```python
import strategy.schema as schema
# rows must carry window == 'oos' and the *total_return_pct* /
# *buyhold_return_pct* columns (the sweep's edge_vs_bh_pct is not enough).
out = schema.oos_pass_fields(rows, min_instruments=2, max_trades_per_year=54)
# today: s109/ema_gate -> pass True ; s103/wide_exit -> pass True ; s55/looser -> pass True
# after §4.2: all three must fail
```

---

## 11. What this plan explicitly does **not** do

| Item | Why not |
|---|---|
| Consume the OOS holdout | A one-shot resource; spent only on a human-nominated finalist after D-1…D-5 |
| Add strategies to classes A / B / F / G / H | Measured dead: 0–3.6 % hit rate; 39 zero-win families holding 62.5 % of the budget |
| Claim that a risk-adjusted bar will manufacture winners | §2.4: it yields 1 cell of 120 on the diverse batch. The point is a correct *diagnosis*, not quick wins |
| Build a walk-forward harness / dedup engine / vectorised engine / YAML schema | Still deliberately deferred (`repo_review_20261028` §3) |
| Merge `strategy_rsi_lib.py` into the shared core | A state-leak bug was hit and reverted (`repo_review_20261028` §B3) |
| Change `oos.pass_criteria` unilaterally | §4.2 needs owner sign-off (§8, D-1 / D-2) |
| Promote S-55 | §4.5 changes the bar; re-evaluate under it first |
| Increase parallelism | §5.7 — amplifies false positives until the protocol is machine-enforced |
| Regenerate historical results after the causality repairs | The repo's own position: historical artifacts are evidence of the *original* implementation, with caveats; recompute into a separate versioned artifact before treating them as current-code evidence |
