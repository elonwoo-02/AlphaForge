
# Tushare Pro 数据采集

A 股行情与财务数据（需 `TUSHARE_TOKEN` 环境变量）。

## 脚本

| 文件 | 说明 |
|------|------|
| `daily_data_tushare.py` | 日线 OHLCV（前复权） |
| `minute_data_tushare.py` | 分钟 K 线（需 1000 元分钟权限） |
| `financial_data_tushare.py` | 综合财务指标（需 2000 积分） |

## 运行

```bash
# 设置 Token（获取地址：https://tushare.pro）
export TUSHARE_TOKEN="your_token_here"

python daily_data_tushare.py
python minute_data_tushare.py
python financial_data_tushare.py
```

> Windows PowerShell 使用 `$env:TUSHARE_TOKEN="xxx"`。

## 注意事项

- 分钟数据需单独捐助开通（1000 元），普通用户不可用
- 财务数据需 2000 积分（免费注册仅 120 积分）