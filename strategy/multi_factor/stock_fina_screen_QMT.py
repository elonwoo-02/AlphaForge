# -*- coding: utf-8 -*-
"""
多因子选股 - 筛选1（通用版，绝对阈值）。

使用 5 层漏斗 + 绝对阈值筛选达标股票：
  1. ROE >= {ROE_MIN}%
  2. 净利润同比 >= {NETPROFIT_YOY_MIN}%
  3. 毛利率 >= {GROSSPROFIT_MARGIN_MIN}%
  4. 资产负债率 <= {DEBT_TO_ASSETS_MAX}%
  5. 经营现金流/营收 >= {OCF_TO_REVENUE_MIN}%

运行前提：
    - 已运行 stock_fina_download_QMT.py 生成输入文件

输入文件：fetch_data/stock_fina_pool_QMT.csv
输出文件：fetch_data/stock_fina_selected_QMT.csv
"""
import logging
from pathlib import Path

import pandas as pd

logger = logging.getLogger(__name__)

# ============ 配置常量 ============
ROE_MIN = 15                 # ROE 下限（%）
NETPROFIT_YOY_MIN = 10       # 净利润同比下限（%）
GROSSPROFIT_MARGIN_MIN = 30  # 毛利率下限（%）
DEBT_TO_ASSETS_MAX = 60      # 资产负债率上限（%）
OCF_TO_REVENUE_MIN = 10      # 经营现金流/营收下限（%）

DIVIDER_WIDTH = 60
DISPLAY_HEAD_LIMIT = 20      # 预览显示行数

DATA_DIR = Path(__file__).resolve().parent / "fetch_data"
INPUT_FILE = DATA_DIR / "stock_fina_pool_QMT.csv"
OUTPUT_FILE = DATA_DIR / "stock_fina_selected_QMT.csv"

NUMERIC_COLUMNS = ['roe', 'netprofit_yoy', 'grossprofit_margin', 'debt_to_assets', 'ocf_to_revenue']

FILTER_LAYERS = [
    ('roe', '>=', ROE_MIN, 'ROE'),
    ('netprofit_yoy', '>=', NETPROFIT_YOY_MIN, '净利润同比'),
    ('grossprofit_margin', '>=', GROSSPROFIT_MARGIN_MIN, '毛利率'),
    ('debt_to_assets', '<=', DEBT_TO_ASSETS_MAX, '资产负债率'),
    ('ocf_to_revenue', '>=', OCF_TO_REVENUE_MIN, '经营现金流/营收'),
]

DISPLAY_COLUMNS = [
    'stock_code', 'stock_name', 'end_date', 'roe', 'netprofit_yoy',
    'grossprofit_margin', 'debt_to_assets', 'ocf_to_revenue',
]


def _load_input():
    """读取输入 CSV 并做数值化处理。"""
    if not INPUT_FILE.exists():
        logger.error(f"Input file not found: {INPUT_FILE}")
        logger.error("  Please run stock_fina_download_QMT.py first")
        return None

    df = pd.read_csv(INPUT_FILE, encoding='utf-8-sig')
    logger.info(f"Loaded {len(df)} stocks from {INPUT_FILE.name}")

    for col in NUMERIC_COLUMNS:
        if col in df.columns:
            df[col] = pd.to_numeric(df[col], errors='coerce')
    return df


def _apply_filters(df):
    """逐层应用筛选条件。"""
    mask = pd.Series(True, index=df.index)

    for idx, (col, op, threshold, label) in enumerate(FILTER_LAYERS, start=1):
        if col not in df.columns:
            logger.warning(f"  Layer {idx}: Column '{col}' not found, skipping")
            continue
        if op == '>=':
            mask &= (df[col] >= threshold)
        else:
            mask &= (df[col] <= threshold)
        logger.info(f"  Layer {idx} {label} {op} {threshold}%: {mask.sum()} stocks remain")

    return df[mask]


def _save_results(selected):
    """保存筛选结果并打印预览。"""
    selected = selected.sort_values('roe', ascending=False).reset_index(drop=True)

    DATA_DIR.mkdir(parents=True, exist_ok=True)
    selected.to_csv(OUTPUT_FILE, index=False, encoding='utf-8-sig')
    logger.info(f"Data saved to: {OUTPUT_FILE}")
    logger.info(f"  {len(selected)} stocks passed all filters")

    if len(selected) > 0:
        disp_cols = [c for c in DISPLAY_COLUMNS if c in selected.columns]
        logger.info("")
        logger.info("=" * DIVIDER_WIDTH)
        logger.info("Qualified stocks (sorted by ROE):")
        logger.info("=" * DIVIDER_WIDTH)
        preview = selected[disp_cols].head(DISPLAY_HEAD_LIMIT).to_string(index=False)
        logger.info(preview)


def screen_stocks():
    """多因子选股 - 筛选1（绝对阈值）。"""
    logger.info("Multi-factor screening - Filter 1 (Absolute Threshold)")
    logger.info(f"  ROE >= {ROE_MIN}% | Net Profit YoY >= {NETPROFIT_YOY_MIN}% | Gross Margin >= {GROSSPROFIT_MARGIN_MIN}%")
    logger.info(f"  Debt-to-Assets <= {DEBT_TO_ASSETS_MAX}% | OCF/Revenue >= {OCF_TO_REVENUE_MIN}%")
    logger.info("-" * DIVIDER_WIDTH)

    df = _load_input()
    if df is None:
        return None

    selected = _apply_filters(df)
    _save_results(selected)
    return OUTPUT_FILE


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO, format='%(message)s')
    result = screen_stocks()

    if result:
        logger.info("=" * DIVIDER_WIDTH)
        logger.info("Screening completed successfully")
        logger.info(f"  Output: {result}")
        logger.info("=" * DIVIDER_WIDTH)
    else:
        logger.error("Screening failed")