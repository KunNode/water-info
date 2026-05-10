# 开发与测试

## 后端平台

```bash
cd water-info-platform
mvn clean compile
mvn test
mvn test -Dtest=StationServiceTest
mvn package -DskipTests
mvn spring-boot:run -Dspring-boot.run.profiles=dev
```

说明：

- 仓库当前 README 指出平台侧使用本地 `mvn`，不要假设 Maven Wrapper 一定存在。
- 部分测试依赖 Testcontainers，需要 Docker。

## AI 服务

```bash
cd water-info-ai
uv sync --extra dev
cp .env.example .env
uv run python -m app.main
uv run pytest tests/ -v
uv run ruff check app/ tests/
uv run ruff format app/ tests/
```

常用配置：

- `OPENAI_API_KEY`
- `OPENAI_API_BASE`
- `OPENAI_MODEL`
- `EMBEDDING_API_KEY`
- `PG_HOST`
- `REDIS_URL`
- `WATER_PLATFORM_BASE_URL`

测试外部 LLM/RAG 时要区分单元测试、集成测试和需要真实服务的 smoke 测试。

## 管理端

```bash
cd water-info-admin
npm install
npm run dev
npm run build
npm run lint
npm run format
```

构建脚本为：

```text
vue-tsc --noEmit && vite build
```

项目记忆中记录过一次历史情况：`npm run build` 可通过；如果某个环境缺失 ESLint 配置，直接运行 ESLint 会失败，应先确认当前仓库配置状态。

## Docker 开发

```bash
docker-compose up -d postgres redis
docker-compose up -d --build platform ai admin nginx
docker-compose down
```

仅调试某个服务时，可以保留基础设施容器，用本地进程运行平台、AI 或前端。

## 验证建议

| 改动类型 | 最低验证 |
| --- | --- |
| Java controller/service | `mvn test` 或相关单测，必要时编译 |
| 数据库迁移 | 启动平台让 Flyway 执行，检查迁移顺序 |
| AI Agent/工具 | `uv run ruff check app tests` 和相关 pytest |
| RAG/记忆 | 单元测试 + 至少一次真实查询或 smoke |
| 前端页面 | `npm run build`，必要时 Playwright 截图 |
| Nginx/Compose | `docker-compose up -d --build` + 健康检查 |

## 提交前检查

- 是否越过了服务所有权边界。
- 是否引入了未说明的新依赖。
- 是否更新了接口、迁移、环境变量和文档。
- 是否覆盖了关键路径测试。
- 是否记录了无法验证的风险。

