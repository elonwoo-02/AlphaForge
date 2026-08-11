# -*- coding: utf-8 -*-
"""
从 QMT / miniQMT 下载全市场 A 股综合财务数据。

遍历指定板块内所有股票，下载资产负债表、利润表、现金流量表、
每股指标和股本结构数据，提取核心财务指标，同时获取股票名称和申万一级行业，
汇总保存为 CSV 至 fetch_data/ 子目录，供多因子筛选脚本使用。

运行前提：
    - 已启动 miniQMT 客户端
    - 已安装 xtquant（pip install xtquant）

默认参数：
    板块：沪深A股
    日期范围：20150101 ~ 今日
    并发线程：{NUM_WORKERS}
    输出文件：fetch_data/stock_fina_pool_QMT.csv
"""
import sys
import time
import logging
from datetime import datetime, date
from pathlib import Path
from concurrent.futures import ThreadPoolExecutor, as_completed

import pandas as pd
from xtquant import xtdata

logger = logging.getLogger(__name__)

# ============ 配置常量 ============
NUM_WORKERS = 8                # 并发下载线程数
SECTOR = '沪深A股'             # 股票池板块
DATA_START = '20150101'        # 财务数据起始日期
DATA_END = date.today().strftime('%Y%m%d')

DATA_DIR = Path(__file__).resolve().parent / "fetch_data"
OUTPUT_FILE = DATA_DIR / "stock_fina_pool_QMT.csv"

TABLE_LIST = ['Balance', 'Income', 'CashFlow', 'PershareIndex', 'Capital']

DIV_ROUND_DECIMALS = 4
PERCENT_MULTIPLIER = 100
GROSSPROFIT_ROUND_DECIMALS = 2

# QMT下载为异步操作，需轮询等待
MAX_DOWNLOAD_WAIT_ATTEMPTS = 60  # 最大轮询次数（= 最大等待秒数）
DOWNLOAD_WAIT_INTERVAL = 0.2     # 轮询间隔（秒）
POST_DOWNLOAD_SLEEP = 0.3        # 全部下载完成后额外等待（数据写入缓存）

TIMETAG_STR_LENGTH = 8
TIMETAG_NS_THRESHOLD = 1e12      # > 1e12 视为微秒级时间戳
TIMETAG_MS_DIVISOR = 1000        # 微秒转毫秒

DIVIDER_WIDTH = 50
FAILED_DISPLAY_LIMIT = 10
SECTOR_HINT_DISPLAY_LIMIT = 15

CSV_COLUMNS_ORDER = [
    'stock_code', 'stock_name', 'industry', 'end_date', 'roe', 'netprofit_yoy',
    'grossprofit_margin', 'debt_to_assets', 'current_ratio', 'operating_cashflow',
    'ocf_to_revenue', 'ocf_to_profit', 'net_profit', 'revenue', 'eps', 'bps',
    'roa', 'netprofit_margin', 'quick_ratio', 'assets_turn', 'total_assets', 'total_equity',
]


def normalize_timetag(ts_val):
    """将 xtquant 的 m_timetag 转换为 YYYYMMDD 字符串。"""
    if ts_val is None:
        return None
    s = str(ts_val).strip()
    if len(s) == TIMETAG_STR_LENGTH and s.isdigit():
        return s
    try:
        v = float(s)
        if v == 0:
            return None
        if v > TIMETAG_NS_THRESHOLD:
            v = v / TIMETAG_MS_DIVISOR
        return datetime.fromtimestamp(v).strftime('%Y%m%d')
    except (OSError, ValueError, TypeError):
        return None


def get_field(record, field_names, default=None):
    """从记录字典中按优先级获取字段值。"""
    for name in field_names:
        val = record.get(name)
        if val is not None:
            return val
    return default


def safe_divide(a, b):
    """安全除法，b 为 0 时返回 None。"""
    if a is None or b is None:
        return None
    a, b = float(a), float(b)
    if b == 0:
        return None
    return round(a / b, DIV_ROUND_DECIMALS)


def safe_divide_pct(a, b):
    """安全除法并转为百分比。"""
    if a is None or b is None:
        return None
    a, b = float(a), float(b)
    if b == 0:
        return None
    return round(a / b * PERCENT_MULTIPLIER, DIV_ROUND_DECIMALS)


def build_period_map(data_list):
    """将财务数据列表转换为 {报告期日期: 记录字典} 的映射。"""
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


def _compute_profitability_metrics(ps, inc):
    """计算盈利能力指标。"""
    eps = get_field(ps, ['s_fa_eps_basic'])
    bps = get_field(ps, ['s_fa_bps'])
    ocfps = get_field(ps, ['s_fa_ocfps'])

    revenue = get_field(inc, ['revenue', 'operating_revenue', 'revenue_inc'])
    net_profit = get_field(inc, ['net_profit_incl_min_int_inc', 'net_profit_excl_min_int_inc'])
    operating_cost = get_field(inc, ['cost_of_goods_sold', 'total_operating_cost', 'total_expense'])

    grossprofit_margin = get_field(ps, ['sales_gross_profit'])
    if grossprofit_margin is None and revenue is not None and operating_cost is not None:
        r, c = float(revenue), float(operating_cost)
        if r > 0:
            grossprofit_margin = round(
                (r - c) / r * PERCENT_MULTIPLIER, GROSSPROFIT_ROUND_DECIMALS
            )

    roe = get_field(ps, ['du_return_on_equity', 'equity_roe', 'net_roe'])
    netprofit_margin = safe_divide_pct(net_profit, revenue)

    return {
        'eps': eps,
        'bps': bps,
        'ocfps': ocfps,
        'grossprofit_margin': grossprofit_margin,
        'netprofit_margin': netprofit_margin,
        'roe': roe,
        'revenue': revenue,
        'net_profit': net_profit,
    }


def _compute_solvency_metrics(bal, net_profit):
    """计算偿债能力与盈利指标。"""
    total_assets = get_field(bal, ['tot_assets'])
    total_liab = get_field(bal, ['tot_liab'])
    total_equity = get_field(bal, ['total_equity', 'tot_shrhldr_eqy_incl_min_int'])
    current_assets = get_field(bal, ['total_current_assets'])
    current_liab = get_field(bal, ['total_current_liability'])
    inventory = get_field(bal, ['inventories'])

    debt_to_assets = safe_divide_pct(total_liab, total_assets)
    current_ratio = safe_divide(current_assets, current_liab)

    quick_ratio = None
    if current_assets is not None and inventory is not None and current_liab is not None:
        quick_ratio = safe_divide(float(current_assets) - float(inventory), current_liab)

    roa = safe_divide_pct(net_profit, total_assets)

    return {
        'total_assets': total_assets,
        'total_liab': total_liab,
        'total_equity': total_equity,
        'debt_to_assets': debt_to_assets,
        'current_ratio': current_ratio,
        'quick_ratio': quick_ratio,
        'roa': roa,
    }


def _compute_cashflow_metrics(cf, revenue, net_profit):
    """计算现金流相关指标。"""
    operating_cashflow = get_field(cf, ['net_cash_flows_oper_act'])

    ocf_to_revenue = safe_divide_pct(operating_cashflow, revenue)
    ocf_to_profit = safe_divide(operating_cashflow, net_profit)

    return {
        'operating_cashflow': operating_cashflow,
        'ocf_to_revenue': ocf_to_revenue,
        'ocf_to_profit': ocf_to_profit,
    }


def extract_all_periods(data, stock_code):
    """提取该股票所有报告期的综合财务指标。"""
    stock_data = data.get(stock_code, {})
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

    records = []
    for period in all_periods:
        ps = pershare_map.get(period, {})
        bal = balance_map.get(period, {})
        inc = income_map.get(period, {})
        cf = cashflow_map.get(period, {})
        cap = capital_map.get(period, {})

        metrics = {}
        metrics.update(_compute_profitability_metrics(ps, inc))
        metrics.update(_compute_solvency_metrics(bal, metrics.get('net_profit')))
        metrics.update(_compute_cashflow_metrics(
            cf, metrics.get('revenue'), metrics.get('net_profit')
        ))
        metrics['assets_turn'] = safe_divide(metrics.get('revenue'), metrics.get('total_assets'))
        metrics['end_date'] = period
        records.append(metrics)

    return records


def calc_netprofit_yoy(records):
    """用年报数据计算最新一期净利润同比增长率。"""
    if not records:
        return None
    annual = [r for r in records if str(r.get('end_date', '')).endswith('1231')]
    if len(annual) < 2:
        return None
    annual = sorted(annual, key=lambda x: x['end_date'])
    profits = [float(r['net_profit']) for r in annual if r.get('net_profit') is not None]
    if len(profits) < 2:
        return None
    s = pd.Series(profits)
    yoy = s.pct_change().iloc[-1] * PERCENT_MULTIPLIER
    return round(yoy, GROSSPROFIT_ROUND_DECIMALS)


def get_stock_industry_map():
    """获取股票 -> 申万一级行业 映射。"""
    stock_to_industry = {}
    try:
        all_sectors = xtdata.get_sector_list()
        sw1_sectors = [
            s for s in all_sectors
            if str(s).upper().startswith('SW1') and '加权' not in str(s)
        ]
        for sector in sw1_sectors:
            stocks = xtdata.get_stock_list_in_sector(sector)
            if stocks:
                for stk in stocks:
                    if '.' in str(stk):
                        stock_to_industry[stk] = sector
    except Exception as e:
        logger.warning(f"Industry mapping error: {e}")
    return stock_to_industry


def get_stock_name(stock_code):
    """获取股票名称。"""
    try:
        detail = xtdata.get_instrument_detail(stock_code)
        if detail:
            return detail.get('InstrumentName', '') or ''
    except Exception:
        pass
    return ''


def download_one_stock(stock_code, industry_map=None):
    """下载单只股票的财务数据并提取最新一期指标（含 netprofit_yoy）。"""
    done_count = [0]

    def on_done(_data):
        done_count[0] += 1

    for table_name in TABLE_LIST:
        xtdata.download_financial_data2(
            stock_list=[stock_code],
            table_list=[table_name],
            start_time=DATA_START,
            end_time=DATA_END,
            callback=on_done
        )

    for _ in range(MAX_DOWNLOAD_WAIT_ATTEMPTS):
        if done_count[0] >= len(TABLE_LIST):
            break
        time.sleep(DOWNLOAD_WAIT_INTERVAL)

    time.sleep(POST_DOWNLOAD_SLEEP)

    data = xtdata.get_financial_data(
        stock_list=[stock_code],
        table_list=TABLE_LIST,
        start_time=DATA_START,
        end_time=DATA_END,
        report_type='report_time'
    )

    if not data or stock_code not in data:
        return None

    records = extract_all_periods(data, stock_code)
    if not records:
        return None

    records = sorted(records, key=lambda x: x['end_date'])
    latest = records[-1].copy()
    latest['netprofit_yoy'] = calc_netprofit_yoy(records)
    latest['stock_code'] = stock_code
    latest['stock_name'] = get_stock_name(stock_code)
    latest['industry'] = (industry_map or {}).get(stock_code, '')
    return latest


def _connect_qmt():
    """连接 QMT。"""
    logger.info("Connecting to QMT fetch_data service...")
    xtdata.connect()
    logger.info("Connected to QMT fetch_data service")


def _get_stock_list():
    """获取板块内的股票列表。"""
    logger.info("Fetching stock list...")
    stock_list = xtdata.get_stock_list_in_sector(SECTOR)
    if not stock_list:
        sectors = xtdata.get_sector_list()
        logger.error(f"Sector '{SECTOR}' returned empty list")
        if sectors:
            hs = [s for s in sectors if '沪深' in str(s)][:SECTOR_HINT_DISPLAY_LIMIT]
            logger.info(f"  Sectors containing '沪深': {hs}")
        return None

    stock_list = [c for c in stock_list if '.' in str(c)]
    return stock_list


def _run_download(stock_list, industry_map):
    """多线程下载股票财务数据。"""
    total = len(stock_list)
    logger.info(f"Total {total} stocks to download")

    pool = []
    failed = []
    start_time = time.time()

    def _download(code):
        """线程池调用包装，异常时返回 (code, None)。"""
        try:
            row = download_one_stock(code, industry_map)
            return code, row
        except Exception:
            return code, None

    logger.info(f"Downloading in parallel ({NUM_WORKERS} threads)...")
    with ThreadPoolExecutor(max_workers=NUM_WORKERS) as executor:
        futures = {executor.submit(_download, code): code for code in stock_list}
        done = 0
        for future in as_completed(futures):
            code, row = future.result()
            if row:
                pool.append(row)
            else:
                failed.append(code)
            done += 1
            elapsed = time.time() - start_time
            pct = done * PERCENT_MULTIPLIER / total
            speed = done / elapsed if elapsed > 0 else 0
            eta = (total - done) / speed if speed > 0 else 0
            sys.stdout.write(
                f"\r  Progress {done}/{total} ({pct:.1f}%) "
                f"| {speed:.1f} stocks/sec | ETA {eta:.0f}s "
                f"| Success {len(pool)}"
            )
            sys.stdout.flush()

    elapsed = time.time() - start_time
    logger.info(f"  Download completed in {elapsed:.1f}s")
    return pool, failed


def _build_dataframe(pool):
    """将下载结果组装为 DataFrame 并固化列顺序。"""
    df = pd.DataFrame(pool)
    for col in CSV_COLUMNS_ORDER:
        if col not in df.columns:
            df[col] = None
    df = df[[c for c in CSV_COLUMNS_ORDER if c in df.columns]]
    return df


def _save_results(df, pool, failed):
    """保存 CSV 并打印结果汇总。"""
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    df.to_csv(OUTPUT_FILE, index=False, encoding='utf-8-sig')
    logger.info(f"Data saved to: {OUTPUT_FILE}")
    logger.info(f"  Success: {len(pool)}, Failed: {len(failed)}")

    if failed:
        logger.warning(f"Failed stocks (first {FAILED_DISPLAY_LIMIT}): {failed[:FAILED_DISPLAY_LIMIT]}")


def download_financial_pool():
    """下载全市场股票财务数据。"""
    logger.info(f"Multi-factor screening - Financial fetch_data download (QMT)")
    logger.info(f"  Sector: {SECTOR}")
    logger.info(f"  Date range: {DATA_START} ~ {DATA_END}")
    logger.info("-" * DIVIDER_WIDTH)

    try:
        _connect_qmt()
        stock_list = _get_stock_list()
        if stock_list is None:
            return None

        logger.info("Fetching industry mapping...")
        industry_map = get_stock_industry_map()
        logger.info(f"  Mapped {len(industry_map)} stocks to industries")

        pool, failed = _run_download(stock_list, industry_map)

        if not pool:
            logger.error("Failed to extract any stock fetch_data")
            return None

        df = _build_dataframe(pool)
        _save_results(df, pool, failed)
        return OUTPUT_FILE

    except Exception:
        logger.exception("Error during fetch_data download")
        return None


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO, format='%(message)s')
    result = download_financial_pool()

    if result:
        logger.info("=" * DIVIDER_WIDTH)
        logger.info("Financial fetch_data download completed successfully")
        logger.info(f"  Output: {result}")
        logger.info("=" * DIVIDER_WIDTH)
    else:
        logger.error("Financial fetch_data download failed")