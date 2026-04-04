# 图4-4 共享状态与动态路由机制图文字描述

## 对应论文位置
第4章 `4.2.2 状态共享与路由机制设计` 后。

## 建议图型
状态图或“共享状态 + 路由”组合图。

## 文字描述
图左侧放置一个共享状态容器，标题为 `FloodResponseState`。容器内部按分组列出关键字段：会话控制组包括 `session_id`、`user_query`、`messages`、`chat_history`、`iteration`、`current_agent`、`next_agent`；数据采集组包括 `station_data`、`overview_data`、`alarm_data`、`threshold_rules`、`weather_forecast`、`historical_floods`、`data_summary`；业务结果组包括 `risk_assessment`、`emergency_plan`、`resource_plan`、`notifications`、`execution_progress`、`final_response`、`error`。图右侧放置节点流转区，以 `supervisor` 为起点，通过条件分支连接到 `data_analyst`、`risk_assessor`、`plan_generator`、`resource_dispatcher`、`notification`、`execution_monitor` 和 `parallel_dispatch`。所有子节点完成后都回到 `supervisor`，最后由 `final_response` 汇总并结束。图中应补充两个控制约束：一是 `iteration` 超限时强制结束，二是 `error` 存在时强制结束。

## 必含元素
- `FloodResponseState` 关键字段分组。
- `messages` 采用追加合并策略。
- `next_agent` 控制条件路由。
- 所有子节点回跳 `supervisor`。
- `final_response -> END`。

## 标注建议
- 在 `messages` 旁标注“reducer: append”。
- 在 `supervisor` 旁标注“iteration + 1”。
- 在结束分支旁标注“`__end__` -> final_response”。

## 项目依据
- `water-info-ai/app/state.py`
- `water-info-ai/app/graph.py`
- `water-info-ai/tests/test_supervisor_routing.py`

