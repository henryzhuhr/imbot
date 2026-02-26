"""
基本格式: 市场前缀 + 数字代码

市场前缀类型
sh - 上海证券交易所（如：sh601899）
sz - 深圳证券交易所（如：sz000001）
hk - 香港证券交易所（如：hk02899）
us - 美国证券交易所
"""

from enum import StrEnum


class StockMarket(StrEnum):
    """股票市场"""

    SH = "SH"  # 上海证券交易所
    SZ = "SZ"  # 深圳证券交易所
    HK = "HK"  # 香港联合交易所
    US = "US"  # 美国证券交易所
