# 通知推送实现 Task

## 目标

在现有告警能力基础上，补齐两类通知能力：

1. 站内通知：提供通知中心、未读数、通知列表、已读状态。
2. 浏览器实时推送：在页面在线时实时收到告警通知，并在合适场景下触发浏览器系统通知。

本 task 以“告警驱动通知”为第一阶段范围，不在本期内实现“浏览器关闭后仍可收到消息”的完整 Web Push 订阅体系。

## 调研结论

### 现有可复用能力

- 后端已经有告警实时广播基础：
  - `water-info-platform/src/main/java/com/waterinfo/platform/config/WebSocketConfig.java`
  - `water-info-platform/src/main/java/com/waterinfo/platform/config/AlarmWebSocketHandler.java`
  - `water-info-platform/src/main/java/com/waterinfo/platform/module/alarm/service/AlarmService.java`
- 前端已经有通用实时通信封装：
  - `water-info-admin/src/composables/useWebSocket.ts`
  - `water-info-admin/src/composables/useSSE.ts`
- 前端告警页已经消费 `/ws/alarms`：
  - `water-info-admin/src/views/alarm/index.vue`
- 顶部栏适合挂通知入口：
  - `water-info-admin/src/layout/components/Header.vue`

### 已发现缺口

- 当前 WebSocket 鉴权不完整：
  - 前端会把 JWT 作为 `?token=` 拼到 `/ws/alarms`
  - 后端 `AlarmWebSocketHandler` 没有解析 token
  - `SecurityConfig` 对除登录外的请求都要求认证，现状存在握手放行/鉴权不一致风险
- 当前“实时告警”只有页面级 toast，没有通知中心，也没有持久化未读通知
- 数据库虽然已有 `alert_rule_action` / `alert_notification` 等标准化表，但 Java 后端主业务当前使用的是 `public.alarm` 这套模型，直接切到标准化通知链路成本偏高

## 推荐方案

### 本期方案

围绕现有 `alarm` 领域做一层“用户通知”能力：

- 后端新增通知表，存储每条面向用户的站内通知
- 告警创建/更新时同步生成通知记录
- 后端新增独立通知 WebSocket 通道，向已登录用户推送通知事件
- 前端在头部增加通知中心，展示未读数量与最近通知
- 页面在线且浏览器授权时，对高等级告警触发 `Notification API`

### 为什么这样做

- 复用现有告警广播链路，改动最小
- 可以先把“站内通知 + 浏览器在线实时提醒”做出来
- 避免本期直接引入 Service Worker、VAPID、订阅管理、离线投递等高复杂度能力

### 暂不纳入本期

- 浏览器关闭后仍然推送的标准 Web Push
- 短信、邮件、钉钉、企业微信等外部渠道
- 通知偏好配置中心

## 数据与接口设计

### 建议新增表

建议在 Java 当前主用域补一张用户通知表，而不是直接改造 `alert_notification`：

- 表名：`sys_notification`
- 核心字段：
  - `id`
  - `user_id`
  - `type`，如 `ALARM_NEW` / `ALARM_UPDATE`
  - `title`
  - `content`
  - `level`
  - `biz_type`，固定先用 `ALARM`
  - `biz_id`，关联 `alarm.id`
  - `read_at`
  - `created_at`

### 建议新增接口

- `GET /api/v1/notifications`
  - 分页查询当前用户通知
- `GET /api/v1/notifications/unread-count`
  - 查询未读数
- `POST /api/v1/notifications/{id}/read`
  - 单条已读
- `POST /api/v1/notifications/read-all`
  - 全部已读

### 建议新增实时通道

- `GET /ws/notifications?token=...`

消息体建议统一为：

```json
{
  "type": "NOTIFICATION_NEW",
  "timestamp": 1713000000000,
  "data": {
    "id": "notification-id",
    "bizType": "ALARM",
    "bizId": "alarm-id",
    "level": "CRITICAL",
    "title": "出现新的严重告警",
    "content": "青山泵站水位超阈值",
    "read": false,
    "createdAt": "2026-04-13T16:00:00"
  }
}
```

## 任务拆解

### Task 1：补齐通知领域模型与数据库

**涉及文件**

- 新增：`water-info-platform/src/main/resources/db/migration/V7__notification_center.sql`
- 新增：`water-info-platform/src/main/java/com/waterinfo/platform/module/notification/entity/SysNotification.java`
- 新增：`water-info-platform/src/main/java/com/waterinfo/platform/module/notification/mapper/SysNotificationMapper.java`
- 新增：`water-info-platform/src/main/java/com/waterinfo/platform/module/notification/vo/NotificationVO.java`

**完成标准**

- 能保存当前用户的通知记录
- 支持按 `user_id + created_at` 查询
- 支持未读查询与已读更新

### Task 2：把告警事件转换成通知记录

**涉及文件**

- 修改：`water-info-platform/src/main/java/com/waterinfo/platform/module/alarm/service/AlarmService.java`
- 新增：`water-info-platform/src/main/java/com/waterinfo/platform/module/notification/service/NotificationService.java`

**完成标准**

- 新告警产生时创建通知
- 告警状态变化时按需创建通知
- 能按角色或用户范围确定接收人

**实现建议**

- 第一版先面向 `ADMIN` 和 `OPERATOR`
- `VIEWER` 是否接收通知作为可配置项留到后续

### Task 3：补齐通知实时推送通道与鉴权

**涉及文件**

- 新增：`water-info-platform/src/main/java/com/waterinfo/platform/config/NotificationWebSocketHandler.java`
- 修改：`water-info-platform/src/main/java/com/waterinfo/platform/config/WebSocketConfig.java`
- 修改：`water-info-platform/src/main/java/com/waterinfo/platform/security/SecurityConfig.java`
- 视实现方式新增：`water-info-platform/src/main/java/com/waterinfo/platform/config/WebSocketAuthHandshakeInterceptor.java`

**完成标准**

- 通知通道只允许已登录用户连接
- 后端能按用户维度或角色维度推送消息
- 明确解决当前 `/ws/alarms` token 只在前端传、后端未消费的问题

### Task 4：补齐通知查询与已读接口

**涉及文件**

- 新增：`water-info-platform/src/main/java/com/waterinfo/platform/module/notification/controller/NotificationController.java`
- 新增：`water-info-platform/src/main/java/com/waterinfo/platform/module/notification/dto/NotificationQueryRequest.java`
- 修改：必要的权限与 OpenAPI 配置

**完成标准**

- 前端可拉取通知列表
- 能单条已读、全部已读
- 能查询未读数量

### Task 5：前端接入通知中心

**涉及文件**

- 新增：`water-info-admin/src/api/notification.ts`
- 新增：`water-info-admin/src/stores/notification.ts`
- 新增：`water-info-admin/src/types/notification.ts` 或补充到 `src/types/models.ts`
- 新增：`water-info-admin/src/layout/components/NotificationBell.vue`
- 修改：`water-info-admin/src/layout/components/Header.vue`

**完成标准**

- 头部显示未读数
- 点击可查看最近通知
- 点击通知可跳转到对应告警详情页或告警列表页
- 支持单条已读与全部已读

### Task 6：前端接入浏览器系统通知

**涉及文件**

- 新增：`water-info-admin/src/composables/useBrowserNotification.ts`
- 修改：`water-info-admin/src/stores/notification.ts`
- 修改：`water-info-admin/src/main.ts`

**完成标准**

- 首次进入时按业务时机请求通知权限，不要在页面加载瞬间直接弹窗
- 页面在线收到严重告警时，在标签页隐藏或失焦场景触发浏览器系统通知
- 点击系统通知后可回到系统并打开告警页面

## 风险与注意事项

### 1. WebSocket 鉴权风险

这是当前最需要优先补的点。否则“通知中心”做完后，实时链路仍然可能在登录态下不稳定或存在越权风险。

### 2. 通知去重

同一个告警持续更新时，不能无限刷通知。建议：

- 新告警：一定发通知
- 状态切换：发通知
- 普通重复触发：只更新 `alarm`，不重复发站内通知

### 3. 浏览器通知权限策略

不要在应用启动后立即申请权限，建议在用户点击“开启通知提醒”后再申请，避免被浏览器静默拒绝。

### 4. 范围控制

本期“浏览器实时推送”建议定义为：

- 用户已登录并打开系统页面时，能实时收到通知
- 页面在后台时，能弹系统通知

如果要求“浏览器关闭后仍推送”，需要另开二期实现 Web Push。

## 验收标准

- 新告警触发后，`ADMIN/OPERATOR` 账户能在站内通知中心看到新通知
- 页面在线时，顶部未读数能实时刷新
- 页面在后台时，高等级告警能触发浏览器系统通知
- 点击通知可以进入告警相关页面
- 已读、全部已读、未读统计都能正常工作
- WebSocket 连接具备明确鉴权逻辑

## 建议开发顺序

1. 先做后端通知表和接口
2. 再补实时通道鉴权
3. 再做前端通知中心
4. 最后接入浏览器系统通知

## 备注

如果后续确定必须支持“浏览器关闭后继续推送”，建议新增二期 task，单独引入：

- Service Worker
- Push Subscription 管理
- VAPID 公私钥
- 后端订阅存储与失效清理
- Web Push 服务端投递
