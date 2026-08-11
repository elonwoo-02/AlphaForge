# -*- coding: utf-8 -*-
"""
从 QMT / miniQMT 下载分钟级 K 线数据。

下载贵州茅台（600519.SH）指定交易日的前复权分钟数据，保存为 CSV 至 fetch_data/ 子目录。

运行前提：
    - 已启动 miniQMT 客户端
    - 已安装 xtquant（pip install xtquant）

默认参数：
    股票：600519.SH
    目标日期：20260811（全天）
    周期：1m（也支持 5m、15m、30m、60m）
    输出文件：fetch_data/600519_SH_1min_QMT.csv
"""
import logging
import pandas as pd
from pathlib import Path
from xtquant import xtdata

logger = logging.getLogger(__name__)

# ============ 配置常量 ============
STOCK_CODE = '600519.SH'      # 贵州茅台（QMT格式）
STOCK_NAME = '贵州茅台'
TARGET_DATE = '20260811'       # 目标日期
PERIOD = '1m'                  # 1分钟K线（可选：1m, 5m, 15m, 30m, 60m）
MINUTE_FIELDS = ['open', 'high', 'low', 'volume', 'amount']  # amount（成交额）为分钟数据独有字段
DATE_FORMAT = '%Y%m%d'  # QMT日期格式，用于动态计算次日日期作为end_time
MINUTE_DATETIME_FORMAT = '%Y%m%d%H%M%S'  # QMT分钟级时间戳格式（YYYYMMDDHHmmss）
WRITE_WAIT_SECONDS = 2  # QMT下载为异步操作，需等待数据写入本地缓存
DATA_DIR = Path(__file__).resolve().parent / "fetch_data"


def _connect_qmt():
    """连接QMT数据服务"""
    xtdata.connect()


def _download_raw():
    """调用xtdata下载分钟历史数据到本地缓存"""
    xtdata.download_history_data(
        stock_code=STOCK_CODE,
        period=PERIOD,
        start_time=TARGET_DATE,
    )


def _fetch_and_parse():
    """获取分钟K线数据并构建清洗后的DataFrame"""
    end_time = (pd.Timestamp(TARGET_DATE) + pd.Timedelta(days=1)).strftime(DATE_FORMAT)

    market_data = xtdata.get_market_data(
        stock_list=[STOCK_CODE],
        period=PERIOD,
        start_time=TARGET_DATE,
        end_time=end_time,
        count=-1,
        dividend_type='front',
        fill_data=False,
    )

    if not has_valid_data(market_data):
        return None

    close_df = market_data['close']
    timestamps = close_df.columns.tolist()
    data_dict = {
        'datetime': timestamps,
        'close': close_df.loc[STOCK_CODE].values,
    }

    for field in MINUTE_FIELDS:
        df_source = market_data.get(field)
        if df_source is not None and STOCK_CODE in df_source.index:
            data_dict[field] = df_source.loc[STOCK_CODE].values

    df = pd.DataFrame(data_dict)
    # QMT返回的时间戳可能是纯数字或字符串，统一转str后解析
    df['datetime'] = pd.to_datetime(
        df['datetime'].astype(str),
        format=MINUTE_DATETIME_FORMAT,
        errors='coerce',
    )
    df = df.dropna(subset=['datetime', 'close'])

    # end_time设为次日，实际数据多拉了一天，需过滤回目标日
    target_date_only = pd.Timestamp(TARGET_DATE).date()
    df = df[df['datetime'].dt.date == target_date_only]
    df = df.sort_values('datetime').reset_index(drop=True)

    if df.empty:
        return None

    return df


def _save_and_report(df):
    """保存CSV并打印数据预览与统计信息"""
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    output_file = DATA_DIR / f'{STOCK_CODE.replace(".", "_")}_1min_QMT.csv'
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


def has_valid_data(market_data):
    """检查获取到的数据是否包含有效的收盘价"""
    return bool(market_data and 'close' in market_data
                and STOCK_CODE in market_data['close'].index)


def download_minute_data():
    """下载指定日期的分钟K线数据并保存到CSV文件"""
    logger.info(f"Stock: {STOCK_NAME} ({STOCK_CODE})")
    logger.info(f"Date: {TARGET_DATE}")
    logger.info(f"Period: {PERIOD}")
    logger.info("-" * 60)

    try:
        _connect_qmt()
        logger.info("Connected to QMT fetch_data service")

        _download_raw()
        logger.info("Raw fetch_data download finished")

        df = _fetch_and_parse()
        if df is None:
            logger.error(f"No fetch_data available for {TARGET_DATE} (possibly a non-trading day)")
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