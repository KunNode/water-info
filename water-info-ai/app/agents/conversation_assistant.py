"""General conversational assistant node."""

from __future__ import annotations

import json

from app.services.llm import get_llm


def _fallback_reply(query: str) -> str:
    lowered = query.strip().lower()
    if lowered in {"你好", "您好", "hi", "hello", "hey"}:
        return (
            "你好，我是防汛 AI 助手。\n\n"
            "我可以陪你一起看站点状态、研判风险、生成预案，也可以先回答你想了解的内容。"
            "如果你愿意，我们可以从某个站点、某段河道，或者当前整体水情开始。"
        )
    if any(keyword in query for keyword in ["你能做什么", "怎么用", "帮助", "help"]):
        return (
            "我可以协助你做几类事情：\n\n"
            "- 查看某个站点、闸口、水库的实时状态\n"
            "- 研判当前洪水风险和趋势\n"
            "- 生成或细化防汛应急预案\n"
            "- 解释当前系统里已有的预案、资源和通知信息\n\n"
            "你可以直接说，比如：`东湖站现在状态怎么样` 或 `生成城区防洪应急预案`。"
        )
    return (
        "我在这儿。你可以像和助手聊天一样直接问我，也可以让我帮你看某个站点、研判风险，或者一起梳理防汛方案。"
    )


async def conversation_assistant_node(state: dict) -> dict:
    query = str(state.get("user_query", ""))
    llm = get_llm()
    reply = _fallback_reply(query)

    if llm.is_enabled:
        try:
            response = await llm.ainvoke(
                json.dumps(
                    {
                        "user_query": query,
                        "intent": state.get("intent", "general_chat"),
                        "supervisor_reasoning": state.get("supervisor_reasoning"),
                        "known_context": {
                            "has_data_summary": bool(state.get("data_summary")),
                            "has_risk_assessment": bool(state.get("risk_assessment")),
                            "has_plan": bool(state.get("emergency_plan")),
                            "focus_station_query": state.get("focus_station_query"),
                        },
                    },
                    ensure_ascii=False,
                    indent=2,
                ),
                system_prompt=(
                    "你是一个真正的防汛 AI 助手，而不是生硬的查询接口。"
                    "当用户在打招呼、闲聊、询问你能做什么，或者表达模糊需求时，"
                    "请自然、友好、简洁地回应，并主动引导用户下一步可以怎么问。"
                    "只有在用户明确要求时才进入数据分析语气。"
                    "输出 Markdown。"
                ),
                temperature=0.5,
            )
            content = getattr(response, "content", "").strip()
            if content:
                reply = content
        except Exception:
            pass

    return {
        "current_agent": "conversation_assistant",
        "final_response": reply,
        "messages": [{"role": "conversation_assistant", "content": reply}],
    }
