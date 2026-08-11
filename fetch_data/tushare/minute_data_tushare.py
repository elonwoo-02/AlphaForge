# -*- coding: utf-8 -*-
"""
从 Tushare Pro 下载分钟级 K 线数据。

下载贵州茅台（600519.SH）指定交易日的前复权分钟数据，保存为 CSV 至 fetch_data/ 子目录。

运行前提：
    - 已安装 tushare（pip install tushare）
    - 已设置环境变量 TUSHARE_TOKEN
    - 已开通分钟行情权限（需单独开通）

默认参数：
    股票：600519.SH
    目标日期：20260811（全天）
    频率：1min（也支持 5min、15min、30min、60min）
    输出文件：fetch_data/600519_SH_1min_tushare.csv

注意：Tushare 的分钟数据（1/5/15/30/60min）需要单独开通权限，
      普通积分用户无法获取。需要捐助 1000 元获取分钟行情权限。
      频次限制：每分钟 500 次，每次最多 8000 行。
"""
import os
import logging
from pathlib import Path

import pandas as pd
import tushare as ts


logger = logging.getLogger(__name__)


# ============================================================
# 配置
# ============================================================
STOCK_CODE = '600519.SH'                 # 贵州茅台（Tushare 格式）
STOCK_NAME = '贵州茅台'
TARGET_DATE = '20260811'                 # 目标日期
FREQ = '1min'                            # 可选：1min, 5min, 15min, 30min, 60min

DATA_DIR = Path(__file__).resolve().parent / "fetch_data"

COLUMN_MAP = {'trade_time': 'datetime', 'vol': 'volume'}
KEEP_COLUMNS = ['datetime', 'open', 'high', 'low', 'close', 'volume', 'amount']


def _get_pro():
    """获取 Tushare Pro 实例（需环境变量 TUSHARE_TOKEN）"""
    token = os.environ.get("TUSHARE_TOKEN")
    if not token or not str(token).strip():
        raise RuntimeError("未设置环境变量 TUSHARE_TOKEN，请先设置后再运行")
    ts.set_token(str(token).strip())
    return ts.pro_api()


def _download_raw(pro):
    """调用 ts.pro_bar 下载原始分钟数据。"""
    logger.info("Downloading raw minute fetch_data from Tushare ...")
    df = ts.pro_bar(
        ts_code=STOCK_CODE,
        start_date=TARGET_DATE,
        end_date=TARGET_DATE,
        adj='qfq',
        freq=FREQ,
    )
    return df


def _fetch_and_parse(raw):
    """列名转换、时间转换、排序、筛选保留列。"""
    if raw is None or len(raw) == 0:
        return raw

    df = raw.rename(columns=COLUMN_MAP)
    df['datetime'] = pd.to_datetime(df['datetime'])
    df = df.sort_values('datetime').reset_index(drop=True)
    df = df[[c for c in KEEP_COLUMNS if c in df.columns]]
    return df


def _save_and_report(df):
    """保存 CSV，打印预览及统计信息。"""
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    output_file = DATA_DIR / f'{STOCK_CODE.replace(".", "_")}_1min_tushare.csv'
    df.to_csv(output_file, index=False, encoding='utf-8-sig')
    logger.info("Data saved to: %s", output_file)

    logger.info("\nData preview (first 10 rows):")
    logger.info("\n%s", df.head(10).to_string(index=False))
    logger.info("\nData preview (last 5 rows):")
    logger.info("\n%s", df.tail(5).to_string(index=False))

    logger.info("\nData statistics:")
    logger.info("  Total records: %s", len(df))
    logger.info("  Close price range: %.2f - %.2f", df['close'].min(), df['close'].max())
    if 'volume' in df.columns:
        logger.info("  Volume range: %s - %s", f"{df['volume'].min():,.0f}", f"{df['volume'].max():,.0f}")

    return output_file


def has_valid_data(data):
    """检查数据是否非空。"""
    return data is not None and len(data) > 0


def download_minute_data():
    """下载指定日期的分钟 K 线数据"""
    logger.info("Stock: %s (%s)", STOCK_NAME, STOCK_CODE)
    logger.info("Date: %s", TARGET_DATE)
    logger.info("Frequency: %s", FREQ)
    logger.info("-" * 60)

    try:
        logger.info("Initializing Tushare Pro ...")
        pro = _get_pro()
        logger.info("Initialization successful")

        logger.info("Downloading %s fetch_data (forward-adjusted) ...", FREQ)
        raw = _download_raw(pro)

        if not has_valid_data(raw):
            logger.error("Failed to fetch minute fetch_data. Possible reasons:")
            logger.error("  1. Minute market permission not granted (requires donation of 1000 CNY)")
            logger.error("  2. Target date is not a trading day")
            logger.error("  3. Insufficient token permissions")
            return None

        df = _fetch_and_parse(raw)
        logger.info("Successfully fetched %s minute fetch_data records", len(df))
        logger.info("Time range: %s to %s", df['datetime'].iloc[0], df['datetime'].iloc[-1])

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
        logger.info("Minute fetch_data download completed!")
        logger.info("Data file: %s", result)
        logger.info("=" * 60)