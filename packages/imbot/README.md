# imbot

机器人消息回复模块，接入飞书等 IM 软件。

## 安装

```bash
uv add imbot
```

## 使用

```python
from imbot import IMBot

bot = IMBot()
bot.send("Hello from imbot!")
```

## 独立发布

```bash
cd packages/imbot
uv build
uv publish
```
