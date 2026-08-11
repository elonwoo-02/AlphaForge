# -*- coding: utf-8 -*-
"""
从 AkShare 下载综合财务数据。

下载贵州茅台（600519）的利润表、资产负债表、现金流量表，
提取并计算核心财务指标，保存为 CSV 至 fetch_data/ 子目录。

运行前提：
    - 已安装 akshare（pip install akshare）

默认参数：
    股票：sh600519（新浪格式）
    输出文件：fetch_data/600519_SH_fina_akshare.csv
"""
import logging
from pathlib import Path

import pandas as pd
import akshare as ak

logger = logging.getLogger(__name__)

# ============================================================
# 常量
# ============================================================
STOCK_CODE_SINA = 'sh600519'   # 贵州茅台（新浪格式：sh/sz + 代码）
STOCK_NAME = '贵州茅台'
STOCK_CODE_FULL = '600519.SH'  # 完整代码（用于输出文件名）

DATA_DIR = Path(__file__).resolve().parent / "fetch_data"

FINANCIAL_REPORTS = [
    ('利润表', 'Income'),
    ('资产负债表', 'Balance'),
    ('现金流量表', 'CashFlow'),
]

KEY_INDICATORS = [
    ('end_date', '报告期'),
    ('eps', '基本每股收益'),
    ('roe', '净资产收益率(%)'),
    ('roa', '总资产报酬率(%)'),
    ('grossprofit_margin', '销售毛利率(%)'),
    ('netprofit_margin', '销售净利率(%)'),
    ('debt_to_assets', '资产负债率(%)'),
    ('current_ratio', '流动比率'),
    ('quick_ratio', '速动比率'),
    ('assets_turn', '总资产周转率'),
    ('revenue', '营业收入'),
    ('net_profit', '净利润'),
    ('operating_cashflow', '经营活动现金流净额'),
    ('ocf_to_profit', '现金流/净利润'),
]


# ============================================================
# 工具函数
# ============================================================

def safe_float(val):
    """安全转换为浮点数"""
    try:
        if val is None or str(val).strip() in ('', '--', 'None', 'nan'):
            return None
        return float(val)
    except (ValueError, TypeError):
        return None


def safe_divide(a, b, pct=False):
    """安全除法，b为0时返回None。pct=True时结果乘以100"""
    if a is None or b is None:
        return None
    a, b = float(a), float(b)
    if b == 0:
        return None
    result = a / b
    if pct:
        result *= 100
    return round(result, 4)


def get_col(row, col_names, default=None):
    """
    从行中获取字段值，支持多个候选列名。
    使用 'in' 进行模糊匹配，避免列名包含额外字符时匹配不上。
    """
    for name in col_names:
        if name in row.index:
            val = safe_float(row[name])
            if val is not None:
                return val
        for col in row.index:
            if name in str(col):
                val = safe_float(row[col])
                if val is not None:
                    return val
    return default


def normalize_date_col(df):
    """标准化日期列为 YYYYMMDD 格式的 _date 列"""
    date_col_name = df.columns[0]
    df = df.copy()
    df['_date'] = df[date_col_name].astype(str).str.replace('-', '').str[:8]
    return df


def has_valid_data(data):
    """检查数据是否非空"""
    return data is not None and len(data) > 0


# ============================================================
# 核心函数
# ============================================================

def _download_raw():
    """下载三大财务报表（利润表、资产负债表、现金流量表）"""
    reports = {}
    for report_name, report_key in FINANCIAL_REPORTS:
        logger.info("Downloading %s ...", report_name)
        df = ak.stock_financial_report_sina(stock=STOCK_CODE_SINA, symbol=report_name)
        logger.info("  %s: %d periods, columns: %s ...", report_name, len(df), df.columns.tolist()[:10])
        reports[report_key] = df
    return reports


def _fetch_and_parse(reports):
    """从原始报表中提取字段并计算财务指标"""
    logger.info("Extracting and computing financial indicators ...")

    df_income = normalize_date_col(reports['Income'])
    df_balance = normalize_date_col(reports['Balance'])
    df_cashflow = normalize_date_col(reports['CashFlow'])

    def build_map(df):
        mapping = {}
        for _, row in df.iterrows():
            period = row['_date']
            if period and len(period) == 8 and period.isdigit():
                mapping[period] = row
        return mapping

    income_map = build_map(df_income)
    balance_map = build_map(df_balance)
    cashflow_map = build_map(df_cashflow)

    all_periods = sorted(set(income_map.keys()) & set(balance_map.keys()))
    logger.info("  Total periods: %d", len(all_periods))

    records = []
    for period in all_periods:
        inc = income_map.get(period)
        bal = balance_map.get(period)
        cf = cashflow_map.get(period)

        # 利润表字段
        revenue = get_col(inc, ['营业收入', '一、营业收入', '一、营业总收入'])
        operating_cost = get_col(inc, ['营业成本', '二、营业总成本', '营业总成本'])
        net_profit = get_col(inc, ['净利润', '五、净利润', '四、净利润'])
        operating_profit = get_col(inc, ['营业利润', '三、营业利润'])
        eps = get_col(inc, ['基本每股收益', '（一）基本每股收益'])

        # 资产负债表字段
        total_assets = get_col(bal, ['资产总计', '资产合计'])
        total_liab = get_col(bal, ['负债合计', '负债总计'])
        total_equity = get_col(bal, ['所有者权益合计', '所有者权益（或股东权益）合计', '股东权益合计', '归属于母公司股东权益合计'])
        current_assets = get_col(bal, ['流动资产合计'])
        current_liab = get_col(bal, ['流动负债合计'])
        inventory = get_col(bal, ['存货'])
        monetary_funds = get_col(bal, ['货币资金'])

        # 现金流量表字段
        operating_cashflow = None
        investing_cashflow = None
        financing_cashflow = None
        if cf is not None:
            operating_cashflow = get_col(cf, ['经营活动产生的现金流量净额'])
            investing_cashflow = get_col(cf, ['投资活动产生的现金流量净额'])
            financing_cashflow = get_col(cf, ['筹资活动产生的现金流量净额'])

        # 计算指标
        grossprofit_margin = safe_divide(revenue - operating_cost, revenue, pct=True)
        netprofit_margin = safe_divide(net_profit, revenue, pct=True)
        op_margin = safe_divide(operating_profit, revenue, pct=True)
        roe = safe_divide(net_profit, total_equity, pct=True)
        roa = safe_divide(net_profit, total_assets, pct=True)
        debt_to_assets = safe_divide(total_liab, total_assets, pct=True)
        current_ratio = safe_divide(current_assets, current_liab)
        quick_ratio = None
        if current_assets and inventory and current_liab:
            quick_ratio = safe_divide(current_assets - inventory, current_liab)
        assets_turn = safe_divide(revenue, total_assets)
        ocf_to_revenue = safe_divide(operating_cashflow, revenue, pct=True)
        ocf_to_profit = safe_divide(operating_cashflow, net_profit)

        record = {
            'end_date': period,
            'eps': eps,
            'roe': roe,
            'roa': roa,
            'grossprofit_margin': grossprofit_margin,
            'netprofit_margin': netprofit_margin,
            'op_margin': op_margin,
            'debt_to_assets': debt_to_assets,
            'current_ratio': current_ratio,
            'quick_ratio': quick_ratio,
            'assets_turn': assets_turn,
            'operating_cashflow': operating_cashflow,
            'investing_cashflow': investing_cashflow,
            'financing_cashflow': financing_cashflow,
            'ocf_to_revenue': ocf_to_revenue,
            'ocf_to_profit': ocf_to_profit,
            'revenue': revenue,
            'net_profit': net_profit,
            'total_assets': total_assets,
            'total_liab': total_liab,
            'total_equity': total_equity,
            'monetary_funds': monetary_funds,
        }
        records.append(record)

    return records


def _save_and_report(df):
    """保存数据到 CSV 并输出预览"""
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    output_file = DATA_DIR / f'{STOCK_CODE_FULL.replace(".", "_")}_fina_akshare.csv'
    df.to_csv(output_file, index=False, encoding='utf-8-sig')
    logger.info("Data saved to: %s", output_file)

    logger.info("=" * 60)
    logger.info("Data preview (recent 3 periods):")
    logger.info("=" * 60)
    recent = df.tail(3).set_index('end_date').T
    logger.info(recent.to_string())

    logger.info("=" * 60)
    logger.info("Key indicators (latest period):")
    logger.info("=" * 60)
    latest = df.iloc[-1]
    for field, label in KEY_INDICATORS:
        val = latest.get(field, '-')
        logger.info(f"  {label:<28s}  {val}")

    logger.info(f"\nColumns ({len(df.columns)} fields):")
    for i, col in enumerate(df.columns):
        logger.info(f"  {i+1:>2d}. {col}")

    return str(output_file)


def download_financial_data():
    """下载贵州茅台的综合财务数据"""
    logger.info("Stock: %s (%s)", STOCK_NAME, STOCK_CODE_SINA)
    logger.info("-" * 60)

    try:
        reports = _download_raw()
        records = _fetch_and_parse(reports)

        if not has_valid_data(records):
            logger.error("No financial indicators extracted")
            return None

        df = pd.DataFrame(records)
        df = df.sort_values('end_date').reset_index(drop=True)
        logger.info("Successfully extracted %d periods of financial fetch_data", len(df))

        output_file = _save_and_report(df)
        return output_file

    except Exception:
        logger.exception("Error downloading financial fetch_data")
        return None


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO, format='%(message)s')
    result = download_financial_data()

    if result:
        logger.info("=" * 60)
        logger.info("Financial fetch_data download completed successfully")
        logger.info(f"Output: {result}")
        logger.info("=" * 60)