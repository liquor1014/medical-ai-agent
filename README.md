# 医疗文件检索与报表统计 Agent

面向医院 SPD（耗材供应管理）场景的演示项目：上传院内制度与耗材文档，基于检索与页码引用回答问题；用自然语言生成库存、供应商、科室消耗报表。仅用于管理辅助，不提供诊疗建议。

## 核心能力

- **文档问答**：文档上传 → 解析分块 → 检索 → 带页码/章节引用的回答，SSE 流式输出
- **报表统计**：自然语言 → SQL（NL2SQL）→ 受控执行（租户隔离 + 只读校验）→ 图表 / CSV 导出
- **多模型路由**：按任务选择 provider，超时或失败自动降级，全部失败时降级到 Mock 兜底
- **成本与降级日志**：`model_call_log` 记录 provider、tokens、成本、延迟、首字延迟、降级来源
- **认证与租户隔离**：数据库用户 + BCrypt + JWT + Redis 会话，所有业务数据按 `tenant_id` 隔离

## 架构

```
浏览器
  │  http://localhost:5173
  ▼
┌──────────────┐  /api/*   ┌──────────────┐   /api/parse, /api/chat   ┌──────────────┐
│  Vue3 前端   │ ────────► │ Java 控制面  │ ────────────────────────► │  AI 编排服务 │
│  (Nginx)     │           │ Spring Boot  │                           │  FastAPI     │
└──────────────┘           └──────┬───────┘                           └──────┬───────┘
                                  │                                        │
                    ┌─────────────┼─────────────┐              ┌─────────────┼─────────────┐
                    ▼             ▼             ▼              ▼             ▼             ▼
               PostgreSQL      Redis        MinIO           Qdrant        Redis        LLM API
               (业务数据)    (登录会话)   (原始文档)       (向量检索)    (可选缓存)   DeepSeek/Qwen/OpenAI
```

## 目录结构

```
medical-ai-agent/
├── web/                 # Vue3 + Vite + Element Plus 前端
├── backend/             # Spring Boot 3.4 / Java 21 控制面
├── ai-service/          # FastAPI + LangGraph AI 编排服务
├── infra/
│   ├── init.sql         # 数据库初始 schema
│   ├── seed.sql         # 演示业务数据
│   ├── migrations/      # 增量迁移脚本（幂等）
│   └── docker-compose.yml  # 仅基础设施（本地开发用）
├── scripts/
│   ├── start.ps1 / stop.ps1    # Windows 一键启动/停止（完整栈）
│   ├── start.sh  / stop.sh     # macOS/Linux 一键启动/停止
│   └── demo.sh                 # 环境连通性检查
├── docker-compose.yml   # 完整栈（基础设施 + 三个业务服务）
└── .env.example         # 环境变量模板
```

## 快速开始（Docker 一键启动）

前置要求：安装并启动 Docker Desktop（Windows / macOS），或 Docker Engine + Compose v2（Linux）。

```powershell
# Windows
.\scripts\start.ps1
```

```bash
# macOS / Linux
bash scripts/start.sh
```

脚本会：创建 `.env`（若不存在）→ 构建镜像 → 启动全部服务 → 等待健康检查 → 打印访问地址。

| 服务 | 地址 | 说明 |
| --- | --- | --- |
| 前端 | http://localhost:5173 | 登录后进入工作台 |
| 后端控制面 | http://localhost:8080 | `/actuator/health` |
| AI 服务 | http://localhost:8000/docs | FastAPI Swagger |
| PostgreSQL | localhost:5432 | `medical / medical123` |
| Redis | localhost:6379 | JWT 会话 |
| MinIO | http://localhost:9001 | `minioadmin / minioadmin123` |
| Qdrant | http://localhost:6333 | 向量检索 |

**演示账号**

- `admin / admin123`（系统管理员）
- `doctor / doctor123`（医生）
- 登录页也支持自助注册（默认医生角色，注册后自动登录）

**模型 Key**：不填 `DEEPSEEK_API_KEY` / `QWEN_API_KEY` / `OPENAI_API_KEY` 也能启动，所有 LLM 调用会按路由降级到 `mock`，页面功能可完整体验。填写任一 Key 后重建/重启 `ai-service` 即走真实模型。

停止服务：

```powershell
.\scripts\stop.ps1              # 保留数据
.\scripts\stop.ps1 -RemoveVolumes  # 连数据卷一起删除
```

> 注意：根目录 `docker-compose.yml`（完整栈）与 `infra/docker-compose.yml`（仅基础设施）使用相同的容器名，二者不能同时启动。切换前先执行对应的 `down`。

## 本地开发（容器只跑基础设施）

本地开发需自备 JDK 21 + Maven、Python 3.11、Node 20。

1. 启动基础设施（首次启动会自动建表、执行迁移并导入演示数据）：

   ```bash
   docker compose -f infra/docker-compose.yml up -d
   docker exec medical-ai-postgres psql -U medical -d medical_ai -c "\dt"   # 确认表已初始化
   ```

2. 后端（http://localhost:8080）：

   ```bash
   cd backend
   mvn spring-boot:run
   ```

3. AI 服务（http://localhost:8000）：

   ```powershell
   cd ai-service
   python -m venv .venv
   .venv\Scripts\pip install -e .
   .venv\Scripts\python -m uvicorn app.main:app --port 8000
   ```

   ```bash
   cd ai-service
   python -m venv .venv
   .venv/bin/pip install -e .
   .venv/bin/python -m uvicorn app.main:app --port 8000
   ```

4. 前端（http://localhost:5173，Vite 已把 `/api` 代理到 8080）：

   ```bash
   cd web
   npm install
   npm run dev
   ```

`.env` 放在项目根目录，后端通过环境变量读取数据库/Redis/MinIO 地址，AI 服务通过 `pydantic-settings` 读取（`POSTGRES_DSN`、`REDIS_URL`、`MINIO_*`、`LLM_*`）。

## 环境变量

参考 [.env.example](.env.example)，常用项：

| 变量 | 默认值 | 说明 |
| --- | --- | --- |
| `POSTGRES_DSN` | `postgresql://medical:medical123@localhost:5432/medical_ai` | AI 服务数据库连接串（Docker 内为 `postgres` 主机） |
| `DEEPSEEK_API_KEY` / `QWEN_API_KEY` / `OPENAI_API_KEY` | 空 | 为空时该 provider 视为未配置，自动跳过 |
| `LLM_ROUTE_CHAT` / `LLM_ROUTE_NL2SQL` / `LLM_ROUTE_REPORT` | `deepseek,qwen,openai,mock` | 按顺序尝试，失败/超时降级到下一个 |
| `LLM_TIMEOUT_SECONDS` | `20` | 单次非流式调用超时 |
| `LLM_STREAM_IDLE_TIMEOUT` | `15` | 流式首 token / 相邻 chunk 空闲超时 |
| `JWT_SECRET` | 演示密钥 | 生产环境必须替换 |
| `JWT_EXPIRE_HOURS` | `12` | JWT 有效期（与 Redis 会话 TTL 一致） |
| `WEB_PORT` | `5173` | 完整栈中前端对外端口 |

## 数据库

- 首次启动时，PostgreSQL 容器会按顺序执行 `infra/init.sql` → 迁移脚本 → `infra/seed.sql`，因此全新数据卷无需手工建表。
- 对**已存在**的数据库升级（如新增用户表），手动执行迁移：

  ```powershell
  Get-Content infra\migrations\003_app_user.sql | docker exec -i medical-ai-postgres psql -U medical -d medical_ai
  ```

- 重置演示数据：

  ```powershell
  Get-Content infra\seed.sql | docker exec -i medical-ai-postgres psql -U medical -d medical_ai
  ```

- 彻底重建（会删除所有数据）：`.\scripts\stop.ps1 -RemoveVolumes` 后重新启动。

## 测试

```bash
cd backend && mvn test          # JUnit 5 + Mockito（含注册功能单元测试）
cd ai-service && .venv/bin/python -m pytest   # Windows 用 .venv\Scripts\python
cd web && npm run type-check    # vue-tsc 类型检查
```

## 运维与排查

- 查看日志：`docker compose logs -f backend` / `ai-service` / `web`
- 重启单个服务：`docker compose restart ai-service`
- 连通性检查：`bash scripts/demo.sh`（需本机有 curl / pg_isready / redis-cli）
- 端口被占用（8080 / 5173 / 5432 等）：先关闭本地同名服务，或修改 `docker-compose.yml` 的端口映射
- 登录后接口全部 401：JWT 已过期或 Redis 会话被清除，重新登录即可
- 模型一直返回 Mock：检查对应 `*_API_KEY` 是否为空、`LLM_ROUTE_*` 是否包含该 provider，并查看 `docker compose logs ai-service`
- 成本/降级数据：`GET /api/models/logs` 可查看 `status`（success/degraded/failed/truncated）、`cost`、`tokens`、`fallback_from`

## 说明

本项目为演示，使用合成数据；不包含真实诊疗能力，不作为生产系统直接部署。生产化前需至少完成：密钥托管、HTTPS、注册限流/审核、审计日志留存策略、MinIO 私有桶与访问控制。
