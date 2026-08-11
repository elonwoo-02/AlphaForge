# -*- coding: utf-8 -*-
"""
从 QMT / miniQMT 下载日线 OHLCV 数据。

下载贵州茅台（600519.SH）的前复权日线数据，保存为 CSV 至 fetch_data/ 子目录。

运行前提：
    - 已启动 miniQMT 客户端
    - 已安装 xtquant（pip install xtquant）

默认参数：
    股票：600519.SH
    日期范围：20240101 ~ 20260811
    输出文件：fetch_data/600519_SH_daily_QMT.csv
"""
import time
import logging
import pandas as pd
from pathlib import Path
from xtquant import xtdata

logger = logging.getLogger(__name__)

# ============ 配置常量 ============
STOCK_CODE = '600519.SH'  # 贵州茅台股票代码
STOCK_NAME = '贵州茅台'
DATA_START = '20240101'   # 数据开始日期
DATA_END = '20260811'     # 数据结束日期
DATA_DIR = Path(__file__).resolve().parent / "fetch_data"
DATE_FORMAT = '%Y%m%d'  # QMT日期格式，用于时间戳解析
WRITE_WAIT_SECONDS = 2  # QMT下载为异步操作，需等待数据写入本地缓存
DAILY_FIELDS = ['open', 'high', 'low', 'volume']  # xtdata.get_market_data返回的OHLCV字段


def _download_raw():
    """调用xtdata下载历史数据到本地缓存"""
    xtdata.download_history_data(
        stock_code=STOCK_CODE,
        period='1d',
        start_time=DATA_START,
    )
    time.sleep(WRITE_WAIT_SECONDS)


def _fetch_and_parse():
    """获取历史数据并构建清洗后的DataFrame"""
    market_data = xtdata.get_market_data(
        stock_list=[STOCK_CODE],
        period='1d',
        start_time=DATA_START,
        end_time='',
        count=-1,
        dividend_type='front',  # 前复权
        fill_data=True,
    )

    if not has_valid_data(market_data):
        return None

    close_df = market_data['close']
    dates = close_df.columns.tolist()
    data_dict = {
        'date': dates,
        'close': close_df.loc[STOCK_CODE].values,
    }

    for field in DAILY_FIELDS:
        df_source = market_data.get(field)
        if df_source is not None and STOCK_CODE in df_source.index:
            data_dict[field] = df_source.loc[STOCK_CODE].values

    df = pd.DataFrame(data_dict)
    df['date'] = pd.to_datetime(df['date'], format=DATE_FORMAT, errors='coerce')
    df = df.dropna(subset=['date', 'close']).sort_values('date').reset_index(drop=True)
    return df


def _save_and_report(df):
    """保存CSV并打印数据预览与统计信息"""
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    output_file = DATA_DIR / f'{STOCK_CODE.replace(".", "_")}_daily_QMT.csv'
    df.to_csv(output_file, index=False, encoding='utf-8-sig')

    logger.info(f"Data saved to: {output_file}")

    logger.info("Data preview (first 5 rows):")
    logger.info(df.head().to_string(index=False))
    logger.info("Data preview (last 5 rows):")
    logger.info(df.tail().to_string(index=False))

    logger.info("Data summary:")
    logger.info(f"  Total records: {len(df)}")
    logger.info(f"  Close range: {df['close'].min():.2f} - {df['close'].max():.2f}")
    if 'volume' in df.columns:
        logger.info(f"  Volume range: {df['volume'].min():,.0f} - {df['volume'].max():,.0f}")

    return output_file


def has_valid_data(market_data):
    """检查获取到的数据是否包含有效的收盘价"""
    return bool(market_data and 'close' in market_data
                and STOCK_CODE in market_data['close'].index)


def download_daily_data():
    """下载股票日线历史数据并保存到CSV文件"""
    logger.info(f"Stock: {STOCK_NAME} ({STOCK_CODE})")
    logger.info(f"Date range: {DATA_START} to {DATA_END}")
    logger.info("-" * 60)

    try:
        _download_raw()
        logger.info("Raw fetch_data download finished")

        df = _fetch_and_parse()
        if df is None:
            logger.error("No valid fetch_data retrieved for the requested range")
            return None

        logger.info(f"Retrieved {len(df)} daily bars")
        logger.info(f"Date range: {df['date'].iloc[0].strftime('%Y-%m-%d')} "
                    f"to {df['date'].iloc[-1].strftime('%Y-%m-%d')}")

        output_file = _save_and_report(df)
        return output_file

    except Exception:
        logger.exception("Error during fetch_data download")
        return None


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO, format='%(message)s')
    result = download_daily_data()

    if result:
        logger.info("=" * 60)
        logger.info("Daily fetch_data download completed successfully")
        logger.info(f"Output: {result}")
        logger.info("=" * 60)