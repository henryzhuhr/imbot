"""
腾讯股票搜索接口
"""

import json
import logging
from types.market import StockMarket
from typing import Any, Dict, List, Optional

import requests
from loguru import logger as default_logger
from common.log import Logger

from search.interface import BaseStockSearcher, StockInfo

# 配置日志（可选）
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


SEARCH_URL = "https://proxy.finance.qq.com/ifzqgtimg/appstock/smartbox/search/get"
STOCK_DATA_URL = "https://qt.gtimg.cn/q="


class TencentStockSearcher(BaseStockSearcher):
    SEARCH_URL = "https://proxy.finance.qq.com/ifzqgtimg/appstock/smartbox/search/get"

    logger: Logger
    """ Logger 对象，用于记录日志 """

    def __init__(self, logger: Optional[Logger] = None, mock: bool = False) -> None:
        super().__init__()
        self.logger = logger or default_logger
        self.mock = mock

    def search_stock_list(self, keyword: str) -> List[StockInfo]:
        self.logger.debug(f"searchStockList keyword: {keyword}")
        params = {"q": keyword}
        resp_json = self._call_api(self.SEARCH_URL, params=params, mock=self.mock)
        self.logger.debug(f"data: {resp_json}")

        # with open(
        #     f"src/stock/search/data/tencent_mock_{keyword}.json", "w", encoding="utf-8"
        # ) as f:
        #     f.write(json.dumps(resp_json, ensure_ascii=False, indent=2))

        if "code" not in resp_json:
            self.logger.error(f"Unexpected response format: {resp_json}")
            return []

        resp_code: int = resp_json["code"]
        if resp_code != 0:
            self.logger.error(
                f"API error: code {resp_code}, message: {resp_json.get('message', 'No message')}"
            )
            return []
        data: Dict[str, list] = resp_json.get("data", {})
        raw_stocks = data.get("stock", [])

        stocks = []
        for stock in raw_stocks:
            stock_info = self._parse_to_stock_info(stock)
            if stock_info:
                stocks.append(stock_info)

        self.logger.debug(f"stockList: {stocks} for keyword: {keyword}")
        return stocks

    def _call_api(
        self,
        url: str,
        params: Dict[str, Any] = {},
        mock=False,
    ) -> Dict[str, Any]:
        response = requests.get(url, params=params)
        response.raise_for_status()
        return response.json()

    def _parse_to_stock_info(self, stock_item: list) -> Optional[StockInfo]:
        """
        将原始股票数据解析为 StockInfo 对象
        - ['sh', '601899', '紫金矿业', '', 'GP-A']
        - ['hk', '02899', '紫金矿业', '', 'GP']
        """
        if len(stock_item) < 4:
            self.logger.error(f"Invalid stock item format: {stock_item}")
            return None
        return StockInfo(
            code=stock_item[1].lower(),
            name=stock_item[2],
            market=StockMarket(stock_item[0].upper()),
            abbreviation=stock_item[3],
        )

    def _parse_market(self, market_str: str) -> Optional[StockMarket]:
        """
        将字符串市场代码转换为StockMarket枚举

        Args:
            market_str: 市场代码字符串

        Returns:
            对应的StockMarket枚举值，无法匹配则返回None
        """
        market_map = {
            "sh": StockMarket.SH,
            "sz": StockMarket.SZ,
            "hk": StockMarket.HK,
            "us": StockMarket.US,
        }

        return market_map.get(market_str.lower())

    def get_stock_info(self, stock_code: str) -> StockInfo:
        raise NotImplementedError


def get_tencent_hk_stock_data(codes: List[str]) -> List[Dict[str, Any]]:
    """
    获取腾讯财经的股票实时数据（支持港股 hk 开头）
    注意：腾讯接口返回的是 GBK 编码的文本，需解码后解析
    """
    # 构造 q 参数，如 r_hk00700,r_sh600000
    q_param = ",".join(f"r_{code}" for code in codes)
    params = {"q": q_param, "fmt": "json"}

    # 发送请求，获取原始字节流（因为是 GBK 编码）
    response = requests.get(STOCK_DATA_URL, params=params)
    response.raise_for_status()

    # 腾讯返回的是 GBK 编码的字符串，不是标准 JSON，而是 var r_hk00700="..." 格式
    # 但 fmt=json 时会返回类似 JSONP 的格式，实际是 JS 对象字面量，需手动处理
    # 实际观察：fmt=json 时返回的是纯文本，每行一个 var ...，但有时直接是 JSON-like 字符串
    # 更可靠的方式：按行分割，提取等号右边的内容，并去除引号和分号

    # 但根据你的 TS 代码，你期望的是一个 JSON 对象，例如 { "r_hk00700": [...] }
    # 然而腾讯的 fmt=json 并不返回标准 JSON！所以需要特殊解析

    # 正确做法：按行解析 var r_xxx="..."; 的形式
    text_gbk = response.content.decode("gbk")
    stock_dict = {}

    for line in text_gbk.strip().split(";"):
        line = line.strip()
        if not line.startswith("v_") or "=" not in line:
            continue
        try:
            key, value = line.split("=", 1)
            key = key.strip()
            value = value.strip()
            if value.startswith('"') and value.endswith('"'):
                value = value[1:-1]  # 去掉首尾引号
            # 将字符串按 ~ 分割（腾讯数据字段分隔符）
            fields = value.split("~")
            stock_dict[key] = fields
        except Exception as e:
            logger.warning(f"Parse line failed: {line}, error: {e}")

    result = []
    for code in codes:
        code_configed = code.lower()
        if code_configed.startswith("hk"):
            # 保持 hk 后小写，如 hk00700
            code_configed = "hk" + code_configed[2:].lower()

        r_key = f"v_{code}"  # 注意：腾讯返回的是 v_hk00700，不是 r_hk00700！
        # 但在你的 TS 代码中用了 r_${code}，这可能是误解
        # 实际测试发现：URL 中用 r_hk00700，但返回变量名是 v_hk00700
        # 所以这里用 v_${code}

        stock_item_arr = stock_dict.get(r_key)

        if not stock_item_arr or len(stock_item_arr) < 38:
            result.append({"code": code_configed, "name": "NODATA"})
            continue

        # 字段索引参考腾讯数据结构（注意索引从 0 开始）
        result.append(
            {
                "code": code_configed,
                "name": stock_item_arr[1],  # 名称
                "price": stock_item_arr[3],  # 最新价
                "yestclose": stock_item_arr[4],  # 昨收
                "open": stock_item_arr[5],  # 今开
                "high": stock_item_arr[33],  # 最高
                "low": stock_item_arr[34],  # 最低
                "volume": stock_item_arr[36],  # 成交量（股）
                "amount": stock_item_arr[37],  # 成交额
                "buy1": stock_item_arr[9],  # 买一价
                "sell1": stock_item_arr[19],  # 卖一价
                "time": stock_item_arr[30],  # 时间（HHMMSS）
            }
        )

    logger.info(f"stockDataList: {result} for codes: {codes}")
    return result


def test():
    stock_seacher = TencentStockSearcher(mock=True)
    stocks = stock_seacher.search_stock_list("紫金矿业")
    for stock in stocks:
        print(stock)


if __name__ == "__main__":
    test()
