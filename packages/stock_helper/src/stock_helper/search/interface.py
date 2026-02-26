"""
搜索股票的接口
"""

from abc import ABC, abstractmethod
from types.market import StockMarket
from typing import List

from pydantic import BaseModel, Field


class StockInfo(BaseModel):
    market: StockMarket = Field(..., description="股票市场")
    code: str = Field(..., description="股票代码")
    name: str = Field(..., description="股票名称")
    abbreviation: str = Field(default="", description="股票简称")


class BaseStockSearcher(ABC):
    """股票代码搜索器基类，定义接口"""

    @abstractmethod
    def search_stock_list(self, keyword: str) -> List[StockInfo]:
        """
        根据关键词搜索股票列表
        """
        raise NotImplementedError("Subclasses must implement search_stock_list method")


class BaseStockDataFetcher(ABC):
    """股票数据获取器基类，定义接口"""

    @abstractmethod
    def get_stock_data(self, stock_code: str) -> StockInfo:
        """
        根据股票代码获取股票信息
        """
        raise NotImplementedError("Subclasses must implement get_stock_data method")
