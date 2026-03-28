"""测试统一 JSON 解析器"""

from __future__ import annotations

from app.utils.json_parser import extract_json


class TestExtractJsonObject:
    """测试提取 JSON 对象"""

    def test_pure_json(self):
        text = '{"risk_level": "high", "risk_score": 75.0}'
        result = extract_json(text)
        assert result is not None
        assert result["risk_level"] == "high"
        assert result["risk_score"] == 75.0

    def test_markdown_code_block(self):
        text = """这是风险评估结果：

```json
{"risk_level": "moderate", "risk_score": 50.0, "trend": "rising"}
```

以上是评估结果。"""
        result = extract_json(text)
        assert result is not None
        assert result["risk_level"] == "moderate"
        assert result["trend"] == "rising"

    def test_markdown_code_block_no_lang(self):
        text = """结果如下：

```
{"risk_level": "low", "risk_score": 20.0}
```
"""
        result = extract_json(text)
        assert result is not None
        assert result["risk_level"] == "low"

    def test_json_with_surrounding_text(self):
        text = '根据分析，风险评估结果如下：{"risk_level": "critical", "risk_score": 95.0} 请立即采取措施。'
        result = extract_json(text)
        assert result is not None
        assert result["risk_level"] == "critical"

    def test_nested_json(self):
        text = '{"plan_id": "EP-001", "actions": [{"action_id": "A-001", "priority": 1}]}'
        result = extract_json(text)
        assert result is not None
        assert result["plan_id"] == "EP-001"
        assert len(result["actions"]) == 1

    def test_invalid_json_returns_none(self):
        text = "这不包含任何 JSON 数据"
        result = extract_json(text)
        assert result is None

    def test_empty_string_returns_none(self):
        result = extract_json("")
        assert result is None

    def test_none_text_returns_none(self):
        result = extract_json(None)
        assert result is None

    def test_malformed_json_returns_none(self):
        text = '{"risk_level": "high", "risk_score": }'
        result = extract_json(text)
        assert result is None


class TestExtractJsonArray:
    """测试提取 JSON 数组"""

    def test_pure_array(self):
        text = '[{"type": "人员", "quantity": 10}, {"type": "设备", "quantity": 5}]'
        result = extract_json(text, expect_array=True)
        assert result is not None
        assert isinstance(result, list)
        assert len(result) == 2

    def test_markdown_wrapped_array(self):
        text = """资源调度方案：

```json
[
    {"resource_type": "人员", "quantity": 20},
    {"resource_type": "物资", "quantity": 100}
]
```
"""
        result = extract_json(text, expect_array=True)
        assert result is not None
        assert isinstance(result, list)
        assert len(result) == 2

    def test_array_with_surrounding_text(self):
        text = '通知方案如下：[{"target": "值班员", "channel": "sms"}] 以上为通知列表。'
        result = extract_json(text, expect_array=True)
        assert result is not None
        assert isinstance(result, list)

    def test_empty_array(self):
        text = "[]"
        result = extract_json(text, expect_array=True)
        assert result is not None
        assert isinstance(result, list)
        assert len(result) == 0

    def test_expect_array_but_get_object_still_works(self):
        """即使 expect_array=True，如果只有对象也应尝试返回"""
        text = '{"key": "value"}'
        result = extract_json(text, expect_array=True)
        # Should still return the object as fallback
        assert result is not None
