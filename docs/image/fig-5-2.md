# 图5-2 LangGraph 多智能体工作流实现图文字描述

## 对应论文位置
第5章 `5.2.2 多智能体工作流实现` 后。

## 建议图型
状态流转图，推荐 Mermaid `flowchart` 或 `stateDiagram-v2`。

## 文字描述
图从 `START` 开始，第一步进入 `supervisor`。`supervisor` 根据当前共享状态中的 `next_agent` 选择后续节点，可路由到 `data_analyst`、`risk_assessor`、`plan_generator`、`resource_dispatcher`、`notification`、`execution_monitor`、`parallel_dispatch` 或直接进入 `final_response`。所有非终止节点处理完成后都会回到 `supervisor`，由其再次判断是否继续下一步。图中应突出两类实现细节：一是 `parallel_dispatch` 代表资源调度与通知生成的并行输出聚合；二是 `final_response` 之后连接 `END`，表示图真正结束。若需要体现流式输出，可以在各节点旁用小注释说明其会触发 `agent_update`、`risk_update`、`plan_update` 或 `agent_message` 事件。

## 必含元素
- `START -> supervisor`
- `supervisor -> 各 agent`
- 各 agent 回到 `supervisor`
- `supervisor -> final_response -> END`
- `parallel_dispatch` 节点

## 标注建议
- `risk_assessor` 节点旁标注“输出 risk_level / risk_score”。
- `plan_generator` 节点旁标注“输出 plan_id / actions”。
- `final_response` 节点旁标注“生成最终文本响应”。

## 项目依据
- `water-info-ai/app/graph.py`
- `water-info-ai/app/main.py`
- `water-info-ai/tests/test_graph.py`
- `water-info-ai/tests/test_supervisor_routing.py`

