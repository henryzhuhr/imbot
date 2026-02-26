# AGENTS

本文件为本仓库内协作开发（人类与 AI Agent）的工作约定。

## 开发目标

- `newsfetcher` 负责拉取结构化新闻数据
- `imbot` 负责把消息发送到 IM 平台（如飞书）
- `app/main.py` 负责把两者串联成完整流程

## Environment Setup

```bash
# 安装依赖（含 workspace 成员）
uv sync

# 安装依赖（含 workspace 成员及其可选依赖）
uv sync --all-extras

# 运行应用
uv run app/main.py

# 分包构建（示例）
cd packages/imbot && uv build
cd packages/newsfetcher && uv build
```

## Project Structure

- 应用入口：`app/main.py`
- 子包：
  - `packages/imbot`：IM 管理模块
  - `packages/newsfetcher`：新闻抓取模块

## Agent 执行约束

- 修改前先阅读目标文件上下文，避免破坏公开接口
- 优先做“最小必要变更”，不引入与任务无关的重构
- 涉及行为变更时，补充最小可运行示例或文档说明
- 修改完成后，执行相关的单元测试，确保功能正确
- 修改完成后，至少执行一次应用入口验证：`uv run app/main.py`

### 代码格式化

每次修改完代码后，需要使用 ruff 检查 Python 代码

- 你需要对自己修改的代码，使用 `ruff format` 进行格式化，有关支持的选项的完整列表，请运行 `ruff format --help`
