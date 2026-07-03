import { expect, type Page, test } from "@playwright/test";

const responsiveViewports = [
  { width: 1366, height: 768 },
  { width: 1280, height: 720 },
  { width: 1024, height: 768 },
  { width: 768, height: 1024 },
];

const staffRoutes = [
  "/staff/profile",
  "/staff/doctors-staff",
  "/staff/patients",
  "/staff/billing",
  "/staff/appointments",
];

const doctorRoutes = [
  "/doctor/dashboard",
  "/doctor/active-visit",
];

async function loginAs(page: Page, role: "Staff" | "Doctor") {
  await page.goto("/login");
  await page.evaluate(() => window.localStorage.clear());
  await page.reload();
  await page.getByRole("button", { name: `Login as ${role}` }).click();
}

async function expectNoPageHorizontalOverflow(page: Page) {
  await expect.poll(async () => page.evaluate(() =>
    document.documentElement.scrollWidth <= document.documentElement.clientWidth + 1,
  )).toBe(true);
}

async function expectCollapsedSidebarUsable(page: Page) {
  const sidebar = page.locator(".sidebar");
  const logout = page.locator(".sidebar-logout");

  await expect(sidebar).toBeVisible();
  await expect(logout).toBeVisible();
  await expect(logout).toBeEnabled();

  const iconsFit = await page.evaluate(() => {
    const sidebarRect = document.querySelector(".sidebar")?.getBoundingClientRect();
    if (!sidebarRect) return false;
    return Array.from(document.querySelectorAll(".sidebar-link svg, .sidebar-logout svg")).every((icon) => {
      const rect = icon.getBoundingClientRect();
      return rect.left >= sidebarRect.left - 1 && rect.right <= sidebarRect.right + 1 && rect.width <= 24 && rect.height <= 24;
    });
  });
  expect(iconsFit).toBe(true);
}

test("staff and doctor routes avoid page-level horizontal overflow at tablet/laptop widths", async ({ page }) => {
  test.setTimeout(60_000);

  for (const viewport of responsiveViewports) {
    await page.setViewportSize(viewport);
    await loginAs(page, "Staff");

    for (const route of staffRoutes) {
      await page.goto(route);
      await expectNoPageHorizontalOverflow(page);
      if (viewport.width <= 1100) {
        await expectCollapsedSidebarUsable(page);
      }
    }

    await loginAs(page, "Doctor");
    for (const route of doctorRoutes) {
      await page.goto(route);
      await expectNoPageHorizontalOverflow(page);
      if (viewport.width <= 1100) {
        await expectCollapsedSidebarUsable(page);
      }
    }
  }
});

test("staff profile keeps schedule and leave content contained", async ({ page }) => {
  for (const viewport of responsiveViewports) {
    await page.setViewportSize(viewport);
    await loginAs(page, "Staff");
    await page.goto("/staff/profile");

    await expect(page.locator(".profile-page-grid")).toBeVisible();
    await expect(page.locator(".working-hours-card")).toBeVisible();
    await expect(page.locator(".leave-exceptions-card")).toBeVisible();

    await expect(page.getByRole("columnheader", { name: "Mon" })).toBeVisible();
    await expect(page.getByRole("columnheader", { name: "Tue" })).toBeVisible();
    await expect(page.getByRole("columnheader", { name: "Wed" })).toBeVisible();
    await expect(page.getByRole("columnheader", { name: "Thu" })).toBeVisible();
    await expect(page.getByRole("columnheader", { name: "Fri" })).toBeVisible();
    await expect(page.getByRole("columnheader", { name: "Sat" })).toBeVisible();
    await expect(page.getByRole("columnheader", { name: "Sun" })).toBeVisible();

    const layoutOk = await page.evaluate(() => {
      const schedule = document.querySelector(".working-hours-card")?.getBoundingClientRect();
      const leave = document.querySelector(".leave-exceptions-card")?.getBoundingClientRect();
      const scheduleTable = document.querySelector(".working-hours-card .schedule-matrix-wrap") as HTMLElement | null;
      const cards = Array.from(document.querySelectorAll(".profile-info-card, .working-hours-card, .leave-exceptions-card")) as HTMLElement[];
      if (!schedule || !leave || !scheduleTable) return false;
      return leave.top > schedule.top &&
        Math.abs(leave.width - schedule.width) <= 2 &&
        scheduleTable.scrollWidth <= scheduleTable.clientWidth + 1 &&
        cards.every((card) => card.scrollWidth <= card.clientWidth + 1);
    });
    expect(layoutOk).toBe(true);
    await expectNoPageHorizontalOverflow(page);
  }
});

test("patient and doctor/staff detail drawers fit without cramped tab overflow", async ({ page }) => {
  await page.setViewportSize({ width: 1366, height: 768 });
  await loginAs(page, "Staff");

  await page.goto("/staff/patients");
  await page.locator("tbody tr[role='button']").first().click();
  await expect(page.getByRole("dialog", { name: "Patient Details" })).toBeVisible();
  const patientDrawerFits = await page.evaluate(() => {
    const drawer = document.querySelector(".drawer-modal")?.getBoundingClientRect();
    if (!drawer) return false;
    return drawer.left >= 0 && drawer.right <= window.innerWidth && drawer.top >= 0 && drawer.bottom <= window.innerHeight;
  });
  expect(patientDrawerFits).toBe(true);
  await page.getByRole("button", { name: "Close drawer" }).click();

  await page.goto("/staff/doctors-staff");
  await page.locator(".staff-card").first().click();
  await expect(page.getByRole("dialog", { name: "Doctor/Staff Profile" })).toBeVisible();
  const tabsFitOneRow = await page.evaluate(() => {
    const tabs = Array.from(document.querySelectorAll(".drawer-modal .tab-button")).map((tab) => tab.getBoundingClientRect());
    if (tabs.length === 0) return false;
    const firstTop = Math.round(tabs[0].top);
    const tabList = document.querySelector(".drawer-modal .tab-list")?.getBoundingClientRect();
    return Boolean(tabList) &&
      tabs.every((rect) => Math.abs(Math.round(rect.top) - firstTop) <= 1) &&
      tabs.every((rect) => rect.left >= tabList!.left - 1 && rect.right <= tabList!.right + 1);
  });
  expect(tabsFitOneRow).toBe(true);
  await expectNoPageHorizontalOverflow(page);
});
