#!/bin/bash
# 预先构建项目镜像的脚本，加快 docker compose up 的速度

IMAGE_NAME=imbot
IMAGE_TAG=1.0.0
# IMAGE_TAG=$(date +%Y%m%d%H%M%S)

# uv: https://github.com/astral-sh/uv/pkgs/container/uv
UV_TAG=0.10.0
NODE_TAG=24
GO_TAG=1.25


MIRRORS_URL="mirrors.ustc.edu.cn"
CLEAN_APT_CACHE=1


# 镜像列表（格式：镜像名:标签）
IMAGES=(
  "ubuntu:24.04"
  "ghcr.io/astral-sh/uv:${UV_TAG}"
  "golang:${GO_TAG}"
  "node:${NODE_TAG}"
)

for IMAGE in "${IMAGES[@]}"; do
  NAME=$(echo "${IMAGE}" | cut -d: -f1)
  TAG=$(echo "${IMAGE}" | cut -d: -f2-)
  if ! docker images | grep -q "^${NAME}[[:space:]]\+${TAG}[[:space:]]"; then
    echo "pull image: ${IMAGE}"
    docker pull "${IMAGE}" || {
      echo "failed to pull image ${IMAGE}, aborting!";
      exit 1;
    }
  else
    echo "found ${IMAGE}, skip docker pull."
  fi
done

docker build -t ${IMAGE_NAME}:${IMAGE_TAG} -f dockerfiles/Dockerfile \
  --build-arg UV_TAG=${UV_TAG} \
  --build-arg GO_TAG=${GO_TAG} \
  --build-arg NODE_TAG=${NODE_TAG} \
  --build-arg MIRRORS_URL=${MIRRORS_URL} \
  --build-arg CLEAN_APT_CACHE=${CLEAN_APT_CACHE} \
  --no-cache .


# 打印构建完成的镜像列表
echo "Built images:"
docker images --format "table {{.Repository}}:{{.Tag}}\t{{.Size}}\t{{.CreatedSince}}\t{{.CreatedAt}}" | grep "${IMAGE_NAME}:${IMAGE_TAG}"