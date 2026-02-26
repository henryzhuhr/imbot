#!/bin/sh


# Install Go tools
export GOPROXY=https://goproxy.cn,direct

go env -w GO111MODULE=on
go env -w GOPROXY=https://goproxy.cn,direct
# for Go latest
go install golang.org/x/tools/gopls@latest
go install github.com/cweill/gotests/...@latest
go install github.com/fatih/gomodifytags@latest
go install github.com/josharian/impl@latest
go install github.com/haya14busa/goplay/cmd/goplay@latest
go install github.com/go-delve/delve/cmd/dlv@latest
go install github.com/golangci/golangci-lint/v2/cmd/golangci-lint@latest

go mod tidy

# Init Python environment
uv sync --all-extras        # 安装所有依赖组
# uv sync --extra dev         # 只安装 dev 组

# Init Node.js environment
NPM_REGISTRY=https://registry.npmmirror.com/ # 设置为淘宝镜像
# NPM_REGISTRY=https://npm.aliyun.com/         # 设置为阿里云镜像
# NPM_REGISTRY=https://mirrors.cloud.tencent.com/npm/  # 设置为腾讯云镜像
# NPM_REGISTRY=https://registry.npmjs.org/             # 恢复为官方源

npm config set registry ${NPM_REGISTRY}
npm install -g pnpm
npm install -g @github/copilot
npm install -g @openai/codex
pnpm config set registry ${NPM_REGISTRY}
# pnpm install


# CodeX
printenv OPENAI_API_KEY | codex login --with-api-key