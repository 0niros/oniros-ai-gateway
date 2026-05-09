# Oniros AI Gateway 技术方案

## 1. 项目目标

Oniros AI Gateway 是一个部署在办公内网可访问环境中的 AI API 网关。它的第一目标不是重写各家模型协议，而是解决内网客户端无法直接访问外部模型服务的问题，并在网关层统一管理上游地址、上游 API Key、日志、超时和后续扩展能力。

首版定位：

- 提供一个内网可访问的 HTTP 服务。
- 通过 URL 路径区分上游厂商和协议形态。
- 对请求和响应尽量透传，优先保证 SDK 兼容性。
- 在网关注入真实上游 API Key，避免内网客户端直接持有外部密钥。
- 支持流式响应透传，满足 OpenAI、Anthropic、DashScope、DeepSeek 等模型接口的常见使用方式。
- 后续再按需要增加协议转换、模型映射、fallback、审计和限流。

非目标：

- 首版不做 Docker。
- 首版不引入数据库。
- 首版不引入 Redis。
- 首版不做管理后台。
- 首版不追求完整协议互转。
- 首版不实现计费、多租户、复杂限流。

## 2. 技术选型

| 模块 | 选型 | 说明 |
| --- | --- | --- |
| 语言 | Python 3.11+ | 开发快，跨平台部署简单，适合快速迭代网关逻辑。 |
| Web 框架 | FastAPI | ASGI 生态成熟，路由和中间件清晰，后续扩展协议接口方便。 |
| ASGI Server | uvicorn | 开发和部署都简单，适合首版单进程服务。 |
| HTTP 客户端 | httpx | 支持 async、连接池、超时和流式请求/响应。 |
| 配置 | YAML + pydantic-settings | YAML 便于维护路由配置，pydantic 负责结构校验。 |
| 数据校验 | pydantic | 后续做协议转换时可以复用模型定义。 |
| 日志 | Python logging | 首版够用，后续可切换为 JSON 日志或 structlog。 |
| 测试 | pytest + pytest-asyncio + respx | mock 上游 HTTP 服务，验证转发、鉴权和流式逻辑。 |
| 代码质量 | ruff | 统一 lint 和格式化。 |

部署方式采用普通 Python 虚拟环境，不使用 Docker。

## 3. 路由设计

首版核心路由格式：

```text
/{provider}/{protocol}/{upstream_path}
```

字段含义：

- `provider`：上游厂商或服务名，例如 `deepseek`、`dashscope`、`openai`、`anthropic`。
- `protocol`：该路由使用的协议形态，例如 `openai`、`anthropic`、`dashscope`。
- `upstream_path`：需要转发给上游的原始 API path。

示例：

```text
POST /deepseek/openai/v1/chat/completions
POST /dashscope/openai/v1/chat/completions
POST /openai/openai/v1/chat/completions
POST /anthropic/anthropic/v1/messages
```

转发规则：

```text
/{provider}/{protocol}/{upstream_path}
  -> route(provider, protocol).base_url + /{upstream_path}
```

例如：

```text
/deepseek/openai/v1/chat/completions
  -> https://api.deepseek.com/v1/chat/completions

/dashscope/openai/v1/chat/completions
  -> https://dashscope.aliyuncs.com/compatible-mode/v1/chat/completions

/anthropic/anthropic/v1/messages
  -> https://api.anthropic.com/v1/messages
```

第一版仅做同协议透传。也就是说：

- `/deepseek/openai/*` 表示客户端和上游都使用 OpenAI-compatible 协议。
- `/anthropic/anthropic/*` 表示客户端和上游都使用 Anthropic 协议。
- 暂不承诺 `/anthropic/openai/*` 这类跨协议转换。

跨协议转换可以作为第二阶段能力加入。

## 4. 配置设计

配置文件建议命名为 `config.yaml`，提供 `config.example.yaml` 作为模板。

示例：

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
    api_key_env: "DEEPSEEK_API_KEY"
    auth:
      header: "Authorization"
      scheme: "Bearer"

  - provider: "dashscope"
    protocol: "openai"
    base_url: "https://dashscope.aliyuncs.com/compatible-mode"
    api_key_env: "DASHSCOPE_API_KEY"
    auth:
      header: "Authorization"
      scheme: "Bearer"

  - provider: "openai"
    protocol: "openai"
    base_url: "https://api.openai.com"
    api_key_env: "OPENAI_API_KEY"
    auth:
      header: "Authorization"
      scheme: "Bearer"

  - provider: "anthropic"
    protocol: "anthropic"
    base_url: "https://api.anthropic.com"
    api_key_env: "ANTHROPIC_API_KEY"
    auth:
      header: "x-api-key"

http:
  connect_timeout_seconds: 10
  read_timeout_seconds: 300
  max_request_body_mb: 20
```

配置原则：

- `provider + protocol` 必须唯一。
- `base_url` 不以 `/` 结尾。
- 上游 API Key 从环境变量读取，不写死在配置文件里。
- 网关对内 API Key 可以先写在配置里，后续再接环境变量或密钥管理。

## 5. 请求处理流程

标准请求流程：

```text
1. 接收客户端请求
2. 解析路径中的 provider、protocol、upstream_path
3. 根据 provider + protocol 查找路由配置
4. 校验内网客户端 API Key
5. 构造上游 URL
6. 复制必要请求头
7. 移除 hop-by-hop headers
8. 注入上游 API Key
9. 使用 httpx 转发 method、query、body
10. 透传上游 status code、headers、body
```

需要移除或重写的 header：

- `host`
- `connection`
- `keep-alive`
- `proxy-authenticate`
- `proxy-authorization`
- `te`
- `trailer`
- `transfer-encoding`
- `upgrade`
- 客户端传入的上游鉴权 header

网关应避免把内网客户端的 `Authorization` 原样传给上游，除非该路由明确配置为透传。默认行为是用配置中的 `api_key_env` 注入上游鉴权信息。

## 6. 流式响应

模型 API 常用 SSE 流式响应，首版必须支持透传。

策略：

- 客户端请求体、query 和 header 原样转发。
- 如果上游返回普通响应，网关普通返回。
- 如果上游返回 `text/event-stream` 或其他流式 body，网关使用 ASGI streaming response 逐块返回。
- 不解析 SSE 内容，不重组 chunk，不修改事件格式。

这样可以最大限度保持 SDK 兼容性。

流式处理注意事项：

- 读取上游响应时不能一次性把 body 读入内存。
- 客户端断开时，应关闭上游连接。
- 对流式接口设置较长 read timeout。
- 日志中不要记录完整流式内容，只记录状态、耗时、provider、protocol、path。

## 7. 鉴权设计

首版有两层鉴权：

1. 网关对内鉴权。
2. 网关对上游鉴权。

对内鉴权：

- 客户端请求网关时使用 `Authorization: Bearer <gateway_api_key>`。
- 网关在 `gateway_auth.api_keys` 中校验。
- 如果 `gateway_auth.enabled=false`，跳过对内鉴权，适合本地开发。

对上游鉴权：

- 每条 route 配置 `api_key_env`。
- 启动时可以不强制要求所有环境变量存在。
- 请求命中某条 route 时，如果对应环境变量不存在，返回 502 配置错误。
- 根据 route 的 `auth.header` 和 `auth.scheme` 注入上游鉴权 header。

示例：

```text
Authorization: Bearer sk-xxx
x-api-key: sk-ant-xxx
```

## 8. 错误处理

错误响应分为两类。

网关自身错误：

- `400`：路径格式错误。
- `401`：网关鉴权失败。
- `404`：没有匹配的 `provider + protocol` route。
- `413`：请求体超过限制。
- `502`：上游配置错误、上游连接失败。
- `504`：上游超时。

上游返回错误：

- 原样透传 status code 和响应 body。
- 尽量保留上游 `content-type`。
- 日志记录上游状态码，但不记录敏感 body。

首版不强制统一上游错误格式。统一错误格式会影响 SDK 兼容性，后续需要协议转换时再处理。

## 9. 项目结构

建议结构：

```text
oniros-ai-gateway/
  README.md
  pyproject.toml
  config.example.yaml
  docs/
    technical-design.md

  app/
    __init__.py
    main.py
    config.py
    errors.py
    logging.py

    gateway/
      __init__.py
      auth.py
      headers.py
      proxy.py
      router.py

    protocols/
      __init__.py
      openai.py
      anthropic.py
      dashscope.py

  tests/
    test_health.py
    test_auth.py
    test_proxy.py
    test_streaming.py
```

职责说明：

- `app/main.py`：创建 FastAPI app，注册路由和中间件。
- `app/config.py`：加载和校验 YAML 配置。
- `app/gateway/router.py`：解析 `provider/protocol/upstream_path` 并选择 route。
- `app/gateway/proxy.py`：负责 httpx 转发和响应透传。
- `app/gateway/auth.py`：负责网关对内鉴权。
- `app/gateway/headers.py`：负责 header 过滤、复制和上游鉴权注入。
- `app/protocols/`：首版可为空壳，后续放协议转换逻辑。

## 10. 运行方式

本地开发：

```bash
python -m venv .venv
source .venv/bin/activate
pip install -e ".[dev]"
cp config.example.yaml config.yaml
uvicorn app.main:app --host 0.0.0.0 --port 8000
```

环境变量示例：

```bash
export DEEPSEEK_API_KEY="..."
export DASHSCOPE_API_KEY="..."
export OPENAI_API_KEY="..."
export ANTHROPIC_API_KEY="..."
```

systemd 部署示例：

```ini
[Unit]
Description=Oniros AI Gateway
After=network.target

[Service]
WorkingDirectory=/opt/oniros-ai-gateway
EnvironmentFile=/opt/oniros-ai-gateway/.env
ExecStart=/opt/oniros-ai-gateway/.venv/bin/uvicorn app.main:app --host 0.0.0.0 --port 8000
Restart=always
RestartSec=3

[Install]
WantedBy=multi-user.target
```

## 11. 测试计划

单元测试：

- 配置加载成功。
- 缺少必填配置时报错。
- `provider + protocol` 路由匹配正确。
- 路径剥离和上游 URL 拼接正确。
- hop-by-hop headers 被移除。
- 上游鉴权 header 注入正确。

集成测试：

- `/health` 返回成功。
- 未带网关 API Key 时返回 401。
- 带正确网关 API Key 时可以转发。
- 上游 4xx/5xx 原样透传。
- 上游连接失败返回 502。
- 上游超时返回 504。

流式测试：

- mock 上游返回 `text/event-stream`。
- 网关逐块返回内容。
- 不缓存完整响应。
- 保留合理的 `content-type`。

质量检查：

```bash
ruff check .
ruff format --check .
pytest
```

## 12. 迭代路线

第一阶段：反向代理 MVP

- FastAPI 服务骨架。
- YAML 配置加载。
- `/health`。
- `/{provider}/{protocol}/{upstream_path}` 通用路由。
- httpx 普通请求转发。
- 上游 API Key 注入。
- 基础测试。

第二阶段：流式透传

- 支持 SSE 和普通 streaming body。
- 客户端断连处理。
- 长超时配置。
- 流式测试。

第三阶段：协议辅助能力

- 为 OpenAI、Anthropic、DashScope 增加轻量协议识别。
- 增加常用 SDK 示例。
- 增加模型路径和 provider 文档。

第四阶段：协议转换

- 支持 `/anthropic/openai/*` 这类跨协议路由。
- 建立内部统一 ChatRequest / ChatResponse。
- 实现 OpenAI Chat Completions 与 Anthropic Messages 的基础转换。
- 谨慎处理 tool calling、multi-modal 和 usage 字段。

第五阶段：网关增强

- 模型别名和 upstream model 映射。
- fallback provider。
- 请求审计日志。
- 简单限流。
- JSON 日志。
- 配置热加载。

## 13. 首版验收标准

首版完成时应满足：

- 可以通过 `uvicorn app.main:app --host 0.0.0.0 --port 8000` 启动。
- `/health` 可用。
- `/deepseek/openai/v1/chat/completions` 能转发到 DeepSeek OpenAI-compatible API。
- `/dashscope/openai/v1/chat/completions` 能转发到 DashScope compatible-mode API。
- `/anthropic/anthropic/v1/messages` 能转发到 Anthropic API。
- 上游 API Key 只存在于网关环境变量中，客户端不需要知道。
- 普通响应和流式响应都可以透传。
- 未配置的 `provider + protocol` 返回明确 404。
- 鉴权失败返回 401。
- `ruff check .` 和 `pytest` 通过。

## 14. 关键设计决策

当前采用的设计决策：

- 使用 Python 而不是 Rust，降低跨平台编译和部署成本。
- 使用 FastAPI + httpx，优先保证开发效率和 async streaming 能力。
- 不使用 Docker，采用 venv + uvicorn/systemd 部署。
- 首版按 `/{provider}/{protocol}` 做配置化路由，不做复杂协议转换。
- 默认透传上游响应，保持 SDK 兼容性。
- 上游密钥由网关注入，内网客户端只持有网关密钥。

这个设计的核心取舍是：先把网关作为可靠的中转层跑起来，保留协议转换扩展点，但不在第一版消耗过多复杂度。
