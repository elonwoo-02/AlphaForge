# AkShare 数据采集

A 股行情与财务数据（免费，无需 Token）。

## 脚本

| 文件 | 说明 |
|------|------|
| `daily_data_akshare.py` | 日线 OHLCV（前复权） |
| `minute_data_akshare.py` | 分钟 K 线（仅最近 5 个交易日） |
| `financial_data_akshare.py` | 综合财务指标（三大报表） |

## 运行

```bash
python daily_data_akshare.py
python minute_data_akshare.py
python financial_data_akshare.py
```

## 注意事项

- 分钟数据仅覆盖最近 5 个交易日（数据来源：东方财富）
- 修改脚本顶部配置常量即可更换股票或日期