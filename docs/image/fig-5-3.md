# 图5-3 AI 智能指挥页面截图文字描述

## 对应论文位置
第5章 `5.3.2 AI 智能指挥页面实现` 后。

## 建议图型
系统页面截图，建议使用完整页面截图。

## 文字描述
截图应展示 `/ai/command` 页面完整布局。页面顶部是深色标题栏，左侧为平台图标和“AI 智能指挥台”，中间可见当前会话 `Session` 标识，右侧显示风险标签和返回按钮。主体区域采用左右双栏结构。左侧大区域是聊天面板，包含历史消息、用户输入框、发送按钮和“分析当前水情”“生成防洪应急预案”“评估当前风险等级”“调度应急资源”等快捷指令。聊天区中应至少出现一条用户提问、一条正在流式输出的助手消息，以及若干带颜色标识的 Agent 分体消息气泡，用来体现打字机式过程输出。右侧侧栏自上而下包括“智能体进度”“风险等级”“预案状态”“活跃告警”“会话信息”五个面板，其中智能体进度面板显示 `supervisor`、`data_analyst`、`risk_assessor`、`plan_generator`、`resource_dispatcher`、`notification` 的状态，风险等级面板显示圆形风险徽标，预案状态面板显示预案名称与进度条，活跃告警面板显示最近告警，会话信息面板显示 session、开始时间和交互次数。

## 必含可视区域
- 顶部标题栏与风险标签。
- 左侧聊天区与快捷指令。
- 至少一条 Agent 消息气泡。
- 右侧五个状态面板。
- 会话编号和时间信息。

## 截图建议
- 选择一次真实流式查询过程截图，而不是空白初始页。
- 优先让 `risk_update` 和 `plan_update` 已经发生，这样右侧面板内容更完整。
- 页面允许任何已登录用户访问，因此无需额外展示管理员特权。

## 项目依据
- `water-info-admin/src/views/ai/command/index.vue`
- `water-info-admin/src/views/ai/command/components/ChatPanel.vue`
- `water-info-admin/src/views/ai/command/components/AgentTimeline.vue`
- `water-info-admin/src/views/ai/command/components/RiskPanel.vue`
- `water-info-admin/src/views/ai/command/components/PlanStatus.vue`
- `water-info-admin/src/views/ai/command/components/ActiveAlerts.vue`
- `water-info-admin/src/views/ai/command/components/SessionInfo.vue`

