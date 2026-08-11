# -*- coding: utf-8 -*-
"""
从 QMT / miniQMT 下载综合财务数据。

下载贵州茅台（600519.SH）的资产负债表、利润表、现金流量表、
每股指标和股本结构数据，提取核心财务指标，保存为 CSV 至 data/ 子目录。

运行前提：
    - 已启动 miniQMT 客户端
    - 已安装 xtquant（pip install xtquant）

默认参数：
    股票：600519.SH
    日期范围：20140101 ~ 20261231
    输出文件：data/600519_SH_fina_QMT.csv
"""
import time
import logging
from datetime import datetime
import pandas as pd
from pathlib import Path
from xtquant import xtdata

logger = logging.getLogger(__name__)

# ============ 配置常量 ============
STOCK_CODE = '600519.SH'  # 贵州茅台（QMT格式）
STOCK_NAME = '贵州茅台'
DATA_START = '20140101'   # 财务数据起始日期
DATA_END = '20261231'     # 财务数据截止日期

DATA_DIR = Path(__file__).resolve().parent / "data"

# QMT财务数据下载为异步操作
TABLE_LIST = ['Balance', 'Income', 'CashFlow', 'PershareIndex', 'Capital']
DOWNLOAD_TIMEOUT_SECONDS = 60  # 最大等待秒数（= 轮询次数 × 间隔）
POLL_INTERVAL_SECONDS = 1       # 轮询间隔（秒）
WRITE_WAIT_SECONDS = 1          # 全部下载完成后额外等待（数据写入缓存）


def normalize_timetag(ts_val):
    """
    将xtquant的m_timetag转换为日期字符串（如 20241231）。
    xtquant返回的m_timetag可能是字符串或数值型时间戳。
    """
    if ts_val is None:
        return None
    s = str(ts_val).strip()
    if len(s) == 8 and s.isdigit():
        return s
    try:
        v = float(s)
        if v == 0:
            return None
        if v > 1e12:
            v = v / 1000
        return datetime.fromtimestamp(v).strftime('%Y%m%d')
    except (OSError, ValueError, TypeError):
        return None


def get_field(record, field_names, default=None):
    """
    从记录字典中获取字段值，支持多个候选字段名。
    因xtquant不同版本的字段名可能不同，按优先级依次尝试。
    """
    for name in field_names:
        val = record.get(name)
        if val is not None:
            return val
    return default


def safe_divide(a, b, pct=False):
    """安全除法，b为0时返回None。pct=True时结果乘以100。"""
    if a is None or b is None:
        return None
    a, b = float(a), float(b)
    if b == 0:
        return None
    result = a / b
    if pct:
        result *= 100
    return round(result, 4)


def build_period_map(data_list):
    """
    将xtquant返回的财务数据列表转换为 {报告期日期: 记录字典} 的映射。
    兼容DataFrame和list两种返回格式。
    """
    period_map = {}
    if isinstance(data_list, pd.DataFrame):
        for _, row in data_list.iterrows():
            period_date = normalize_timetag(row.get('m_timetag'))
            if period_date:
                period_map[period_date] = row.to_dict()
    elif isinstance(data_list, list):
        for rec in data_list:
            if isinstance(rec, dict):
                period_date = normalize_timetag(rec.get('m_timetag'))
                if period_date:
                    period_map[period_date] = rec
    return period_map


def extract_all_periods(data):
    """
    从xtquant返回的单只股票财务数据中，提取所有报告期的综合财务指标。

    参数：
      data: xtdata.get_financial_data 返回的 {stock: {table: data}} 中该股票的部分

    返回：按报告期排列的记录列表
    """
    stock_data = data.get(STOCK_CODE, {})
    if not stock_data:
        return []

    pershare_map = build_period_map(stock_data.get('PershareIndex', []))
    balance_map = build_period_map(stock_data.get('Balance', []))
    income_map = build_period_map(stock_data.get('Income', []))
    cashflow_map = build_period_map(stock_data.get('CashFlow', []))
    capital_map = build_period_map(stock_data.get('Capital', []))

    all_periods = sorted(set(
        list(pershare_map.keys()) +
        list(balance_map.keys()) +
        list(income_map.keys()) +
        list(cashflow_map.keys())
    ))

    logger.info(f"Found {len(all_periods)} reporting periods")
    if all_periods:
        logger.info(f"  Range: {all_periods[0]} to {all_periods[-1]}")

    # 打印最新报告期的可用字段名（用于调试字段缺失问题）
    if all_periods:
        first_period = all_periods[-1]
        logger.debug(f"  [Field reference] Available fields for latest period {first_period}:")
        for table_name, table_map in [
            ('PershareIndex', pershare_map),
            ('Balance', balance_map),
            ('Income', income_map),
            ('CashFlow', cashflow_map),
        ]:
            rec = table_map.get(first_period, {})
            fields = [k for k in rec.keys() if not k.startswith('m_')]
            if fields:
                logger.debug(
                    f"    {table_name}: {', '.join(fields[:15])}"
                    f"{'...' if len(fields) > 15 else ''}"
                )

    records = []
    for period in all_periods:
        ps = pershare_map.get(period, {})
        bal = balance_map.get(period, {})
        inc = income_map.get(period, {})
        cf = cashflow_map.get(period, {})
        cap = capital_map.get(period, {})

        eps = get_field(ps, ['s_fa_eps_basic'])
        bps = get_field(ps, ['s_fa_bps'])
        ocfps = get_field(ps, ['s_fa_ocfps'])
        undist_ps = get_field(ps, ['s_fa_undistributedps'])

        roe = get_field(ps, ['du_return_on_equity', 'equity_roe', 'net_roe'])
        grossprofit_margin_ps = get_field(ps, ['sales_gross_profit'])

        revenue = get_field(inc, ['revenue', 'operating_revenue', 'revenue_inc'])
        net_profit = get_field(inc, ['net_profit_incl_min_int_inc', 'net_profit_excl_min_int_inc'])
        operating_profit = get_field(inc, ['oper_profit'])
        operating_cost = get_field(inc, ['cost_of_goods_sold', 'total_operating_cost', 'total_expense'])

        grossprofit_margin = grossprofit_margin_ps
        if grossprofit_margin is None and revenue and operating_cost:
            revenue_f = float(revenue)
            if revenue_f > 0:
                grossprofit_margin = safe_divide(
                    revenue_f - float(operating_cost), revenue_f, pct=True
                )

        netprofit_margin = safe_divide(net_profit, revenue, pct=True)
        op_margin = safe_divide(operating_profit, revenue, pct=True)

        total_assets = get_field(bal, ['tot_assets'])
        total_liab = get_field(bal, ['tot_liab'])
        total_equity = get_field(bal, ['total_equity', 'tot_shrhldr_eqy_incl_min_int'])
        current_assets = get_field(bal, ['total_current_assets'])
        current_liab = get_field(bal, ['total_current_liability'])
        inventory = get_field(bal, ['inventories'])
        monetary_funds = get_field(bal, ['cash_equivalents'])

        debt_to_assets = safe_divide(total_liab, total_assets, pct=True)
        current_ratio = safe_divide(current_assets, current_liab)
        quick_ratio = None
        if current_assets and inventory and current_liab:
            quick_ratio = safe_divide(float(current_assets) - float(inventory), current_liab)

        roa = safe_divide(net_profit, total_assets, pct=True)
        if roe is None and net_profit and total_equity:
            roe = safe_divide(net_profit, total_equity, pct=True)

        assets_turn = safe_divide(revenue, total_assets)

        operating_cashflow = get_field(cf, ['net_cash_flows_oper_act'])
        investing_cashflow = get_field(cf, ['net_cash_flows_inv_act'])
        financing_cashflow = get_field(cf, ['net_cash_flows_fnc_act'])

        ocf_to_revenue = safe_divide(operating_cashflow, revenue, pct=True)
        ocf_to_profit = safe_divide(operating_cashflow, net_profit)

        total_shares = get_field(cap, ['totalShares', 'totalCapital', 'total_shares'])

        record = {
            'end_date': period,
            'eps': eps,
            'bps': bps,
            'ocfps': ocfps,
            'undist_profit_ps': undist_ps,
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
            'total_assets': total_assets,
            'total_liab': total_liab,
            'total_equity': total_equity,
            'revenue': revenue,
            'net_profit': net_profit,
            'monetary_funds': monetary_funds,
            'total_shares': total_shares,
        }
        records.append(record)

    return records


def _connect_qmt():
    """连接QMT数据服务"""
    xtdata.connect()


def _download_raw():
    """异步下载财务报表数据到本地缓存"""
    downloaded_count = [0]
    total_tables = len(TABLE_LIST)

    def on_download_done(_data):
        downloaded_count[0] += 1
        logger.debug(f"  Downloaded {downloaded_count[0]}/{total_tables} tables")

    for table_name in TABLE_LIST:
        xtdata.download_financial_data2(
            stock_list=[STOCK_CODE],
            table_list=[table_name],
            start_time=DATA_START,
            end_time=DATA_END,
            callback=on_download_done,
        )

    # QMT异步下载需轮询等待（最多DOWNLOAD_TIMEOUT_SECONDS秒）
    for _ in range(DOWNLOAD_TIMEOUT_SECONDS):
        if downloaded_count[0] >= total_tables:
            break
        time.sleep(POLL_INTERVAL_SECONDS)

    if downloaded_count[0] < total_tables:
        logger.warning(
            f"Only downloaded {downloaded_count[0]}/{total_tables} tables, "
            f"attempting to fetch data anyway"
        )
    else:
        logger.info("All financial tables downloaded")

    time.sleep(WRITE_WAIT_SECONDS)


def _fetch_and_parse():
    """获取财务数据并提取核心财务指标"""
    market_data = xtdata.get_financial_data(
        stock_list=[STOCK_CODE],
        table_list=TABLE_LIST,
        start_time=DATA_START,
        end_time=DATA_END,
        report_type='report_time',
    )

    if not has_valid_data(market_data):
        return None

    records = extract_all_periods(market_data)
    if not records:
        return None

    df = pd.DataFrame(records)
    df = df.sort_values('end_date').reset_index(drop=True)
    return df


def _save_and_report(df):
    """保存CSV并打印数据预览与关键指标"""
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    output_file = DATA_DIR / f'{STOCK_CODE.replace(".", "_")}_fina_QMT.csv'
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
    indicators = [
        ("End Date",                latest.get('end_date')),
        ("Basic EPS",               latest.get('eps')),
        ("Net Assets per Share",    latest.get('bps')),
        ("ROE (%)",                 latest.get('roe')),
        ("ROA (%)",                 latest.get('roa')),
        ("Gross Profit Margin (%)", latest.get('grossprofit_margin')),
        ("Net Profit Margin (%)",   latest.get('netprofit_margin')),
        ("Debt-to-Assets (%)",      latest.get('debt_to_assets')),
        ("Current Ratio",           latest.get('current_ratio')),
        ("Quick Ratio",             latest.get('quick_ratio')),
        ("Asset Turnover",          latest.get('assets_turn')),
        ("Operating CF per Share",  latest.get('ocfps')),
        ("Revenue",                 latest.get('revenue')),
        ("Net Profit",              latest.get('net_profit')),
    ]
    for name, val in indicators:
        logger.info(f"  {name:<28s}  {val}")

    logger.info(f"\nColumns ({len(df.columns)} fields):")
    for i, col in enumerate(df.columns):
        logger.info(f"  {i+1:>2d}. {col}")

    return output_file


def has_valid_data(data):
    """检查获取到的数据是否包含有效的财务数据"""
    return bool(data and STOCK_CODE in data)


def download_financial_data():
    """下载贵州茅台的综合财务数据"""
    logger.info(f"Stock: {STOCK_NAME} ({STOCK_CODE})")
    logger.info(f"Date range: {DATA_START} to {DATA_END}")
    logger.info("-" * 60)

    try:
        _connect_qmt()
        logger.info("Connected to QMT data service")

        _download_raw()
        logger.info("Raw data download finished")

        df = _fetch_and_parse()
        if df is None:
            logger.error("Unable to extract valid financial data")
            return None

        logger.info(f"Extracted {len(df)} periods of financial data")

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