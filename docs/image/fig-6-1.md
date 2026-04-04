# 图6-1 AI 服务自动化测试结果图文字描述

## 对应论文位置
第6章 `6.2.1 AI 服务自动化测试结果` 后。

## 建议图型
测试报告截图或统计结果图。

## 文字描述
如果采用截图，推荐截取测试报告中“Summary”和“Executed Commands / Result”区域，同屏展示日期、运行环境、测试结论和最终结果。核心文字应突出：`57 passed, 3 deselected, 1 warning in 5.22s`。若采用统计图，建议用一张简洁的柱状图或信息卡片组合，显示总测试数、通过数、跳过数、执行时间，并在下方列出主要测试类别，包括 API 冒烟测试、工作流测试、结构化结果测试、流式响应测试和容错回退测试。图中还可在角落补一条说明，指出天气数据目前使用模拟数据。

## 必含元素
- 测试日期：`2026-03-12`
- 测试框架：`pytest 9.0.2`
- 结果：`57 passed, 3 deselected`
- 用时：`5.22s`
- 关键类别：API smoke、workflow、streaming、resilience

## 标注建议
- 若使用截图，可在论文排版后加红框或箭头强调最终结果行。
- 若使用统计图，建议加一行脚注“当前天气接口为模拟数据，不影响核心工作流验证”。

## 项目依据
- `water-info-ai/TEST_REPORT.md`
- `water-info-ai/tests/test_main_api.py`
- `water-info-ai/tests/test_graph.py`
- `water-info-ai/tests/test_supervisor_routing.py`

