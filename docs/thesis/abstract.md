# 摘要

近年来，受极端天气频发、城市化进程加快和防洪应急业务复杂化等因素影响，传统依赖人工研判和静态文本预案的防洪应急模式已难以满足实时响应和协同处置需求。针对现有防洪应急系统中监测与决策脱节、预案动态生成能力不足以及执行闭环不完整等问题，本文设计并实现了一种基于多智能体协同的防洪应急预案生成与执行系统。

本文结合防洪应急业务特点，构建了由前端管理端、业务平台服务、AI 智能服务、数据库与缓存服务组成的分层协同架构。其中，业务平台基于 Spring Boot 实现站点管理、观测数据管理、阈值规则配置、告警处理、用户权限控制与审计日志等核心业务功能；AI 服务基于 FastAPI 与 LangGraph 构建多智能体工作流，设计了监督智能体、数据分析智能体、风险评估智能体、预案生成智能体、资源调度智能体、通知智能体和执行监控智能体，实现了从实时数据获取、风险评估到预案生成、资源联动和执行跟踪的智能协同处理；前端管理端基于 Vue3 实现业务管理、风险展示和 AI 智能指挥交互，并结合 WebSocket 与 Server-Sent Events 实现实时告警推送和流式结果展示。

在系统实现过程中，本文重点采用了“AI 服务直接读取数据库、业务写入统一通过平台服务”的协同设计，以兼顾实时分析效率和业务规则一致性。同时，系统通过共享状态对象在多智能体之间传递结构化中间结果，提高了复杂任务处理的稳定性和可解释性。测试结果表明，系统能够完成防洪态势分析、风险等级判断、应急预案生成、资源调度建议和通知方案输出等核心任务，具备较好的功能完整性和工程可实现性。AI 模块在现有自动化测试中取得了 57 项测试全部通过的结果，并在端到端冒烟测试中成功完成完整防汛应急响应方案生成。

本文研究表明，将多智能体协同机制应用于防洪应急预案生成与执行场景，能够有效提升系统在复杂业务流程中的任务分工能力、响应效率和辅助决策能力。该系统可为智慧水务和智能应急系统建设提供一定参考，也为多智能体技术在垂直业务场景中的工程应用提供了实践基础。

**关键词：** 多智能体协同；防洪应急；应急预案生成；LangGraph；智慧水务；智能决策

# Abstract

In recent years, frequent extreme weather events, accelerated urbanization, and the growing complexity of flood emergency management have made traditional response approaches based on manual judgment and static text plans increasingly inadequate for real-time decision-making and coordinated response. To address the problems of weak linkage between monitoring and decision-making, insufficient dynamic plan generation, and incomplete execution closed-loop in existing flood emergency systems, this thesis designs and implements a multi-agent collaborative system for flood emergency plan generation and execution.

According to the characteristics of flood emergency management, a layered collaborative architecture is constructed, consisting of a frontend administration interface, a business platform service, an AI intelligent service, and database and cache services. The business platform, built with Spring Boot, implements core functions including station management, observation data management, threshold rule configuration, alarm handling, user authorization, and audit logging. The AI service, built with FastAPI and LangGraph, organizes a multi-agent workflow composed of a supervisor agent, data analyst agent, risk assessor agent, plan generator agent, resource dispatcher agent, notification agent, and execution monitor agent, thereby enabling intelligent collaborative processing from real-time data acquisition and risk assessment to emergency plan generation, resource coordination, and execution tracking. The frontend administration interface, developed with Vue3, provides business management, risk visualization, and AI command interaction, while WebSocket and Server-Sent Events are used to support real-time alarm pushing and streaming result presentation.

During implementation, this thesis adopts a collaborative strategy in which the AI service reads data directly from the database while all business write operations are uniformly handled through the platform service, so as to balance real-time analysis efficiency and business rule consistency. In addition, the system transmits structured intermediate results among agents through a shared state object, which improves the stability and interpretability of complex task processing. Experimental and testing results show that the system can complete key tasks such as flood situation analysis, risk level assessment, emergency plan generation, resource dispatch suggestion, and notification output, demonstrating good functional completeness and engineering feasibility. In the current automated verification, the AI module passed 57 test cases, and it also successfully completed an end-to-end smoke test for full flood emergency response plan generation.

The study shows that applying multi-agent collaboration to flood emergency plan generation and execution can effectively improve task decomposition capability, response efficiency, and decision-support performance in complex business processes. The proposed system can provide a useful reference for smart water management and intelligent emergency response systems, and also offers practical experience for the engineering application of multi-agent technologies in domain-specific scenarios.

**Keywords:** multi-agent collaboration; flood emergency response; emergency plan generation; LangGraph; smart water management; intelligent decision support
