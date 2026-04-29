const e2ePort = process.env.PLAYWRIGHT_PORT || "5174"
const baseURL = process.env.PLAYWRIGHT_BASE_URL || `http://localhost:${e2ePort}`

module.exports = {
  testDir: "./tests/e2e",
  timeout: 30_000,
  use: {
    baseURL,
  },
  webServer: process.env.PLAYWRIGHT_BASE_URL
    ? undefined
    : {
        command: `npm run dev -- --host 127.0.0.1 --port ${e2ePort} --strictPort`,
        url: baseURL,
        reuseExistingServer: false,
        timeout: 120_000,
      },
  projects: [
    {
      name: "smoke",
      testMatch: /smoke\.spec\.cjs$/,
    },
    {
      name: "situation",
      testMatch: /ai-assessment-situation\.spec\.cjs$/,
    },
  ],
}
