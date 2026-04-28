# Water Info AI Test Report

Date: 2026-03-12
Service: `water-info-ai`
Mode: real database + real LLM + simulated weather

## Summary

The AI module is currently runnable end to end.

- Automated test suite: `57 passed, 3 deselected`
- Full workflow smoke test: passed
- Current weather mode: simulated data
- Main remaining limitation: weather is intentionally mocked and does not call a live weather provider

## Test Environment

- OS: Windows
- Python: 3.13.5
- Test runner: pytest 9.0.2
- LLM gateway: SiliconFlow OpenAI-compatible API
- Database: configured PostgreSQL instance
- Weather: mock path in `app/tools/weather_tools.py`

## Designed Test Cases

| ID | Scenario | Type | Expected Result | Status |
| --- | --- | --- | --- | --- |
| TC-01 | Service health check | API smoke | `/health` returns `status=ok` | Passed |
| TC-02 | Flood query basic response | API smoke | `/api/v1/flood/query` returns a valid response envelope | Passed |
| TC-03 | Flood query SSE stream | API smoke | `/api/v1/flood/query/stream` emits SSE events successfully | Passed |
| TC-04 | Startup with DB warmup failure | Resilience | service still starts when DB warmup fails | Passed |
| TC-05 | Data-only query path | Workflow | `data_analyst` returns deterministic summary quickly | Passed |
| TC-06 | Risk query routing | Workflow | supervisor routes risk intent to `risk_assessor` | Passed |
| TC-07 | Structured risk assessment | Workflow | risk level and score are generated from overview data | Passed |
| TC-08 | Plan generation | Workflow | emergency plan is produced with actions and metadata | Passed |
| TC-09 | Final response rendering | Workflow | final response is generated deterministically without extra LLM call | Passed |
| TC-10 | Full emergency workflow | End-to-end smoke | query completes with plan, resources, notifications, and risk result | Passed |
| TC-11 | Simulated weather fallback | Integration | weather tools return mock payload when no key is configured | Passed |
| TC-12 | LLM fallback path | Resilience | agent falls back to LLM path when deterministic bundle is unavailable | Passed |

## Executed Commands

```powershell
uv run pytest
```

Result:

```text
57 passed, 3 deselected, 1 warning in 5.22s
```

The warning is a pytest cache permission warning and does not affect functional results.

## End-to-End Smoke Test

Query:

```text
制定完整的防汛应急响应方案
```

Observed result:

```json
{
  "elapsed_seconds": 1.62,
  "error": null,
  "risk_level": "moderate",
  "risk_score": 46.3,
  "plan_id": "EP-20260312-A40E",
  "actions_count": 6,
  "resources_count": 6,
  "notifications_count": 2
}
```

Interpretation:

- The multi-agent workflow completed successfully
- Supervisor routing worked as expected
- Risk assessment, plan generation, resource dispatch, and notification generation all completed
- No timeout or retry loop was observed in this run

## Simulated Weather Verification

Current configuration intentionally does not set `WEATHER_API_KEY` in `.env`.

Weather tool behavior was verified separately:

```json
{
  "forecast": {
    "source": "模拟数据",
    "note": "此为模拟数据，请配置 weather_api_key 获取真实预报"
  },
  "warning": {
    "source": "模拟数据",
    "note": "此为模拟数据，请配置 weather_api_key 获取真实预警"
  }
}
```

This confirms the workflow is using mock weather data rather than a live weather API.

## Files Covered by New or Updated Tests

- `tests/test_main_api.py`
- `tests/test_final_response.py`
- `tests/test_agents.py`
- `tests/test_supervisor_routing.py`

## Conclusion

The AI module has passed both automated verification and a live end-to-end smoke test under the current configuration.

The system is suitable for demonstration and integration testing with:

- real PostgreSQL data
- real LLM generation through SiliconFlow
- simulated weather inputs

## Known Limitations

- Weather data is mocked by design in the current setup
- Test output shows one non-blocking pytest cache permission warning
