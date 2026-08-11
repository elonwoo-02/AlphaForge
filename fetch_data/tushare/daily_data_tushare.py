# -*- coding: utf-8 -*-
"""
从 Tushare Pro 下载日线 OHLCV 数据。

下载贵州茅台（600519.SH）的前复权日线数据，保存为 CSV 至 data/ 子目录。

运行前提：
    - 已安装 tushare（pip install tushare）
    - 已设置环境变量 TUSHARE_TOKEN

默认参数：
    股票：600519.SH
    日期范围：20240101 ~ 20260811
    输出文件：data/600519_SH_daily_tushare.csv
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
DATA_START = '20240101'
DATA_END = '20260811'

COLUMN_MAP = {'trade_date': 'date', 'vol': 'volume'}
KEEP_COLUMNS = ['date', 'open', 'high', 'low', 'close', 'volume']
DATE_FORMAT = '%Y%m%d'

DATA_DIR = Path(__file__).resolve().parent / "data"


def _get_pro():
    """初始化 Tushare Pro（需环境变量 TUSHARE_TOKEN）"""
    token = os.environ.get("TUSHARE_TOKEN")
    if not token or not str(token).strip():
        raise RuntimeError("未设置环境变量 TUSHARE_TOKEN，请先设置后再运行")
    ts.set_token(str(token).strip())
    return ts.pro_api()


def _download_raw(pro):
    """调用 ts.pro_bar 下载前复权日线数据"""
    df = pro.pro_bar(
        ts_code=STOCK_CODE,
        start_date=DATA_START,
        end_date=DATA_END,
        adj='qfq',
        freq='D',
    )
    return df


def _fetch_and_parse():
    """列名转换、日期转换、排序、筛选保留列"""
    pro = _get_pro()
    raw = _download_raw(pro)
    if not has_valid_data(raw):
        return None

    df = raw.rename(columns=COLUMN_MAP)
    df['date'] = pd.to_datetime(df['date'], format=DATE_FORMAT)
    df = df.sort_values('date').reset_index(drop=True)
    df = df[[c for c in KEEP_COLUMNS if c in df.columns]]
    return df


def _save_and_report(df):
    """保存 CSV 并打印预览与统计"""
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    output_file = DATA_DIR / f'{STOCK_CODE.replace(".", "_")}_daily_tushare.csv'
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


def has_valid_data(data):
    """检查获取到的数据是否包含有效记录"""
    return data is not None and not data.empty


def download_daily_data():
    """下载股票日线历史数据"""
    logger.info(f"Stock: {STOCK_NAME} ({STOCK_CODE})")
    logger.info(f"Date range: {DATA_START} to {DATA_END}")
    logger.info("-" * 60)

    try:
        df = _fetch_and_parse()
        if df is None:
            logger.error("No valid data retrieved, check token permissions and stock code")
            return None

        logger.info(f"Retrieved {len(df)} daily bars")
        logger.info(f"Date range: {df['date'].iloc[0].strftime('%Y-%m-%d')} "
                    f"to {df['date'].iloc[-1].strftime('%Y-%m-%d')}")

        output_file = _save_and_report(df)
        return output_file

    except Exception:
        logger.exception("Error during data download")
        return None


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO, format='%(message)s')
    result = download_daily_data()

    if result:
        logger.info("=" * 60)
        logger.info("Daily data download completed successfully")
        logger.info(f"Output: {result}")
        logger.info("=" * 60)