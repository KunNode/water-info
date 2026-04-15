# 大屏与地图改造设计（方案 A）

## 1. 背景与目标

当前前端存在两类核心问题：

1. 地图页与大屏依赖在线瓦片服务（Leaflet + OSM/CartoDB），离线不可用且受外网稳定性影响。
2. 大屏与 Dashboard 关键图表使用硬编码假数据，无法反映后端真实监测与告警状态。

本次采用 **方案 A（一次性完成 6 个 Phase）**，以 SVG 示意图 + ECharts 完成地图统一与数据真实化改造。

## 2. 范围

### 2.1 In Scope

1. 新增/完善翠屏湖流域 SVG 示意图资源（`src/assets/cuiping-lake.svg`）。
2. 建立统一地图渲染能力（`src/composables/useLakeMap.ts`），用于大屏和地图页。
3. 改造 `views/bigscreen/index.vue`：
   - 中央地图 Leaflet → ECharts + SVG；
   - 左右图表与浮动指标全部改为 API 驱动；
   - 告警联动（地图脉冲、列表、站点指标）统一来源。
4. 改造 `views/map/index.vue`：
   - Leaflet → ECharts + SVG；
   - 保留站点类型筛选、tooltip 展示等核心交互。
5. 改造 `views/dashboard/index.vue`：
   - 饼图/折线图/柱状图去除假数据，全部接后端 API。
6. 数据层配套：
   - 使用 `V7__cuiping_lake_demo_data.sql` 作为翠屏湖演示数据基线。
7. 清理前端 Leaflet 依赖（`leaflet`、`@types/leaflet`）。

### 2.2 Out of Scope

1. 后端 API 协议变更（本次仅消费既有接口）。
2. 新增地图引擎或三方 GIS SDK。
3. AI 服务流程变更。

## 3. 方案概述

### 3.1 地图技术路线

采用 ECharts 作为统一地图可视化引擎：

1. 底图层：翠屏湖 SVG 示意图。
2. 站点层：`scatter`（正常）+ `effectScatter`（告警脉冲）。
3. 交互层：tooltip 展示站点基本信息与最新值，支持 resize。

> 说明：当前 `useLakeMap.ts` 已使用“SVG 作为背景 + ECharts 坐标叠加”的实现方式，能满足离线、动效、交互、主题统一目标。  
> 与 `registerMap(svg)` 路线相比，该方式落地更稳、改造成本更低，保留后续升级为 `registerMap` 的空间。

### 3.2 坐标体系

采用 **站点 code → SVG 像素坐标映射** 作为前端地图唯一绘制依据：

1. 不依赖 `lat/lon` 做地图投影；
2. `lat/lon` 保留为站点业务属性（后台管理与数据记录用途）；
3. 地图渲染严格通过映射表驱动，避免跨页坐标偏差。

## 4. 页面改造设计

### 4.1 BigScreen（`views/bigscreen/index.vue`）

#### 4.1.1 数据来源

1. 站点统计：`getStations`、`getSensors`、`getAlarms`、`getObservations(今日)`。
2. 站点类型分布：`getStations` 结果按 `type` 分组计数。
3. 水位趋势（24h）：目标水位站 `getObservations(metric=WATER_LEVEL)`。
4. 降雨统计（7日）：目标雨量站 `getObservations(metric=RAINFALL)` 按天聚合。
5. 浮动指标（最高水位/最大雨量/最大流量）：按站点类型取 `getLatestObservation` 后求最大。
6. 站点排名：各站最新观测值降序（显示前 N）。
7. 地图告警态：`OPEN` 告警站点集合映射到 `effectScatter`。

#### 4.1.2 刷新策略

1. 页面初始化加载一次全量数据；
2. 每 30s 轮询刷新；
3. 全屏切换与窗口 resize 时触发图表和地图 resize。

### 4.2 Map（`views/map/index.vue`）

#### 4.2.1 功能保留与替换

1. 保留：站点类型筛选、站点数量显示、站点状态图例、悬浮信息。
2. 替换：Leaflet 地图容器与 marker 体系 → `useLakeMap` 数据驱动渲染。

#### 4.2.2 交互一致性

1. 筛选后只渲染当前类型站点；
2. 状态与告警颜色编码与大屏保持一致；
3. Tooltip 字段与大屏统一（站名、编码、类型、最新值、告警状态）。

### 4.3 Dashboard（`views/dashboard/index.vue`）

1. 水位趋势折线：替换掉 `Math.random/Math.sin` 假数据，使用真实 observation 时间序列。
2. 降雨统计柱状：按近 7 日真实数据聚合。
3. 站点状态饼图：按 `getStations` 实时分组。
4. 卡片统计：沿用既有 API，保持口径一致。

## 5. 数据与口径

### 5.1 口径定义

1. “活跃告警” = `status=OPEN`。
2. “今日数据量” = 当日 `observedAt` 在 `[00:00:00, 23:59:59]` 的 observation 总量。
3. “降雨量 7 日” = 自然日聚合（按站点本地日期字符串分桶）。
4. 排名值统一保留合理小数位（2 位或按指标单位规则）。

### 5.2 演示数据

`V7__cuiping_lake_demo_data.sql` 作为前后台联调基线，确保：

1. 翠屏湖站点编码与前端坐标映射一致；
2. 观测数据覆盖 WATER_LEVEL / RAINFALL / FLOW；
3. 存在可视化告警样例以验证脉冲效果。

## 6. 依赖与清理

1. 前端卸载 Leaflet 相关依赖：
   - `leaflet`
   - `@types/leaflet`
2. 清理对应 import、样式引用与 marker 相关遗留代码。

## 7. 实施顺序（执行版）

1. Phase 1：确认并修正 `V7__cuiping_lake_demo_data.sql`（数据一致性）。
2. Phase 2：完善 `cuiping-lake.svg` 与 `useLakeMap.ts`（通用地图能力）。
3. Phase 3：完成 `bigscreen/index.vue` 地图替换与图表 API 化。
4. Phase 4：完成 `map/index.vue` Leaflet 替换。
5. Phase 5：完成 `dashboard/index.vue` 图表 API 化。
6. Phase 6：移除 Leaflet 依赖并清理引用。

## 8. 风险与对策

1. **风险：批量拉取最新观测导致接口请求较多。**  
   对策：并发受控；后续可追加“批量最新值”后端接口（本次不改协议）。
2. **风险：站点编码与 SVG 坐标映射不一致导致点位缺失。**  
   对策：以 `station.code` 建立单一映射表并在加载时记录缺失项。
3. **风险：图表空数据场景显示不佳。**  
   对策：统一空态处理（空数组 + 文案），避免抛错与 NaN 展示。

## 9. 验收标准

1. 大屏、地图页在断网环境可正常显示地图。
2. 三页关键图表不再使用硬编码假数据。
3. 地图点位、告警脉冲、tooltip 与站点筛选均可用。
4. `leaflet` 及类型依赖已移除，代码无残留引用。
5. 以 V7 演示数据启动后，可看到完整翠屏湖场景联动。
