# 图4-2 平台服务与 AI 服务协同交互图文字描述

## 对应论文位置
第4章 `4.1.2 多服务协同设计` 后。

## 建议图型
时序图，推荐 Mermaid `sequenceDiagram`。

## 文字描述
时序从“用户在前端发起 AI 查询”开始。前端将请求发送到 `/api/v1/flood/query` 或 `/api/v1/flood/query/stream`，先进入 Nginx，再进入 Spring Boot 平台服务的 AI 代理控制器。平台服务将请求转发给 FastAPI AI 服务。AI 服务接收到查询后，先构建共享状态，再通过多智能体图执行。执行过程中，AI 服务直接访问 PostgreSQL 获取站点、观测、告警和阈值规则等实时数据；若发生告警确认、告警关闭、预案执行等受业务规则约束的写操作，则通过 `WaterPlatformClient` 调用平台 REST API，并在调用前通过 `/api/v1/auth/login` 获取 JWT。最终，AI 服务将结构化结果返回平台服务，由平台统一返回给前端。图中应明确区分“读路径”和“写路径”，其中读路径用实线直接连接 AI 服务与数据库，写路径用另一种颜色或虚线强调“必须经过平台”。

## 必含元素
- 前端、Nginx、平台服务、AI 服务、PostgreSQL。
- 平台登录接口 `/api/v1/auth/login`。
- 读取对象：站点、观测、告警、规则。
- 写回对象：告警 ACK/CLOSE、预案执行状态、业务操作。

## 标注建议
- 在写路径旁标注“统一治理、审计留痕”。
- 在读路径旁标注“降低跨服务读取延迟”。

## 项目依据
- `nginx.conf`
- `water-info-ai/app/services/platform_client.py`
- `water-info-ai/app/services/database.py`
- `water-info-platform/src/main/java/com/waterinfo/platform/module/ai/controller/FloodAiController.java`

