# -*- coding: utf-8 -*-
"""
从 AkShare 下载日线 OHLCV 数据。

下载贵州茅台（600519）的前复权日线数据，保存为 CSV 至 data/ 子目录。

运行前提：
    - 已安装 akshare（pip install akshare）

默认参数：
    股票：600519
    日期范围：20240101 ~ 20260811
    输出文件：data/600519_SH_daily_akshare.csv
"""
import logging
from pathlib import Path

import akshare as ak
import pandas as pd

logger = logging.getLogger(__name__)

# AkShare 使用纯数字代码，不带交易所后缀
STOCK_CODE = "600519"
STOCK_NAME = "贵州茅台"
STOCK_CODE_FULL = "600519.SH"  # 完整代码，用于输出文件名
DATA_START = "20240101"
DATA_END = "20260811"

DATA_DIR = Path(__file__).resolve().parent / "data"

COLUMN_MAP = {
    "日期": "date",
    "开盘": "open",
    "收盘": "close",
    "最高": "high",
    "最低": "low",
    "成交量": "volume",
    "成交额": "amount",
    "振幅": "amplitude",
    "涨跌幅": "pct_chg",
    "涨跌额": "change",
    "换手率": "turnover",
}

KEEP_COLUMNS = ["date", "open", "high", "low", "close", "volume"]


def has_valid_data(data):
    return data is not None and len(data) > 0


def _download_raw():
    return ak.stock_zh_a_hist(
        symbol=STOCK_CODE,
        period="daily",
        start_date=DATA_START,
        end_date=DATA_END,
        adjust="qfq",
    )


def _fetch_and_parse():
    df = _download_raw()
    df = df.rename(columns=COLUMN_MAP)
    df["date"] = pd.to_datetime(df["date"])
    df = df.sort_values("date").reset_index(drop=True)
    df = df[[c for c in KEEP_COLUMNS if c in df.columns]]
    return df


def _save_and_report(df):
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    output_file = DATA_DIR / f"{STOCK_CODE_FULL.replace('.', '_')}_daily_akshare.csv"
    df.to_csv(output_file, index=False, encoding="utf-8-sig")
    logger.info("Data saved to: %s", output_file)

    logger.info("\nData preview (first 5 rows):")
    logger.info(df.head().to_string(index=False))
    logger.info("\nData preview (last 5 rows):")
    logger.info(df.tail().to_string(index=False))

    logger.info("\nData statistics:")
    logger.info("  Total records: %d", len(df))
    logger.info("  Close range: %.2f - %.2f", df["close"].min(), df["close"].max())
    if "volume" in df.columns:
        logger.info("  Volume range: %,.0f - %,.0f", df["volume"].min(), df["volume"].max())

    return output_file


def download_daily_data():
    logger.info("Stock: %s (%s)", STOCK_NAME, STOCK_CODE)
    logger.info("Date range: %s to %s", DATA_START, DATA_END)
    logger.info("-" * 60)

    try:
        df = _fetch_and_parse()
        if not has_valid_data(df):
            logger.error("Failed to fetch daily data, please check the stock code")
            return None

        logger.info("Successfully fetched %d daily records", len(df))
        logger.info(
            "Data date range: %s to %s",
            df["date"].iloc[0].strftime("%Y-%m-%d"),
            df["date"].iloc[-1].strftime("%Y-%m-%d"),
        )

        return _save_and_report(df)

    except Exception:
        logger.exception("Error during data download")
        return None


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO, format="%(message)s")
    result = download_daily_data()

    if result:
        logger.info("\n" + "=" * 60)
        logger.info("Data download complete!")
        logger.info("Data file: %s", result)
        logger.info("=" * 60)