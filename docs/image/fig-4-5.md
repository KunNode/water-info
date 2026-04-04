# 图4-5 核心数据库 ER 图文字描述

## 对应论文位置
第4章 `4.3.3 数据关系设计` 后。

## 建议图型
ER 图，推荐分区展示“监测数据域”“告警域”“权限域”。

## 文字描述
整张 ER 图建议分三块。第一块是监测数据域，以 `station_region`、`station`、`station_contact`、`sensor_type`、`sensor`、`metric`、`unit`、`observation_batch`、`observation_batch_item`、`observation`、`data_quality` 为主。关系上，`station_region` 与 `station` 是一对多，`station` 与 `sensor` 是一对多，`metric` 与 `unit` 是多对一，`observation_batch` 与 `observation_batch_item` 是一对多，`station`、`sensor`、`metric` 与 `observation` 都存在关联。第二块是告警域，以 `alert_rule`、`alert_rule_scope`、`alert_rule_action`、`alert_event`、`alert_event_observation`、`alert_notification` 为主，突出规则定义、规则作用范围、规则动作、告警实例和通知投递的关系。第三块是权限域，以 `organization`、`user`、`role`、`permission`、`user_role`、`role_permission`、`user_session`、`operation_log` 为主，突出基于角色的访问控制。若论文正文更偏工程表达，可在图旁补一句说明：论文中“站点、观测、阈值规则、告警、用户权限”这些核心业务对象，已在数据库层分别有实体或实体组实现。

## 必含元素
- 监测核心实体：站点、传感器、指标、观测。
- 告警核心实体：规则、事件、通知。
- 权限核心实体：用户、角色、权限、组织。
- 关键关系：一对多、多对多、桥接表。

## 标注建议
- 监测域建议用蓝色，告警域用橙色，权限域用绿色。
- 可在图底部补充“查询优化索引见 V5 迁移脚本”。

## 项目依据
- `water-info-platform/src/main/resources/db/migration/V1__water_info_schema.sql`
- `water-info-platform/src/main/resources/db/migration/V2__user_access_control.sql`
- `water-info-platform/src/main/resources/db/migration/V5__performance_indexes.sql`

