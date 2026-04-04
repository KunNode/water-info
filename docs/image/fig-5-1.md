# 图5-1 业务平台模块实现结构图文字描述

## 对应论文位置
第5章 `5.1.1 平台整体实现结构` 后。

## 建议图型
模块结构图或分层包结构图。

## 文字描述
图的中心是 `water-info-platform`。向外分为三层。最上层是通用支撑层，包括 `common`、`config`、`security` 和 `handler`，分别表示统一响应/异常处理、WebSocket/Redis/RateLimit/OpenAPI 配置、JWT 认证授权与元数据处理。中间层是业务模块层，按模块横向排布：`auth`、`station`、`sensor`、`observation`、`threshold`、`alarm`、`user`、`audit`、`ai`。每个业务模块内部都采用统一的分层结构：`entity -> dto/vo -> mapper -> service -> controller`。最下层是基础设施层，包括 PostgreSQL、Redis、Flyway、WebSocket。若希望更直观，可在 `alarm` 模块旁注明“状态机 + WebSocket 广播”，在 `ai` 模块旁注明“代理 AI 服务请求”，在 `user` 模块旁注明“RBAC”。

## 必含元素
- 模块名称：`station`、`observation`、`alarm`、`threshold`、`user`、`audit`、`ai`。
- 通用层：`config`、`security`、`common`。
- 模块内部统一分层模式。
- 基础设施：PostgreSQL、Redis、Flyway、WebSocket。

## 标注建议
- 用一个示意放大框展示任一模块的典型目录结构。
- 可在图旁补充“便于新增业务模块时保持一致工程组织方式”。

## 项目依据
- `water-info-platform/src/main/java/com/waterinfo/platform/module`
- `water-info-platform/src/main/java/com/waterinfo/platform/config`
- `water-info-platform/src/main/java/com/waterinfo/platform/security`

