# -*- coding: utf-8 -*-
"""
从 Tushare Pro 下载综合财务数据。

下载贵州茅台（600519.SH）的综合财务指标（来自 fina_indicator 接口），
保存为 CSV 至 data/ 子目录。

运行前提：
    - 已安装 tushare（pip install tushare）
    - 已设置环境变量 TUSHARE_TOKEN
    - Token 需 2000 积分（免费注册仅 120 积分）

默认参数：
    股票：600519.SH
    输出文件：data/600519_SH_fina_tushare.csv
"""
import logging
import os
import pandas as pd
from pathlib import Path
import tushare as ts

logger = logging.getLogger(__name__)

# ============ 配置常量 ============
STOCK_CODE = '600519.SH'
STOCK_NAME = '贵州茅台'

DATA_DIR = Path(__file__).resolve().parent / "data"

# Tushare fina_indicator 接口字段列表
# 文档: https://tushare.pro/document/2?doc_id=79
FINA_FIELDS = ",".join([
    "ts_code", "ann_date", "end_date",

    # 每股指标
    "eps", "dt_eps", "bps", "ocfps", "undist_profit_ps", "total_revenue_ps",

    # 盈利能力
    "roe", "roe_waa", "roe_dt", "roa", "grossprofit_margin", "netprofit_margin",
    "profit_to_gr", "op_of_gr", "ebit_of_gr",

    # 偿债能力
    "debt_to_assets", "current_ratio", "quick_ratio", "cash_ratio",

    # 成长能力
    "netprofit_yoy", "dt_netprofit_yoy", "or_yoy", "op_yoy", "ocf_yoy",
    "bps_yoy", "assets_yoy", "eqt_yoy",

    # 营运能力
    "assets_turn", "inv_turn", "ar_turn", "ca_turn", "fa_turn",
    "invturn_days", "arturn_days",

    # 现金流
    "fcff", "fcfe", "salescash_to_or", "ocf_to_or", "ocf_to_opincome",

    # 收益质量
    "op_income", "ebit", "ebitda",
])

KEY_INDICATORS = [
    ("End Date",           'end_date'),
    ("Basic EPS",          'eps'),
    ("Net Assets per Share", 'bps'),
    ("ROE (%)",            'roe'),
    ("ROA (%)",            'roa'),
    ("Gross Profit Margin (%)", 'grossprofit_margin'),
    ("Net Profit Margin (%)",   'netprofit_margin'),
    ("Debt-to-Assets (%)", 'debt_to_assets'),
    ("Current Ratio",      'current_ratio'),
    ("Net Profit YoY (%)", 'netprofit_yoy'),
    ("Revenue YoY (%)",    'or_yoy'),
    ("Asset Turnover",     'assets_turn'),
    ("Inventory Turnover", 'inv_turn'),
    ("Operating CF per Share", 'ocfps'),
]


def _get_pro():
    """初始化 Tushare Pro（需环境变量 TUSHARE_TOKEN）"""
    token = os.environ.get("TUSHARE_TOKEN")
    if not token or not str(token).strip():
        raise RuntimeError("未设置环境变量 TUSHARE_TOKEN，请先设置后再运行")
    ts.set_token(str(token).strip())
    return ts.pro_api()


def _fetch_and_parse():
    """获取综合财务指标并排序"""
    pro = _get_pro()
    df = pro.fina_indicator(ts_code=STOCK_CODE, fields=FINA_FIELDS)
    if not has_valid_data(df):
        return None
    df = df.sort_values('end_date').reset_index(drop=True)
    return df


def _save_and_report(df):
    """保存 CSV 并打印预览与关键指标"""
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    output_file = DATA_DIR / f'{STOCK_CODE.replace(".", "_")}_fina_tushare.csv'
    df.to_csv(output_file, index=False, encoding='utf-8-sig')

    logger.info(f"Data saved to: {output_file}")

    logger.info("=" * 60)
    logger.info("Data preview (recent 3 periods):")
    logger.info("=" * 60)
    recent = df.tail(3).set_index('end_date').T
    logger.info(recent.to_string())

    logger.info("=" * 60)
    logger.info("Key indicators (latest period):")
    logger.info("=" * 60)
    latest = df.iloc[-1]
    for name, field in KEY_INDICATORS:
        val = latest.get(field)
        logger.info(f"  {name:<28s}  {val}")

    logger.info(f"\nColumns ({len(df.columns)} fields):")
    for i, col in enumerate(df.columns):
        logger.info(f"  {i+1:>2d}. {col}")

    return output_file


def has_valid_data(data):
    """检查获取到的数据是否包含有效记录"""
    return data is not None and not data.empty


def download_financial_data():
    """下载贵州茅台的综合财务数据"""
    logger.info(f"Stock: {STOCK_NAME} ({STOCK_CODE})")
    logger.info(f"Requested fields: {len(FINA_FIELDS.split(','))}")
    logger.info("-" * 60)

    try:
        df = _fetch_and_parse()
        if df is None:
            logger.error("Unable to retrieve financial data, check token permissions (requires 2000 credits)")
            return None

        logger.info(f"Retrieved {len(df)} periods of financial data")
        logger.info(f"Report range: {df['end_date'].iloc[0]} to {df['end_date'].iloc[-1]}")

        output_file = _save_and_report(df)
        return output_file

    except Exception:
        logger.exception("Error during data download")
        return None


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO, format='%(message)s')
    result = download_financial_data()

    if result:
        logger.info("=" * 60)
        logger.info("Financial data download completed successfully")
        logger.info(f"Output: {result}")
        logger.info("=" * 60)