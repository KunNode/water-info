# 管理端

`water-info-admin` 是 Vue 3 管理端，提供日常管理、监测展示、AI 指挥和系统治理界面。

## 技术栈

| 类别 | 技术 |
| --- | --- |
| Framework | Vue 3, TypeScript |
| Build | Vite |
| UI | Element Plus, `@element-plus/icons-vue` |
| State | Pinia |
| HTTP | Axios |
| Charts/Map | ECharts, Leaflet 相关组合能力 |
| Markdown | marked, highlight.js, dompurify |
| Test | vue-tsc, Playwright |

## 路由与页面

| 路由 | 页面 | 说明 |
| --- | --- | --- |
| `/login` | 登录 | JWT 登录入口 |
| `/dashboard` | 指挥仪表盘 | 系统概览和核心指标 |
| `/bigscreen` | 大屏 | 面向展示屏的大屏页面 |
| `/monitor/station` | 站点管理 | 监测站 CRUD |
| `/monitor/sensor` | 传感器 | 传感器维护、状态和心跳 |
| `/data/observation` | 观测数据 | 水位、雨量、流量等数据查询 |
| `/warning/alarm` | 告警管理 | 告警查看、确认、关闭 |
| `/warning/threshold` | 阈值规则 | 阈值规则配置 |
| `/ai/command` | AI 命令中心 | 流式 AI 对话、执行轨迹、研判 |
| `/ai/plan` | 应急预案 | AI 预案列表、详情、执行 |
| `/ai/knowledge` | 知识库 | 文档上传、检索、重建索引 |
| `/resource/material` | 物资 | 应急物资管理 |
| `/resource/personnel` | 人员 | 应急人员管理 |
| `/resource/vehicle` | 车辆设备 | 车辆设备管理 |
| `/resource/dispatch` | 调度记录 | 调度创建和状态跟踪 |
| `/map` | 流域地图 | 地图态势展示 |
| `/system/*` | 系统管理 | 用户、角色、组织、部门、日志 |

## 状态与权限

- `stores/user.ts` 管理用户、令牌和角色。
- `stores/app.ts` 管理布局、标签页等 UI 状态。
- `stores/aiConversation.ts` 和 `stores/situation.ts` 支持 AI 对话和态势相关状态。
- `directives/permission.ts` 提供基于角色的 UI 权限控制。
- 路由守卫负责登录态检查和跳转。

## API 层

`src/api/request.ts` 封装 Axios：

- 自动注入 JWT。
- 统一处理接口错误。
- 支持业务 API、AI API、知识库、资源、告警等模块化封装。

主要 API 文件：

- `api/auth.ts`
- `api/station.ts`
- `api/sensor.ts`
- `api/observation.ts`
- `api/alarm.ts`
- `api/threshold.ts`
- `api/flood.ts`
- `api/knowledge.ts`
- `api/resource.ts`
- `api/system.ts`

## 实时能力

- `composables/useWebSocket.ts`：告警 WebSocket。
- `composables/useSSE.ts`：通用 SSE。
- `composables/useAgentStream.ts`：AI 指挥台 SSE 流式事件消费。

AI 指挥台会消费 `session_init`、`agent_update`、`agent_message`、`risk_update`、`plan_update`、`evidence_update`、`trace_update` 等事件，并渲染过程轨迹和最终回答。

## 开发注意事项

- 开发服务器默认端口 `5173`。
- 生产镜像构建后由 Nginx 容器反向代理访问。
- 菜单权限和接口权限都要维护；前端隐藏不等于后端授权。
- Markdown/AI 输出渲染应保持 DOMPurify 清洗，避免 XSS。

