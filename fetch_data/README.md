# 数据采集 (fetch_data)

本目录提供 **A 股行情、财务数据** 以及 **加密货币行情** 的下载脚本，覆盖 **4 种数据源**，共 **12 个脚本**。

> 各子目录均包含独立的 `README.md` 和 `requirements.txt`，详细内容请查看对应子目录。

---

## 目录结构

```
fetch_data/
├── README.md                  # 本说明（总索引）
├── requirements.txt           # Python 依赖（全部）
│
├── akshare/                   # A 股 — AkShare（免费，无 Token）
│   ├── README.md
│   ├── daily_data_akshare.py
│   ├── minute_data_akshare.py
│   └── financial_data_akshare.py
│
├── qmt/                       # A 股 — QMT / miniQMT
│   ├── README.md
│   ├── daily_data_qmt.py
│   ├── minute_data_qmt.py
│   └── financial_data_qmt.py
│
├── tushare/                   # A 股 — Tushare Pro（需 Token）
│   ├── README.md
│   ├── daily_data_tushare.py
│   ├── minute_data_tushare.py
│   └── financial_data_tushare.py
│
└── okx/                       # 加密货币 — OKX
    ├── README.md
    ├── daily_okx.py
    └── minute_okx.py
```

---

## 数据源速览

| 数据源 | 覆盖 | 依赖 | 配置要求 |
|--------|------|------|---------|
| **AkShare** | A 股日线 / 分钟 / 财务 | `akshare` | 无 |
| **QMT / miniQMT** | A 股日线 / 分钟 / 财务 | `xtquant` | 启动 miniQMT 客户端 |
| **Tushare Pro** | A 股日线 / 分钟 / 财务 | `tushare` | 环境变量 `TUSHARE_TOKEN` |
| **OKX** | 加密货币日线 / 分钟 | 无需 | 公开 API，无需配置 |

---

## 快速开始

```bash
# 全部安装
pip install -r requirements.txt

# 或使用子目录各自的依赖
pip install -r akshare/requirements.txt
pip install -r tushare/requirements.txt

# AkShare（免费）
python akshare/daily_data_akshare.py

# QMT（需先启动 miniQMT 客户端）
python qmt/daily_data_qmt.py

# Tushare（需设置 Token）
export TUSHARE_TOKEN="your_token_here"
python tushare/daily_data_tushare.py

# 加密货币（无需配置）
python okx/daily_okx.py
```

---

## 输出文件

所有 CSV 统一保存在各自子目录的 `data/` 子目录下，使用 `utf-8-sig` 编码（Excel 直接打开不乱码）。

| 文件 | 来源 | 说明 |
|------|------|------|
| `600519_SH_daily_*.csv` | 三源 | 贵州茅台日线 OHLCV（前复权） |
| `600519_SH_1min_*.csv` | 三源 | 贵州茅台 1 分钟 K 线 |
| `600519_SH_fina_*.csv` | 三源 | 贵州茅台综合财务指标 |
| `BTC_USDT_daily_okx.csv` | OKX | BTC-USDT 日线 OHLCV |
| `BTC_USDT_1min_okx.csv` | OKX | BTC-USDT 1 分钟 K 线 |
| `ETH_USDT_daily_okx.csv` | OKX | ETH-USDT 日线 OHLCV |
| `ETH_USDT_1min_okx.csv` | OKX | ETH-USDT 1 分钟 K 线 |
| `SOL_USDT_daily_okx.csv` | OKX | SOL-USDT 日线 OHLCV |
| `SOL_USDT_1min_okx.csv` | OKX | SOL-USDT 1 分钟 K 线 |

---

## 数据格式约定

### 日线 / 分钟数据

| 字段 | 含义 |
|------|------|
| `date` / `datetime` | 日期（日线）或精确时间戳（分钟） |
| `open` / `high` / `low` / `close` | 开高低收 |
| `volume` | 成交量 |

### 财务数据

| 类别 | 字段 |
|------|------|
| 每股指标 | `eps`, `bps`, `ocfps` |
| 盈利能力 | `roe`, `roa`, `grossprofit_margin`, `netprofit_margin`, `op_margin` |
| 偿债能力 | `debt_to_assets`, `current_ratio`, `quick_ratio` |
| 营运能力 | `assets_turn` |
| 现金流 | `operating_cashflow`, `investing_cashflow`, `financing_cashflow`, `ocf_to_revenue`, `ocf_to_profit` |
| 规模 | `revenue`, `net_profit`, `total_assets`, `total_liab`, `total_equity` |

---

## 更多详情

| 主题 | 查看 |
|------|------|
| 各数据源详细运行说明 | 对应子目录的 `README.md` |
| QMT 开户与 QMT/miniQMT 对比 | `qmt/README.md` |
| 加密货币与 A 股差异说明 | `okx/README.md` |