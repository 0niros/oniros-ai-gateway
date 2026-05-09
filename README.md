# Oniros AI Gateway

Oniros AI Gateway 是一个轻量级 AI API 网关，用于把办公内网中的模型请求中转到外部模型服务。

它的首版目标很直接：**客户端访问内网网关，网关根据 URL 选择上游厂商，注入真实上游 API Key，然后把请求和响应尽量原样透传**。

当前版本不做复杂协议转换，优先保证简单、稳定、容易部署。

## 适用场景

这个项目适合下面这类情况：

- 办公网或内网机器不能直接访问外部模型 API。
- 不希望把 OpenAI、DeepSeek、DashScope、Anthropic 等真实 API Key 分发给每个客户端。
- 希望用一个统一入口管理多个上游模型服务。
- 希望先做稳定转发，后续再逐步加入协议转换、模型映射、fallback、审计日志等能力。

首版重点是反向代理，不是完整 AI 协议网关。

## 当前能力

- 基于 Python + FastAPI + httpx 实现。
- 支持配置化上游路由。
- 支持路径格式 `/{provider}/{protocol}/{upstream_path}`。
- 支持网关侧 Bearer Token 鉴权。
- 支持按路由注入上游 API Key。
- 支持普通 HTTP 响应透传。
- 支持 SSE / streaming 响应透传。
- 自动移除不应该转发的 hop-by-hop headers。
- 默认不会把客户端访问网关用的 `Authorization` 透传给上游。
- 提供测试覆盖：配置、鉴权、转发、流式响应。

## 非目标

当前版本暂不做：

- Docker 部署。
- 数据库。
- Redis。
- 管理后台。
- 多租户和计费。
- 复杂限流。
- OpenAI、Anthropic、DashScope 之间的完整协议互转。

这些能力可以后续按实际需求逐步添加。

## 路由规则

网关统一使用下面的路径格式：

```text
/{provider}/{protocol}/{upstream_path}
```

字段说明：

- `provider`：上游厂商或服务名，例如 `deepseek`、`dashscope`、`openai`、`anthropic`。
- `protocol`：该路由使用的协议形态，例如 `openai`、`anthropic`。
- `upstream_path`：实际要转发给上游的 API 路径。

例如：

```text
POST /deepseek/openai/v1/chat/completions
POST /dashscope/openai/v1/chat/completions
POST /openai/openai/v1/chat/completions
POST /anthropic/anthropic/v1/messages
```

网关会剥掉前两段 `/{provider}/{protocol}`，把剩余路径拼到配置中的 `base_url` 后面。

示例：

```text
/deepseek/openai/v1/chat/completions
  -> https://api.deepseek.com/v1/chat/completions

/dashscope/openai/v1/chat/completions
  -> https://dashscope.aliyuncs.com/compatible-mode/v1/chat/completions

/anthropic/anthropic/v1/messages
  -> https://api.anthropic.com/v1/messages
```

## 快速开始

### 一键启动

项目提供了一键启动脚本：

```bash
./scripts/start.sh
```

脚本会自动完成：

- 创建 `.venv`。
- 安装运行依赖。
- 如果没有 `config.yaml`，从 `config.example.yaml` 复制一份。
- 使用 `uvicorn` 启动服务。

默认监听：

```text
http://0.0.0.0:8000
```

可通过环境变量覆盖：

```bash
HOST=127.0.0.1 PORT=8001 ./scripts/start.sh
```

指定配置文件：

```bash
CONFIG=/opt/oniros-ai-gateway/config.yaml ./scripts/start.sh
```

安装开发依赖并启动：

```bash
INSTALL_DEV=1 ./scripts/start.sh
```

首次启动后，请编辑 `config.yaml`，把 `api_key` 占位值替换成真实上游密钥。

### 1. 创建虚拟环境

```bash
python3 -m venv .venv
source .venv/bin/activate
```

### 2. 安装依赖

开发环境安装：

```bash
pip install -e ".[dev]"
```

如果只运行服务，也可以安装基础依赖：

```bash
pip install -e .
```

### 3. 创建配置文件

```bash
cp config.example.yaml config.yaml
```

按需要修改 `config.yaml` 里的上游地址、路由和网关密钥。

### 4. 填写上游 API Key

在 `config.yaml` 的每条 route 里直接填写对应上游的 `api_key`。

示例：

```yaml
routes:
  - provider: "deepseek"
    protocol: "openai"
    base_url: "https://api.deepseek.com"
    api_key: "your-deepseek-api-key"
    auth:
      header: "Authorization"
      scheme: "Bearer"
```

`config.yaml` 已经被 `.gitignore` 忽略，不要把真实密钥提交到仓库。

### 5. 启动服务

```bash
uvicorn app.main:app --host 0.0.0.0 --port 8000
```

也可以显式指定配置文件：

```bash
ONIROS_CONFIG=config.yaml uvicorn app.main:app --host 0.0.0.0 --port 8000
```

### 6. 检查健康状态

```bash
curl http://127.0.0.1:8000/health
```

正常返回：

```json
{"status":"ok"}
```

## 配置说明

示例配置见 [config.example.yaml](config.example.yaml)。

完整结构：

```yaml
server:
  host: "0.0.0.0"
  port: 8000

gateway_auth:
  enabled: true
  api_keys:
    - "local-dev-key"

routes:
  - provider: "deepseek"
    protocol: "openai"
    base_url: "https://api.deepseek.com"
    api_key: "your-deepseek-api-key"
    auth:
      header: "Authorization"
      scheme: "Bearer"

http:
  connect_timeout_seconds: 10
  read_timeout_seconds: 300
  max_request_body_mb: 20
```

### `gateway_auth`

网关对内鉴权配置。

```yaml
gateway_auth:
  enabled: true
  api_keys:
    - "local-dev-key"
```

客户端请求网关时需要携带：

```text
Authorization: Bearer local-dev-key
```

本地调试时可以关闭鉴权：

```yaml
gateway_auth:
  enabled: false
  api_keys: []
```

生产环境不建议关闭。

### `routes`

每一条 route 描述一个上游目标。

```yaml
- provider: "deepseek"
  protocol: "openai"
  base_url: "https://api.deepseek.com"
  api_key: "your-deepseek-api-key"
  auth:
    header: "Authorization"
    scheme: "Bearer"
```

字段说明：

- `provider`：URL 第一段。
- `protocol`：URL 第二段。
- `base_url`：上游服务基础地址。
- `api_key`：上游模型服务的真实 API Key，直接明文写在本地 `config.yaml`。
- `auth.header`：向上游注入 API Key 时使用的 header。
- `auth.scheme`：可选，常见值是 `Bearer`。

`provider + protocol` 必须唯一。

例如同时配置：

```yaml
- provider: "deepseek"
  protocol: "openai"
  base_url: "https://api.deepseek.com"
  api_key: "your-deepseek-api-key"

- provider: "dashscope"
  protocol: "openai"
  base_url: "https://dashscope.aliyuncs.com/compatible-mode"
  api_key: "your-dashscope-api-key"
```

对应请求路径分别是：

```text
/deepseek/openai/v1/chat/completions
/dashscope/openai/v1/chat/completions
```

### `http`

HTTP 转发相关配置。

```yaml
http:
  connect_timeout_seconds: 10
  read_timeout_seconds: 300
  max_request_body_mb: 20
```

说明：

- `connect_timeout_seconds`：连接上游的超时时间。
- `read_timeout_seconds`：读取上游响应的超时时间。流式响应通常需要更长时间。
- `max_request_body_mb`：请求体大小限制的预留配置。

## 调用示例

### DeepSeek OpenAI-compatible

```bash
curl http://127.0.0.1:8000/deepseek/openai/v1/chat/completions \
  -H "Authorization: Bearer local-dev-key" \
  -H "Content-Type: application/json" \
  -d '{
    "model": "deepseek-chat",
    "messages": [
      {"role": "user", "content": "你好，用一句话介绍你自己"}
    ]
  }'
```

实际上游请求会打到：

```text
https://api.deepseek.com/v1/chat/completions
```

并自动注入：

```text
Authorization: Bearer your-deepseek-api-key
```

### DashScope OpenAI-compatible

```bash
curl http://127.0.0.1:8000/dashscope/openai/v1/chat/completions \
  -H "Authorization: Bearer local-dev-key" \
  -H "Content-Type: application/json" \
  -d '{
    "model": "qwen-plus",
    "messages": [
      {"role": "user", "content": "你好"}
    ]
  }'
```

实际转发到：

```text
https://dashscope.aliyuncs.com/compatible-mode/v1/chat/completions
```

### Anthropic Messages

```bash
curl http://127.0.0.1:8000/anthropic/anthropic/v1/messages \
  -H "Authorization: Bearer local-dev-key" \
  -H "Content-Type: application/json" \
  -H "anthropic-version: 2023-06-01" \
  -d '{
    "model": "claude-3-5-sonnet-20241022",
    "max_tokens": 512,
    "messages": [
      {"role": "user", "content": "你好"}
    ]
  }'
```

实际转发到：

```text
https://api.anthropic.com/v1/messages
```

并自动注入：

```text
x-api-key: your-anthropic-api-key
```

### 流式响应

OpenAI-compatible 流式调用示例：

```bash
curl -N http://127.0.0.1:8000/deepseek/openai/v1/chat/completions \
  -H "Authorization: Bearer local-dev-key" \
  -H "Content-Type: application/json" \
  -d '{
    "model": "deepseek-chat",
    "stream": true,
    "messages": [
      {"role": "user", "content": "写一段很短的自我介绍"}
    ]
  }'
```

网关不会解析或重组 SSE 事件，只会逐块透传上游响应。

## 和 SDK 一起使用

如果 SDK 允许配置 `base_url`，可以把 base URL 指到带 provider/protocol 的路径前缀。

例如 OpenAI-compatible SDK 访问 DeepSeek：

```text
base_url = "http://127.0.0.1:8000/deepseek/openai/v1"
api_key = "local-dev-key"
```

这样 SDK 请求：

```text
/chat/completions
```

实际网关收到：

```text
/deepseek/openai/v1/chat/completions
```

再转发到：

```text
https://api.deepseek.com/v1/chat/completions
```

## 安全说明

默认安全策略：

- 客户端只持有网关 API Key。
- 上游 API Key 明文保存在网关机器本地的 `config.yaml` 里。
- 客户端传给网关的 `Authorization` 不会原样透传给上游。
- 网关会按 route 配置注入新的上游鉴权 header。
- 常见 hop-by-hop headers 会被移除。

建议：

- 生产环境务必开启 `gateway_auth.enabled`。
- `config.yaml` 只放在部署机器本地，不要提交到 git。
- 不要把真实上游 API Key 写进 `config.example.yaml`、README 或测试代码。
- 用 systemd 或进程管理工具管理服务。
- 在外层按需加 Nginx、内网负载均衡或 TLS 终止。

## 错误行为

网关自身错误：

- `401`：缺少或错误的网关 API Key。
- `404`：没有匹配的 `provider + protocol` 路由。
- `502`：上游配置错误，或连接上游失败。
- `504`：上游超时。

上游返回的业务错误：

- 网关尽量原样透传上游状态码、响应头和响应体。
- 例如上游返回 `429`，客户端也会收到 `429`。

这样做是为了保持模型 SDK 的兼容性。

## 开发和测试

安装开发依赖：

```bash
pip install -e ".[dev]"
```

运行测试：

```bash
pytest
```

运行 lint：

```bash
ruff check .
```

检查格式：

```bash
ruff format --check .
```

自动格式化：

```bash
ruff format .
```

## 项目结构

```text
app/
  main.py              # FastAPI 应用入口
  config.py            # YAML 配置加载和校验
  errors.py            # 网关错误工具
  logging.py           # 日志初始化

  gateway/
    auth.py            # 网关对内鉴权
    headers.py         # header 过滤和上游鉴权注入
    proxy.py           # httpx 转发和 streaming 透传
    router.py          # provider/protocol 路由匹配

  protocols/
    openai.py          # 后续协议转换扩展点
    anthropic.py       # 后续协议转换扩展点
    dashscope.py       # 后续协议转换扩展点

tests/
  test_auth.py
  test_config.py
  test_health.py
  test_proxy.py
  test_streaming.py
```

## systemd 部署示例

项目不使用 Docker。可以用普通 Python 虚拟环境配合 systemd 部署。

假设项目目录为：

```text
/opt/oniros-ai-gateway
```

示例 service：

```ini
[Unit]
Description=Oniros AI Gateway
After=network.target

[Service]
WorkingDirectory=/opt/oniros-ai-gateway
ExecStart=/opt/oniros-ai-gateway/.venv/bin/uvicorn app.main:app --host 0.0.0.0 --port 8000
Restart=always
RestartSec=3

[Install]
WantedBy=multi-user.target
```

如果需要指定配置文件路径，可以在 systemd 中加环境变量：

```ini
Environment=ONIROS_CONFIG=/opt/oniros-ai-gateway/config.yaml
```

## 后续计划

后续可以按使用情况逐步加入：

- OpenAI / Anthropic / DashScope 之间的基础协议转换。
- 模型别名和上游模型名映射。
- 多上游 fallback。
- 请求 ID 和结构化 JSON 日志。
- 简单限流。
- 配置热加载。
- 管理接口或只读状态接口。

首版的原则是：先把稳定中转做好，再扩展网关能力。
