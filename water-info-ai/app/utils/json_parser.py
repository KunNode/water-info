"""统一 JSON 解析工具

从 LLM 回复中可靠地提取 JSON，支持 markdown 代码块包裹和纯文本两种形式。
"""

from __future__ import annotations

import json
import re
from typing import Any


def extract_json(text: str, expect_array: bool = False) -> Any | None:
    """从 LLM 回复文本中提取 JSON 对象或数组。

    解析策略:
    1. 先尝试匹配 ```json ... ``` 代码块
    2. 再用 find/rfind 定位 JSON 边界
    3. json.loads 解析，失败返回 None

    Args:
        text: LLM 回复文本
        expect_array: True 则优先提取 JSON 数组 ([...])，否则提取对象 ({...})

    Returns:
        解析后的 dict / list，解析失败返回 None
    """
    if not text or not text.strip():
        return None

    # 策略1: 提取 markdown 代码块 ```json ... ``` 或 ``` ... ```
    code_block_pattern = re.compile(r"```(?:json)?\s*\n?(.*?)\n?\s*```", re.DOTALL)
    for match in code_block_pattern.finditer(text):
        candidate = match.group(1).strip()
        parsed = _try_parse(candidate, expect_array)
        if parsed is not None:
            return parsed

    # 策略2: find/rfind 定位 JSON 边界
    open_char, close_char = ("[", "]") if expect_array else ("{", "}")
    start = text.find(open_char)
    end = text.rfind(close_char)
    if start >= 0 and end > start:
        candidate = text[start : end + 1]
        parsed = _try_parse(candidate, expect_array)
        if parsed is not None:
            return parsed

    # 如果 expect_array 失败，也尝试提取对象（反之亦然）
    alt_open, alt_close = ("{", "}") if expect_array else ("[", "]")
    start = text.find(alt_open)
    end = text.rfind(alt_close)
    if start >= 0 and end > start:
        candidate = text[start : end + 1]
        try:
            return json.loads(candidate)
        except (json.JSONDecodeError, ValueError):
            pass

    return None


def _try_parse(candidate: str, expect_array: bool) -> Any | None:
    """尝试解析 JSON 字符串，验证类型匹配。"""
    try:
        result = json.loads(candidate)
        if expect_array and isinstance(result, list):
            return result
        if not expect_array and isinstance(result, dict):
            return result
        # 类型不匹配但仍然是有效 JSON，也返回
        return result
    except (json.JSONDecodeError, ValueError):
        return None
