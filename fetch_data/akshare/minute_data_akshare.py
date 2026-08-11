# -*- coding: utf-8 -*-
"""
从 AkShare 下载分钟级 K 线数据。

下载贵州茅台（600519）指定交易日的分钟数据，保存为 CSV 至 fetch_data/ 子目录。

运行前提：
    - 已安装 akshare（pip install akshare）

注意：AkShare 分钟数据仅支持最近 5 个交易日（数据来源：东方财富）。

默认参数：
    股票：600519
    目标日期：2026-08-11（全天）
    周期：1（也支持 5、15、30、60）
    输出文件：fetch_data/600519_SH_1min_akshare.csv
"""
import logging
import pandas as pd
from pathlib import Path
import akshare as ak

logger = logging.getLogger(__name__)

# ============ 配置常量 ============
STOCK_CODE = '600519'         # 贵州茅台（AkShare格式：纯数字）
STOCK_NAME = '贵州茅台'
STOCK_CODE_FULL = '600519.SH'
TARGET_DATE = '2026-08-11'    # 目标日期
PERIOD = '1'                  # 1分钟（可选：1, 5, 15, 30, 60）
TRADE_START = '09:30:00'      # A股开盘时间
TRADE_END = '15:00:00'        # A股收盘时间

COLUMN_MAP = {
    '时间': 'datetime',
    '开盘': 'open',
    '收盘': 'close',
    '最高': 'high',
    '最低': 'low',
    '成交量': 'volume',
    '成交额': 'amount',
    '最新价': 'latest',
}
KEEP_COLUMNS = ['datetime', 'open', 'high', 'low', 'close', 'volume', 'amount']

DATA_DIR = Path(__file__).resolve().parent / "fetch_data"


def _download_raw():
    """调用 ak.stock_zh_a_hist_min_em 下载分钟数据"""
    start_dt = f"{TARGET_DATE} {TRADE_START}"
    end_dt = f"{TARGET_DATE} {TRADE_END}"
    df = ak.stock_zh_a_hist_min_em(
        symbol=STOCK_CODE,
        start_date=start_dt,
        end_date=end_dt,
        period=PERIOD,
        adjust='',
    )
    return df


def _fetch_and_parse():
    """列名转换、时间转换、排序、筛选保留列"""
    raw = _download_raw()
    if not has_valid_data(raw):
        return None

    df = raw.rename(columns=COLUMN_MAP)
    df['datetime'] = pd.to_datetime(df['datetime'])
    df = df.sort_values('datetime').reset_index(drop=True)
    df = df[[c for c in KEEP_COLUMNS if c in df.columns]]
    return df


def _save_and_report(df):
    """保存 CSV 并打印预览与统计"""
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    output_file = DATA_DIR / f'{STOCK_CODE_FULL.replace(".", "_")}_1min_akshare.csv'
    df.to_csv(output_file, index=False, encoding='utf-8-sig')

    logger.info(f"Data saved to: {output_file}")

    logger.info("Data preview (first 10 rows):")
    logger.info(df.head(10).to_string(index=False))
    logger.info("Data preview (last 5 rows):")
    logger.info(df.tail(5).to_string(index=False))

    logger.info("Data summary:")
    logger.info(f"  Total records: {len(df)}")
    logger.info(f"  Close range: {df['close'].min():.2f} - {df['close'].max():.2f}")
    if 'volume' in df.columns:
        logger.info(f"  Volume range: {df['volume'].min():,.0f} - {df['volume'].max():,.0f}")

    return output_file


def has_valid_data(data):
    """检查获取到的数据是否包含有效记录"""
    return data is not None and not data.empty


def download_minute_data():
    """下载指定日期的分钟 K 线数据"""
    logger.info(f"Stock: {STOCK_NAME} ({STOCK_CODE})")
    logger.info(f"Date: {TARGET_DATE}")
    logger.info(f"Period: {PERIOD}")
    logger.info("-" * 60)
    logger.info("Note: AkShare minute fetch_data is only available for the most recent 5 trading days")

    try:
        df = _fetch_and_parse()
        if df is None:
            logger.error("No minute fetch_data retrieved (target date may exceed 5 trading day limit or be a non-trading day)")
            return None

        logger.info(f"Retrieved {len(df)} minute bars")
        logger.info(f"Time range: {df['datetime'].iloc[0]} to {df['datetime'].iloc[-1]}")

        output_file = _save_and_report(df)
        return output_file

    except Exception:
        logger.exception("Error during fetch_data download")
        return None


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO, format='%(message)s')
    result = download_minute_data()

    if result:
        logger.info("=" * 60)
        logger.info("Minute fetch_data download completed successfully")
        logger.info(f"Output: {result}")
        logger.info("=" * 60)