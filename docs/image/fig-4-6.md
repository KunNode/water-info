# 图4-6 实时通信机制图文字描述

## 对应论文位置
第4章 `4.4.2 实时通信设计` 后。

## 建议图型
双泳道时序图，左侧 WebSocket，右侧 SSE。

## 文字描述
图左半部分展示告警实时推送链路。顺序为“告警页面 -> `useWebSocket('/ws/alarms')` -> 浏览器 WebSocket 连接 -> Nginx `/ws/` 升级代理 -> Spring Boot `AlarmWebSocketHandler` -> 广播 `ALARM_NEW / ALARM_UPDATE / ALARM_DELETE` 消息 -> 前端收到新消息后弹出‘收到新告警’提示并刷新表格”。图右半部分展示 AI 流式返回链路。顺序为“AI 智能指挥台 -> `useSSE()` -> POST `/api/v1/flood/query/stream` -> 请求携带 Bearer Token -> Nginx 对该路径关闭缓冲 -> 平台转发到 AI 服务 -> AI 服务依次输出 `session_init`、`agent_update`、`risk_update`、`plan_update`、`agent_message` 与最终完成事件 -> 前端同步更新会话区、时间线、风险面板、预案面板和聊天消息”。整张图需要强调这两种机制的差异：WebSocket 面向平台主动广播离散事件，SSE 面向单次查询的连续文本与结构化事件流。

## 必含元素
- `useWebSocket.ts` 自动重连。
- `useSSE.ts` 的结构化事件解析。
- Nginx 对 `/api/v1/flood/query/stream` 的 `proxy_buffering off`。
- WebSocket 连接状态标签与 SSE 实时面板更新。

## 标注建议
- 左侧注明“全双工，持续连接”。
- 右侧注明“单向流式，面向一次查询”。
- 在请求头处标注“JWT/Bearer Token”。

## 项目依据
- `nginx.conf`
- `water-info-admin/src/composables/useWebSocket.ts`
- `water-info-admin/src/composables/useSSE.ts`
- `water-info-platform/src/main/java/com/waterinfo/platform/config/AlarmWebSocketHandler.java`
- `water-info-ai/app/main.py`

