import { test, expect } from "@playwright/test";

// #464: seed scenarios — three smoke checks that prove the harness
// works against a built sessionwiki demo site. Real generated specs land
// via #466's Generator pass once this bootstrap is on master.

test.describe("seed — site reachability", () => {
  test("home renders the sessionwiki hero", async ({ page }) => {
    await page.goto("/");
    await expect(page).toHaveTitle(/sessionwiki/);
    await expect(page.locator("h1").first()).toContainText("sessionwiki");
  });

  test("nav has the canonical links", async ({ page }) => {
    await page.goto("/");
    for (const label of ["Home", "Projects", "Sessions", "Graph", "Docs", "Changelog"]) {
      await expect(
        page.getByRole("link", { name: label }).first(),
      ).toBeVisible();
    }
  });

  test("graph page carries the site nav (regression for #456)", async ({
    page,
  }) => {
    await page.goto("/graph.html");
    await expect(page.getByRole("link", { name: "Home" }).first()).toBeVisible();
    await expect(page.getByRole("link", { name: "Graph" }).first()).toBeVisible();
  });
});
