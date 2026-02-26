"""
IM 机器人 - hello world 示例
"""


class IMBot:
    """IM 机器人，接入飞书等 IM 平台"""

    def __init__(self, platform: str = "feishu") -> None:
        self.platform = platform

    def send(self, message: str) -> None:
        """向 IM 平台发送消息（hello world 示例）"""
        print(f"Hello from imbot! [{self.platform}] Sending: {message}")
