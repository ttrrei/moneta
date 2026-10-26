# Moneta / Nova: Technical Indicator & Feature Engine Final Specification (`indicator_final.md`)

> **版本**：v2.0 Final (Unified Production Blueprint)  
> **定位**：量化交易策略搜索与特征工程的最终研发蓝本（AI 自动化重构与代码生成的 Single Source of Truth）  
> **适用范围**：OANDA CFD 多品种（外汇 FX、贵金属、原油、全球股指、加密货币），5m（日内交易信号层）与 1h（宏观背景层）OHLCV 数据  
> **前序版本依据**：深度整合 `docs/indicators.md` (v0 spec)、`docs/indicator_draft_version_a.md` (库层实现)、`docs/indicator_draft_version_b.md` (特征广度与金融逻辑) 及 `docs/indicator_comment.md` (架构补充与生产决策)

---

## 1. 核心目标与量化设计哲学

1. **库优先，严禁手写基础公式**：核心指标优先采用成熟生产级 C 库（`TA-Lib`），杜绝手工编码带来的数值偏差、边界漏洞与 Python 循环性能瓶颈。
2. **因果性（Causality）第一，零前瞻偏差**：任何在 $T$ 时刻生成的特征，数学上仅依赖 $\le T$ 的历史数据。严格禁止未来函数、重绘算子（Repainting）与错误的跨周期拼接。
3. **全自动化验证，不依赖人工肉眼**：建立全自动化的六重质量门禁（因果截断、起点无关收敛、数值不变性、奇异值容错、双库交叉 Parity、时序不对称校验）。
4. **CFD 专属周期网格，彻底脱离传统股市默认值**：全面废除 9/14/20/50/200 等美股日线习惯参数，统一采用贴合 24h 连续交易市场的 Bar-Count 统一网格。
5. **特征丰富度服务于策略搜索，解耦特征生成与 Alpha 检验**：系统性覆盖“趋势跟踪、动量衰竭、波动率挤压、市场体制/效率、K线微观结构、活跃度代理”六大维度，构建高信息密度的特征矩阵。

---

## 2. 精度管理与存储优化（Precision & Storage Policy）

结合底层计算精度要求与下游机器学习（PyTorch / LightGBM）的高效训练需求，确立两段式精度机制：

| 阶段 | 采用精度 | 核心目标与依据 |
|---|---|---|
| **特征计算阶段** | **`float64`** (Double Precision) | 1. 与 `TA-Lib` 底层 C 指针（`double*`）原生对齐，杜绝 NumPy 频繁隐式转换带来的性能开销；<br>2. 保证 EMA、Wilder RSI、ADX 等长周期递归平滑特征无累积截断漂移。 |
| **存储与导出阶段** | **`float32`** (Single Precision) | 1. 5m 级别单品种 ~51 万行 $\times$ 150+ 特征列，转为 `float32` 可使 Parquet 文件大小及读取内存直接减半（从 ~600MB 降至 ~300MB）；<br>2. 树模型（LightGBM/XGBoost）特征分箱与神经网络浮点张量计算天然基于 `float32`，无信息损失。 |

---

## 3. 数据事实、断层处理与时序防线（Data Reality & Look-Ahead Prevention）

### 3.1 拒绝合成数据插值（No Synthetic Filling）

- **数据稀疏性事实**：OANDA CFD 数据在周末休市、流动性枯竭时不存在对应分钟的行情。
- **计算原则**：**所有滚动窗口（`rolling(n)`）严格按连续的“有效 Bar 行数（Row Count）”计算**，严禁在底层做前向填充（ffill）或线性插值假数据。
  > *避坑理由*：若在周末休市 48 小时盲目按 5m 插值填充，会凭空捏造 576 根一模一样的平价 Bar，导致均线完全拉平、ATR 暴跌至 0，严重污染技术指标分布。

### 3.2 显式断层微观特征（Explicit Gap Features）

不伪造数据，而是将断层显式量化为策略信号层的输入特征，由下游模型自主决策是否过滤：
- **`is_gap_bar`**：当前 Bar 的 `time` 与前一根 Bar 的 `close_time` 差值大于一个标准周期时标记为 1，否则为 0；
- **`is_partial`**：当前 Bar 聚合的 1m 行数不足标准根数（5m < 5 根，1h < 60 根）时标记为 1；
- **`is_near_market_close`**：时间处于周五纽约收盘前 2 小时内标记为 1（防范周末持仓隔夜风险）。

### 3.3 跨周期 As-Of Join 黄金法则

将 1h 宏观背景特征对齐到 5m 信号层时，**必须且只能以 `close_time`（收盘时间）进行 As-Of Join**：

$$\text{Bar}_{5m}.\text{close\_time} \ge \text{Bar}_{1h}.\text{close\_time}$$

```sql
-- 5m: close_time = time + 5 minutes
-- 1h: close_time = time + 1 hour
SELECT 
    m.*,
    h.ema_24 AS h1_ema_24,
    h.atr_24 AS h1_atr_24
FROM ohlcv_5m m
ASOF LEFT JOIN ohlcv_1h h
  ON m.instrument = h.instrument
 AND m.close_time >= h.close_time;
```
- **执行规则**：在 $T$ 时刻 Bar 收盘后生成特征，信号仅允许在 **$T+1$ 时刻的 Open 价格**成交。
- **算子禁区**：严禁全局均值/方差标准化、严禁 `shift(-k)`、严禁未来平移指标（如 Ichimoku 迟行带）、严禁未右侧确认拐点的 Zigzag/Fractals、严禁 `df.ta.strategy("All")`。

---

## 4. CFD 参数网格与动态时区结算（Parameter Grid & Dynamic VWAP）

### 4.1 统一参数网格

参数一律由封装层强制白名单校验，库默认值全部屏蔽：
- **单窗口集合**：$N \in \{6, 12, 24, 60, 120\}$；
- **双窗口对（快, 慢）**：仅允许 `(6, 24)`, `(12, 60)`, `(24, 120)`；
- **固定常量**：Bollinger $\sigma=2.0$，Keltner $mult=2.0$，CCI 常数 $=0.015$，无量纲基准 ATR 窗口 $\text{NORM\_ATR}=24$。

### 4.2 动态品种结算时区（Dynamic Session Reset）

彻底废除全局一刀切的 UTC 00:00 截断，根据不同资产类别的真实交易惯例配置日内锚定重置点（Session Reset）：

| 资产类别 | 代表品种 | 真实结算锚定时间 | 说明与业务逻辑 |
|---|---|---|---|
| **外汇与现货贵金属** | `EUR_USD`, `GBP_USD`, `USD_JPY`, `XAU_USD`, `XAG_USD` | **17:00 EST**（纽约收盘，对应 UTC 21:00/22:00） | 全球银行间外汇展期换日点，在此重置 VWAP 最具资金流向指示价值。 |
| **美股指数 CFD** | `US30_USD`, `SPX500_USD`, `NAS100_USD` | **09:30 EST**（纽约开盘，对应 UTC 13:30/14:30） | 以美股常规交易时段（RTH）开盘作为日内累积基准点。 |
| **欧洲指数 CFD** | `DE30_EUR`, `UK100_GBP` | **08:00 CET/BST**（对应 UTC 07:00/08:00） | 欧洲主要交易时段开盘锚定。 |
| **亚太指数 CFD** | `JP225_USD`, `HK33_HKD`, `CN50_USD` | **本地交易所开市时间**（例如东京 09:00 JST / 香港 09:30 HKT） | 锚定亚洲主力流动性释放时间。 |
| **大宗原油与加密货币** | `WTICO_USD`, `BCO_USD`, `BTC_USD`, `ETH_USD` | **UTC 00:00** | 国际大宗商品与 24/7 纯数字资产基准日切。 |

---

## 5. 核心定义冲突的最终决议

| 争议项 | 决策对比 | 最终落地决议 | 决议理由 |
|---|---|---|---|
| **Bollinger & HV 标准差自由度** | 总体标准差 (`ddof=0`) vs 样本标准差 (`ddof=1`) | **统一采用 `ddof=0`** | TA-Lib 底层原生为 `ddof=0`；在 $N \ge 24$ 时相对差异 $<2\%$，在 $N=120$ 时仅 $0.4\%$，保持 C 底层零转换与极致性能。 |
| **Stochastic %K 平滑** | `STOCH` (库默认慢速平滑) vs `STOCHF` (快速未平滑) | **必须使用 `talib.STOCHF`** | 杜绝库隐式过度平滑，保留原汁原味快速 %K；%D 统一固定使用网格参数 SMA 6。 |
| **Keltner Channels** | pandas-ta `kc` vs TA-Lib EMA+ATR 组合 | **采用 TA-Lib EMA $\pm 2.0 \times$ ATR** | 避免 pandas-ta 内部采用 TR 移动平均（而非 Wilder ATR）的不确定性；用已验证的 TA-Lib 输出直接做 2 行向量化运算，性能极高。 |
| **MACD 信号线** | 默认 9 vs 显式传入快线周期 | **固定为 `signal = fast`** | 即 `(6, 24)` 的信号线为 6，`(12, 60)` 为 12，`(24, 120)` 为 24，确保所有参数严格封闭在 CFD 网格内。 |
| **预热期丢弃策略 (Warm-up Drop)** | 保留前导 NaN vs 全自动裁剪 | **全流程最终落盘时自动裁剪（DropNA）** | 矩阵计算完成后，自动截断前 $3 \times \max(N) = 360$ 行头部预热数据（占 50 万行数据的 0.07%），向下游交付绝对纯净无 NaN 的特征矩阵。 |

---

## 6. 模块化特征族架构（Modular Architecture for `pipeline/indicators.py`）

为彻底改变原有单体脚本难以维护的缺陷，`pipeline/indicators.py` 全面重构为基于抽象基类的 **7 大模块化特征族（Feature Groups）** 架构：

```
                    +-----------------------------+
                    |    BaseFeatureGroup (ABC)   |
                    +-----------------------------+
                                   |
         +-------------------------+-------------------------+
         |                         |                         |
+-------------------+     +-------------------+     +-------------------+
|    TrendGroup     |     |   MomentumGroup   |     |  VolatilityGroup  |
|  (SMA/EMA/MACD/   |     | (RSI/ROC/MOM/     |     | (ATR/Bollinger/   |
|   ADX/Aroon/DC)   |     |  Stoch/CCI/WILLR) |     |  Keltner/Squeeze) |
+-------------------+     +-------------------+     +-------------------+
         |                         |                         |
+-------------------+     +-------------------+     +-------------------+
|    RegimeGroup    |     |CandleStructureGrp |     |  VolumeProxyGroup |
|   (ER/Choppiness) |     | (Body/Wick/CLV)   |     | (VolSMA/VWAP/MFI) |
+-------------------+     +-------------------+     +-------------------+
                                   |
                          +-------------------+
                          |DerivedFeatureGroup|
                          | (Norm ATR/Dist/   |
                          |  Spread/Cyclic)   |
                          +-------------------+
```

### 6.1 抽象接口约定

```python
class BaseFeatureGroup(abc.ABC):
    """所有特征族必须实现的标准化接口。"""
    
    @abc.abstractmethod
    def compute(self, df: pd.DataFrame, n_grid: list[int], pairs: list[tuple[int, int]]) -> dict[str, np.ndarray]:
        """执行全向量化特征计算，返回 {列名: float64一维数组} 字典。"""
        pass
        
    @property
    @abc.abstractmethod
    def required_columns(self) -> list[str]:
        """该组所需的输入字段（例如 ['close'] 或 ['high', 'low', 'close', 'volume']）。"""
        pass
```

---

## 7. 全景指标与特征映射清单（The Feature Catalog）

全流程输入必须为 `float64`、内存连续（C-contiguous）的 NumPy 数组。

### 7.1 趋势与方向组 (`TrendGroup`)

| 特征代码 | 输出列名规范 | 实现库与底层函数 | 对照基准 | 预热行数 | 数学定义与逻辑 |
|---|---|---|---|---|---|
| **SMA** | `sma_{n}` | `talib.SMA(c, timeperiod=n)` | pandas rolling mean | $n$ | 简单收盘价移动平均 |
| **EMA** | `ema_{n}` | `talib.EMA(c, timeperiod=n)` | pandas ewm (span=n) | $3n$ | 指数移动平均（由 3n 预热消除起点差异） |
| **MACD** | `macd_{f}_{s}`<br>`macd_signal_{f}_{s}`<br>`macd_hist_{f}_{s}` | `talib.MACD(c, fastperiod=f, slowperiod=s, signalperiod=f)` | pandas-ta `macd` | $3s$ | 信号线周期等于 $f$；柱状图 $\text{hist} = \text{macd} - \text{signal}$ |
| **ADX / DI** | `adx_{n}`<br>`plus_di_{n}`<br>`minus_di_{n}` | `talib.ADX(h, l, c, n)`<br>`talib.PLUS_DI(h, l, c, n)`<br>`talib.MINUS_DI(h, l, c, n)` | pandas-ta `adx` | $3n$ | Wilder 平滑方向性指标，取值严格在 $[0, 100]$ |
| **Aroon** | `aroon_up_{n}`<br>`aroon_down_{n}` | `talib.AROON(h, l, timeperiod=n)` | pandas-ta `aroon` | $n+1$ | 度量创近期新高/新低的 Bar 距离，$[0, 100]$ |
| **Donchian**| `dc_upper_{n}`<br>`dc_lower_{n}`<br>`dc_mid_{n}` | 向量封装：`talib.MAX(h, n)`，`talib.MIN(l, n)`，mid 为均值 | pandas rolling max/min | $n$ | 唐奇安通道；突破策略使用前一根通道值 `shift(1)` 对比 |

### 7.2 动量与衰竭组 (`MomentumGroup`)

| 特征代码 | 输出列名规范 | 实现库与底层函数 | 对照基准 | 预热行数 | 数学定义与逻辑 |
|---|---|---|---|---|---|
| **RSI** | `rsi_{n}` | `talib.RSI(c, timeperiod=n)` | pandas-ta `rsi` | $3n$ | Wilder 相对强弱指数，$[0, 100]$ |
| **ROC** | `roc_{n}` | `talib.ROC(c, timeperiod=n)` | pandas pct_change*100 | $n$ | 动量变动率：$(c_t - c_{t-n}) / c_{t-n} \times 100$ |
| **MOM** | `mom_{n}` | `talib.MOM(c, timeperiod=n)` | pandas diff(n) | $n$ | 原始差值动量：$c_t - c_{t-n}$ |
| **Stochastic**| `stoch_k_{n}`<br>`stoch_d_{n}` | `talib.STOCHF(h, l, c, fastk_period=n, fastd_period=6, fastd_matype=0)` | pandas-ta `stoch` (raw) | $n + 6$ | **严禁使用 `talib.STOCH`**；%D 统一采用 SMA 6 |
| **CCI** | `cci_{n}` | `talib.CCI(h, l, c, timeperiod=n)` | pandas-ta `cci` | $n$ | 顺势指标，常数固定为 $0.015$ |
| **Williams %R**| `willr_{n}` | `talib.WILLR(h, l, c, timeperiod=n)` | pandas-ta `willr` | $n$ | 威廉指标，本质为 $\text{stoch\_k} - 100$，取值 $[-100, 0]$ |

### 7.3 波动率、挤压与突破准备组 (`VolatilityGroup`)

| 特征代码 | 输出列名规范 | 实现库与底层函数 | 对照基准 | 预热行数 | 数学定义与逻辑 |
|---|---|---|---|---|---|
| **True Range** | `tr` | `talib.TRANGE(h, l, c)` | 手算 max(h-l, ...) | 1 | 真实波幅 |
| **ATR** | `atr_{n}` | `talib.ATR(h, l, c, timeperiod=n)` | pandas-ta `atr` | $3n$ | Wilder 平均真实波幅 |
| **Bollinger** | `bb_mid_{n}`<br>`bb_upper_{n}`<br>`bb_lower_{n}` | `talib.BBANDS(c, timeperiod=n, nbdevup=2.0, nbdevdn=2.0, matype=0)` | pandas-ta `bbands` | $n$ | 中轨、上轨、下轨（采用总体标准差 ddof=0） |
| **BB 派生** | `bb_width_{n}`<br>`bb_pctb_{n}` | 向量化算术：<br>`width = (upper - lower) / mid`<br>`pctb = (c - lower) / (upper - lower)` | pandas | $n$ | **关键预警特征**：宽度衡量波动率压缩程度，%B 衡量相对位置 |
| **Keltner** | `kc_mid_{n}`<br>`kc_upper_{n}`<br>`kc_lower_{n}` | 向量化算术：<br>`mid = talib.EMA(c, n)`<br>`upper/lower = mid ± 2.0 * talib.ATR(h,l,c,n)` | - | $3n$ | 基于已验证的 TA-Lib 基础输出直接组合 |
| **Squeeze** | `sqz_on_{n}` | 向量化逻辑：<br>`(bb_lower > kc_lower) & (bb_upper < kc_upper)` | - | $3n$ | **核心预警特征**：布林带收缩进肯特纳通道内为 1（强压缩爆发就绪），否则为 0 |
| **HV** | `hv_{n}` | 对数收益后调用：`talib.STDDEV(log_ret, n)` | pandas rolling std(ddof=0) | $n+1$ | 历史波动率（未年化，直接反映尺度离散度） |

### 7.4 市场体制与混沌组 (`RegimeGroup`)

| 特征代码 | 输出列名规范 | 实现库与底层函数 | 对照基准 | 预热行数 | 数学定义与逻辑 |
|---|---|---|---|---|---|
| **Efficiency Ratio** | `er_{n}` | `pandas-ta-classic.er(c, length=n)` | 手算单边比值 | $n$ | 卡夫曼效率比，$[0, 1]$；接近 1 为强单边，接近 0 为混乱震荡 |
| **Choppiness** | `chop_{n}` | `pandas-ta-classic.chop(h, l, c, length=n)` | 向量化手算 | $n$ | 混沌指数，$[0, 100]$；$> 61.8$ 为密集盘整，$< 38.2$ 为强趋势单边 |

### 7.5 K 线微观结构组 (`CandleStructureGroup`)

全向量化单 Bar 无量纲形态提取，除以零处添加 $\epsilon = 10^{-12}$ 保护：

| 特征代码 | 命名规范 | 计算公式 | 物理交易含义 |
|---|---|---|---|
| **Body Ratio** | `bar_body_ratio` | $\lvert c - o \rvert / \max(h - l, \epsilon)$ | 实体占总振幅比例（单边主导动力） |
| **Upper Wick** | `bar_upper_wick_ratio` | $(h - \max(o, c)) / \max(h - l, \epsilon)$ | 上影线比例（上方抛压与多头衰竭） |
| **Lower Wick** | `bar_lower_wick_ratio` | $(\min(o, c) - l) / \max(h - l, \epsilon)$ | 下影线比例（下方承接与空头衰竭） |
| **Close Location** | `bar_clv` | $((c - l) - (h - c)) / \max(h - l, \epsilon)$ | 收盘相对位置 $[-1, 1]$；+1 强收顶，-1 强收底 |

### 7.6 成交量活跃度代理组 (`VolumeProxyGroup`)

> **注**：OANDA 数据为 Tick Volume（价格跳动频次），全部作为**市场活跃度代理（Activity Proxy）**。

| 特征代码 | 输出列名规范 | 实现库与映射 | 预热行数 | 数学定义与逻辑 |
|---|---|---|---|---|
| **Volume SMA** | `vol_sma_{n}` | `talib.SMA(volume, n)` | $n$ | Tick 活跃度基准移动平均 |
| **Volume Ratio** | `vol_rel_{n}` | `volume / talib.SMA(volume, n)` | $n$ | 相对活跃度倍数（量比异动） |
| **Dynamic VWAP**| `vwap` | 依据 §4.2 品种结算时区累加：<br>`cumsum(tp * vol) / cumsum(vol)` | 当日首根重置 | 动态品种时区锚定日内成交量加权均价代理 |
| **MFI** | `mfi_{n}` | `talib.MFI(h, l, c, volume, n)` | $n$ | 资金流量指标（基于活跃度加权的强弱振荡） |
| **CMF** | `cmf_{n}` | `pandas-ta-classic.cmf(h, l, c, volume, n)` | $n$ | 佳庆资金流量指标 |

### 7.7 尺度无关复合特征组 (`DerivedFeatureGroup`)

消除价格绝对水平漂移，用于跨品种、跨年份模型训练：

| 特征代码 | 命名规范 | 构造公式 | 物理金融含义 |
|---|---|---|---|
| **Normalized ATR** | `atr_pct_{n}` | `atr_{n} / close` | 相对波动率百分比 |
| **EMA Distance** | `ema_dist_{n}` | `(close - ema_{n}) / atr_24` | 价格偏离均线的 ATR 倍数（均值回归拉伸度） |
| **EMA Spread** | `ema_spread_{f}_{s}` | `(ema_{f} - ema_{s}) / atr_24` | 喇叭口扩散程度（趋势加速预警） |
| **Donchian Pos** | `dc_pos_{n}` | `(close - dc_lower_{n}) / max(dc_upper_{n} - dc_lower_{n}, \epsilon)` | 通道内相对百分比位置 $[0, 1]$ |
| **High/Low Dist**| `dist_high_{n}`<br>`dist_low_{n}` | `(talib.MAX(h, n).shift(1) - close) / atr_24`<br>`(close - talib.MIN(l, n).shift(1)) / atr_24` | 距离过去 $N$ 根突破极值的 ATR 距离（杜绝前瞻，shift 1） |
| **Time Cyclic** | `hour_sin`, `hour_cos`<br>`dow_sin`, `dow_cos` | 时间戳正余弦变换：<br>$\sin(2\pi \cdot \text{hour} / 24)$ 等 | 捕获时区重叠与星期效应的连续周期性特征 |

---

## 8. 六重自动化质量验证体系（Quality Gates）

任何新指标或库版本升级，必须通过六重自动化门禁断言：

```
                    [ 待验证特征流水线 ]
                              |
    +---------------------------------------------------+
    | Gate 1: 因果性与截断测试 (Causality / Truncation)  | -> 断言: max|V_trunc - V_full[:k]| < 1e-12 (零重绘)
    +---------------------------------------------------+
                              | PASS
    +---------------------------------------------------+
    | Gate 2: 起点无关与预热测试 (Start-Independence)   | -> 断言: 3n预热后截断重算相对误差 < 1e-4
    +---------------------------------------------------+
                              | PASS
    +---------------------------------------------------+
    | Gate 3: 数值边界与不变性测试 (Bounds & Invariants) | -> 断言: RSI/Stoch in [0,100], ATR >= 0, BB lower<=upper
    +---------------------------------------------------+
                              | PASS
    +---------------------------------------------------+
    | Gate 4: 奇异值与极限容错测试 (Edge-Cases Division)| -> 断言: 平价Bar/零振幅注入无未捕获Inf/崩溃
    +---------------------------------------------------+
                              | PASS
    +---------------------------------------------------+
    | Gate 5: 双库 Parity 交叉比对 (Dual-Library Parity)| -> 断言: 滚动类相对误差 < 1e-9，递归类 < 1e-3 (ddof=0对齐)
    +---------------------------------------------------+
                              | PASS
    +---------------------------------------------------+
    | Gate 6: 跨周期 As-Of 时序测试 (Time Alignment)    | -> 断言: 违背 5m.close >= 1h.close 的行数严格为 0
    +---------------------------------------------------+
                              | PASS
                 [ 标记为 PARITY_PASS 准入生产 ]
```

---

## 9. 最终工程实施路线图（Implementation Roadmap）

开发与重构任务划分为三个严格递进的阶段：

### Phase 1: 模块化重构与特征族骨架构建
- 建立 `pipeline/indicators.py`，实现 `BaseFeatureGroup` 及 7 大特征族类；
- 实现统一网格白名单校验器与列名自动生成器；
- 引入 `float64` 向量化计算与可选 `float32` Parquet 输出转换。

### Phase 2: 六重质量门禁与 Parity 冒烟测试
- 编写 `scripts/verify_indicator_parity.py`，采用 20,000 行 `EUR_USD` 5m 真实样本作为固定测试夹具；
- 全面运行 Gate 1（因果截断）与 Gate 5（TA-Lib vs pandas-ta 对照，验证 `ddof=0` 和 `STOCHF`）；
- 输出基线 Parity 检查报告。

### Phase 3: 动态 VWAP、断层特征及落盘裁剪流水线
- 实现按品种动态锚定结算时区的 VWAP（FX 17:00 EST，美股指数 09:30 EST 等）；
- 计算 `is_gap_bar`, `is_partial`, `is_near_market_close` 断层特征；
- 流水线集成头部自动 DropNA（截掉前 360 行）与 DuckDB/Parquet 分块流式写出。

