# -*- coding: utf-8 -*-
"""
多因子选股 - 筛选2（行业版，打分制）。

纯行业视角打分制：每个指标按行业内排名换算为 1~5 分，
5 项总分相加，筛选总分 >= SCORE_MIN 的股票。

打分规则：
  - 行业内前 20% -> 5 分，20%~40% -> 4 分，40%~60% -> 3 分，60%~80% -> 2 分，后 20% -> 1 分
  - 5 个指标各自得分后相加，总分范围 5~25

运行前提：
    - 已运行 stock_fina_download_QMT.py 生成输入文件

输入文件：fetch_data/stock_fina_pool_QMT.csv
输出文件：fetch_data/stock_fina_selected_QMT_industry.csv
        fetch_data/industry_viz/*.png（行业指标分布可视化）
"""
import logging
from pathlib import Path

import pandas as pd

logger = logging.getLogger(__name__)

# ============ 配置常量 ============
SCORE_MIN = 18               # 总分下限（5~25）
ENABLE_VISUALIZATION = True

SCORE_MIN_VAL = 1            # 单项最低分
SCORE_MAX_VAL = 5            # 单项最高分

DIVIDER_WIDTH = 60
DISPLAY_MAX_COLUMNS = 20
DISPLAY_WIDTH = 200
DISPLAY_HEAD_LIMIT = 20

VIZ_FIGSIZE_WIDTH = 12
VIZ_BAR_MIN_HEIGHT = 6
VIZ_BAR_HEIGHT_PER_ROW = 0.3
VIZ_YTICK_FONT_SIZE = 8
VIZ_SAVE_DPI = 100
VIZ_MIN_SAMPLE_COUNT = 3
VIZ_BAR_ALPHA = 0.8

DATA_DIR = Path(__file__).resolve().parent / "fetch_data"
INPUT_FILE = DATA_DIR / "stock_fina_pool_QMT.csv"
OUTPUT_FILE = DATA_DIR / "stock_fina_selected_QMT_industry.csv"
VIZ_OUTPUT_DIR = DATA_DIR / "industry_viz"

NUMERIC_COLUMNS = ['roe', 'netprofit_yoy', 'grossprofit_margin', 'debt_to_assets', 'ocf_to_revenue']
SCORE_COLUMNS = [
    'roe', 'netprofit_yoy', 'grossprofit_margin',
    'ocf_to_revenue', 'debt_to_assets',
]

DISPLAY_COLUMNS = [
    'stock_code', 'stock_name', 'industry', 'industry_score', 'end_date',
    'roe', 'netprofit_yoy', 'grossprofit_margin', 'debt_to_assets', 'ocf_to_revenue',
]


def add_industry_percentile(df):
    """计算各指标在行业内的排名百分比。"""
    if 'industry' not in df.columns or df['industry'].isna().all() or (df['industry'] == '').all():
        logger.warning("No valid industry fetch_data found, skipping industry percentile")
        return df
    df = df.copy()
    valid = df['industry'].notna() & (df['industry'] != '')
    if not valid.any():
        return df

    higher_better_map = {
        'roe': True, 'netprofit_yoy': True, 'grossprofit_margin': True,
        'ocf_to_revenue': True, 'debt_to_assets': False,
    }
    for col in SCORE_COLUMNS:
        if col not in df.columns:
            continue
        higher_better = higher_better_map.get(col, True)
        pct_col = f'{col}_industry_pct'
        if higher_better:
            df.loc[valid, pct_col] = (
                df.loc[valid].groupby('industry')[col].rank(pct=True, method='average')
            )
        else:
            df.loc[valid, pct_col] = (
                1 - df.loc[valid].groupby('industry')[col].rank(pct=True, method='average')
            )
    return df


def add_industry_score(df):
    """将行业排名百分比换算为 1~5 分，并计算总分。"""
    pct_cols = [f'{col}_industry_pct' for col in SCORE_COLUMNS]

    def pct_to_score(x):
        if pd.isna(x):
            return None
        s = min(SCORE_MAX_VAL, max(SCORE_MIN_VAL, int(x * SCORE_MAX_VAL) + SCORE_MIN_VAL))
        return s

    score_cols = []
    for pct_col in pct_cols:
        if pct_col not in df.columns:
            continue
        score_col = pct_col.replace('_pct', '_score')
        df[score_col] = df[pct_col].apply(pct_to_score)
        score_cols.append(score_col)
    if score_cols:
        df['industry_score'] = df[score_cols].sum(axis=1)
    return df


def industry_distribution_stats(df):
    """计算各行业的指标分布（均值、中位数、样本数）。"""
    if 'industry' not in df.columns or df['industry'].isna().all():
        return None
    valid = df['industry'].notna() & (df['industry'] != '')
    if not valid.any():
        return None
    sub = df.loc[valid]
    metrics = [m for m in NUMERIC_COLUMNS if m in sub.columns]
    if not metrics:
        return None
    agg_dict = {m: ['mean', 'median', 'count'] for m in metrics}
    stats = sub.groupby('industry').agg(agg_dict).round(2)
    return stats


def save_industry_visualization(df, output_dir):
    """按行业生成指标分布可视化图。"""
    try:
        import matplotlib
        matplotlib.use('Agg')
        import matplotlib.pyplot as plt
        plt.rcParams['font.sans-serif'] = ['Microsoft YaHei', 'SimHei', 'SimSun', 'KaiTi']
        plt.rcParams['axes.unicode_minus'] = False
    except ImportError:
        logger.warning("matplotlib not available, skipping visualization")
        return

    if 'industry' not in df.columns or df['industry'].isna().all():
        return
    valid = df['industry'].notna() & (df['industry'] != '')
    if not valid.any():
        return

    output_dir.mkdir(parents=True, exist_ok=True)
    viz_metrics = [
        ('roe', 'ROE (%)'),
        ('grossprofit_margin', '毛利率 (%)'),
        ('debt_to_assets', '资产负债率 (%)'),
    ]
    for col, label in viz_metrics:
        if col not in df.columns:
            continue
        sub = df.loc[valid, ['industry', col]].dropna(subset=[col])
        if sub.empty:
            continue
        ind_agg = sub.groupby('industry')[col].agg(['mean', 'median', 'count'])
        ind_agg = ind_agg[ind_agg['count'] >= VIZ_MIN_SAMPLE_COUNT].sort_values(
            'mean', ascending=(col == 'debt_to_assets')
        )
        if ind_agg.empty:
            continue

        fig, ax = plt.subplots(figsize=(
            VIZ_FIGSIZE_WIDTH,
            max(VIZ_BAR_MIN_HEIGHT, len(ind_agg) * VIZ_BAR_HEIGHT_PER_ROW)
        ))
        ax.barh(range(len(ind_agg)), ind_agg['mean'], label='均值', alpha=VIZ_BAR_ALPHA)
        ax.set_yticks(range(len(ind_agg)))
        ax.set_yticklabels(ind_agg.index, fontsize=VIZ_YTICK_FONT_SIZE)
        ax.set_xlabel(label)
        ax.set_title(f'各行业{label}分布（均值）')
        ax.legend()
        plt.tight_layout()
        out_path = output_dir / f'industry_{col}.png'
        plt.savefig(out_path, dpi=VIZ_SAVE_DPI, bbox_inches='tight')
        plt.close()
        logger.info(f"  Chart saved: {out_path}")


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


def _save_results(selected):
    """保存筛选结果并打印预览。"""
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    selected.to_csv(OUTPUT_FILE, index=False, encoding='utf-8-sig')
    logger.info(f"Data saved to: {OUTPUT_FILE}")
    logger.info(f"  {len(selected)} stocks passed industry scoring filter")

    if len(selected) > 0:
        disp_cols = [c for c in DISPLAY_COLUMNS if c in selected.columns]
        score_cols = [c for c in selected.columns if c.endswith('_industry_score') and c != 'industry_score']
        disp_cols += score_cols
        logger.info("")
        logger.info("=" * DIVIDER_WIDTH)
        logger.info("Qualified stocks (sorted by total score):")
        logger.info("=" * DIVIDER_WIDTH)
        preview = selected[disp_cols].head(DISPLAY_HEAD_LIMIT).to_string(index=False)
        logger.info(preview)


def screen_stocks_industry():
    """多因子选股 - 筛选2（行业打分制）。"""
    logger.info("Multi-factor screening - Filter 2 (Industry Scoring)")
    logger.info(f"  Criteria: 5 metrics x {SCORE_MIN_VAL}~{SCORE_MAX_VAL} score (by industry ranking), total >= {SCORE_MIN}")
    logger.info("-" * DIVIDER_WIDTH)

    df = _load_input()
    if df is None:
        return None

    df = add_industry_percentile(df)
    df = add_industry_score(df)

    mask = (df['industry_score'] >= SCORE_MIN) & df['industry_score'].notna()
    logger.info(f"  Scored: total >= {SCORE_MIN} (each 1~5, range 5~25): {mask.sum()} stocks remain")

    selected = df[mask].copy()
    selected = selected.sort_values('industry_score', ascending=False).reset_index(drop=True)

    _save_results(selected)

    stats = industry_distribution_stats(df)
    if stats is not None:
        logger.info("")
        logger.info("=" * DIVIDER_WIDTH)
        logger.info("Industry distribution stats (full market):")
        logger.info("=" * DIVIDER_WIDTH)
        pd.set_option('display.max_columns', DISPLAY_MAX_COLUMNS)
        pd.set_option('display.width', DISPLAY_WIDTH)
        logger.info(stats.to_string())

    if ENABLE_VISUALIZATION:
        logger.info("")
        logger.info("Generating industry distribution charts...")
        save_industry_visualization(df, VIZ_OUTPUT_DIR)

    return OUTPUT_FILE


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO, format='%(message)s')
    result = screen_stocks_industry()

    if result:
        logger.info("=" * DIVIDER_WIDTH)
        logger.info("Industry screening completed successfully")
        logger.info(f"  Output: {result}")
        logger.info("=" * DIVIDER_WIDTH)
    else:
        logger.error("Industry screening failed")