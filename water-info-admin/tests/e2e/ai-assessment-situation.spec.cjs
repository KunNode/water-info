const { expect, test } = require("@playwright/test")

const VIEWPORT = { width: 1440, height: 1000 }
const TRACE_ID = "e2e-situation"
const HIGH_ASSESSMENT_TEMPLATE = {
  id: "assessment-high-1",
  stationId: "station-001",
  stationName: "翠屏湖主坝",
  metricType: "WATER_LEVEL",
  level: "HIGH",
  summary: "主坝水位连续抬升，建议立即启动高风险巡检和会商研判。",
  planExcerpt: "加密水位复核，核查上游来水，并准备预警广播。",
  source: "EVENT",
}

function apiResponse(data) {
  return {
    code: 200,
    message: "ok",
    data,
    traceId: TRACE_ID,
    timestamp: Date.now(),
  }
}

function pageResponse(records = [], size = 100) {
  return {
    records,
    total: records.length,
    page: 1,
    size,
    pages: records.length > 0 ? 1 : 0,
  }
}

function buildHighAssessment() {
  const assessedAt = new Date(Date.now() - 5 * 60 * 1000).toISOString()
  return {
    ...HIGH_ASSESSMENT_TEMPLATE,
    assessedAt,
    createdAt: assessedAt,
  }
}

async function primeClientState(page) {
  await page.addInitScript(() => {
    localStorage.setItem("water_access_token", "playwright-e2e-token")
    localStorage.removeItem("water_ai_current_session_id")
    localStorage.removeItem("water_ai_input_draft")
    localStorage.setItem("water_ai_drawer_open", "false")
  })
}

async function mockSituationApis(page, assessments) {
  await page.route("**/api/v1/**", async (route) => {
    const url = new URL(route.request().url())
    const key = `${route.request().method()} ${url.pathname}`
    let payload

    switch (key) {
      case "GET /api/v1/ai-assessments":
        payload = apiResponse(assessments)
        break
      case "GET /api/v1/conversations":
        payload = apiResponse([])
        break
      case "GET /api/v1/stations":
        payload = apiResponse(pageResponse([], 100))
        break
      case "GET /api/v1/sensors":
        payload = apiResponse(pageResponse([], 1))
        break
      case "GET /api/v1/alarms":
        payload = apiResponse(pageResponse([], 10))
        break
      case "GET /api/v1/observations":
        payload = apiResponse(pageResponse([], 500))
        break
      case "GET /api/v1/observations/latest":
        payload = apiResponse(null)
        break
      case "POST /api/v1/observations/latest/batch":
        payload = apiResponse([])
        break
      default:
        payload = apiResponse({})
        break
    }

    await route.fulfill({
      status: 200,
      contentType: "application/json",
      body: JSON.stringify(payload),
    })
  })
}

async function expectBigscreenHighAssessment(page, assessment) {
  await expect(page.getByText("AI 综合研判")).toBeVisible()
  await expect(page.getByText(assessment.source, { exact: true })).toBeVisible()
  await expect(page.getByText("HIGH", { exact: true })).toBeVisible()
  await expect(page.getByText(assessment.summary, { exact: true })).toBeVisible()
}

async function expectAiCommandHighAssessment(page, assessment) {
  await expect(page.getByRole("button", { name: "系统态势" })).toBeVisible()
  await expect(page.getByText("高风险", { exact: true })).toBeVisible()
  await page.getByRole("button", { name: "AI 巡检" }).click()
  await expect(page.getByText(assessment.source, { exact: true })).toBeVisible()
  await expect(page.getByText("高风险", { exact: true })).toBeVisible()
  await expect(page.getByText(assessment.summary, { exact: true })).toBeVisible()
}

async function expectBigscreenEmptyAssessment(page) {
  await expect(page.getByText("AI 综合研判")).toBeVisible()
  await expect(page.getByText("暂无 AI 研判", { exact: true })).toBeVisible()
  await expect(page.getByText("HIGH", { exact: true })).toHaveCount(0)
  await expect(page.getByText("CRITICAL", { exact: true })).toHaveCount(0)
}

async function expectAiCommandEmptyAssessment(page) {
  await expect(page.getByRole("button", { name: "系统态势" })).toBeVisible()
  await expect(page.getByText("暂无 AI 研判", { exact: true })).toBeVisible()
  await expect(page.getByText("高风险", { exact: true })).toHaveCount(0)
  await expect(page.getByText("极高风险", { exact: true })).toHaveCount(0)
  await page.getByRole("button", { name: "AI 巡检" }).click()
  await expect(page.getByText("暂无 AI 研判", { exact: true })).toBeVisible()
}

test.describe("AI assessment consistency coverage", () => {
  test.use({ viewport: VIEWPORT })

  test.beforeEach(async ({ page }) => {
    await primeClientState(page)
  })

  test("shows the same persisted HIGH assessment on bigscreen and AI command", async ({ page }) => {
    const assessment = buildHighAssessment()
    await mockSituationApis(page, [assessment])

    await page.goto("/bigscreen", { waitUntil: "domcontentloaded" })
    await expectBigscreenHighAssessment(page, assessment)

    await page.goto("/ai/command", { waitUntil: "domcontentloaded" })
    await expectAiCommandHighAssessment(page, assessment)
  })

  test("shows no fabricated AI risk when there is no persisted assessment", async ({ page }) => {
    await mockSituationApis(page, [])

    await page.goto("/bigscreen", { waitUntil: "domcontentloaded" })
    await expectBigscreenEmptyAssessment(page)

    await page.goto("/ai/command", { waitUntil: "domcontentloaded" })
    await expectAiCommandEmptyAssessment(page)
  })
})
