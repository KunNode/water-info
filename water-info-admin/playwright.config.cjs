module.exports = {
  testDir: "./tests/e2e",
  timeout: 30_000,
  use: {
    baseURL: process.env.PLAYWRIGHT_BASE_URL || "http://localhost:5173",
  },
  projects: [
    {
      name: "smoke",
      testMatch: /smoke\.spec\.cjs$/,
    },
  ],
}
