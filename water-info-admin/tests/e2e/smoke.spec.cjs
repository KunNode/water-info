const { expect, test } = require("@playwright/test")

test("admin app serves login and bigscreen routes", async ({ request }) => {
  const login = await request.get("/login")
  expect(login.status()).toBe(200)
  expect(await login.text()).toContain('<div id="app">')

  const bigscreen = await request.get("/bigscreen")
  expect(bigscreen.status()).toBe(200)
  expect(await bigscreen.text()).toContain('<div id="app">')
})
