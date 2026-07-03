import { expect, test } from "@playwright/test";

test.beforeEach(async ({ page }) => {
  await page.goto("/login");
  await page.evaluate(() => window.localStorage.clear());
  await page.reload();
});

test("auth screens validate credentials and reset flows", async ({ page }) => {
  await page.goto("/login");

  await expect(page.getByLabel("Username or email")).toHaveAttribute("required", "");
  await expect(page.getByLabel("Password")).toHaveAttribute("required", "");

  await page.getByLabel("Username or email").fill("nobody");
  await page.getByLabel("Password").fill("wrong");
  await page.getByRole("button", { name: "Login", exact: true }).click();
  await expect(page.getByText("Invalid mock credentials")).toBeVisible();

  await page.getByLabel("Username or email").fill("olivia.frontdesk");
  await page.getByLabel("Password").fill("password");
  await page.getByRole("button", { name: "Login", exact: true }).click();
  await expect(page.getByText("must change password")).toBeVisible();

  await page.getByRole("link", { name: "Forgot password?" }).click();
  await page.getByLabel("Email").fill("person@example.com");
  await page.getByRole("button", { name: "Send reset link" }).click();
  await expect(page.getByText("If this email is registered, a password reset link will be sent.")).toBeVisible();

  await page.goto("/reset-password");
  await page.getByLabel("New password").fill("first-password");
  await page.getByLabel("Confirm password").fill("second-password");
  await page.getByRole("button", { name: "Update password" }).click();
  await expect(page.getByText("Passwords do not match.")).toBeVisible();

  await page.goto("/reset-password?state=expired");
  await expect(page.getByText("This reset link has expired.")).toBeVisible();

  await page.goto("/reset-password?state=used");
  await expect(page.getByText("This reset link has already been used.")).toBeVisible();

  await page.goto("/reset-password");
  await page.getByLabel("New password").fill("same-password");
  await page.getByLabel("Confirm password").fill("same-password");
  await page.getByRole("button", { name: "Update password" }).click();
  await expect(page.getByText("Your password has been updated successfully.")).toBeVisible();
});

test("role-based demo login exposes only the intended navigation", async ({ page }) => {
  await page.goto("/login");
  await page.getByRole("button", { name: "Login as Admin" }).click();
  await expect(page).toHaveURL(/\/admin\/dashboard/);
  await expect(page.getByRole("link", { name: "Roles & Permissions" })).toHaveCount(0);
  await expect(page.getByRole("link", { name: "Users", exact: true }).first()).toBeVisible();
  await page.goto("/admin/roles-permissions");
  await expect(page.getByText("Page not found")).toBeVisible();

  await page.goto("/login");
  await page.getByRole("button", { name: "Login as Staff" }).click();
  await expect(page).toHaveURL(/\/staff\/dashboard/);
  await expect(page.getByRole("link", { name: "Appointments" })).toBeVisible();
  await expect(page.getByRole("link", { name: "Billing" })).toBeVisible();
  await expect(page.getByRole("link", { name: "Users", exact: true })).toHaveCount(0);

  await page.goto("/admin/users");
  await expect(page.getByText("Permission denied")).toBeVisible();

  await page.goto("/missing-page");
  await page.getByRole("button", { name: "Go to dashboard" }).click();
  await expect(page).toHaveURL(/\/staff\/dashboard/);

  await page.goto("/login");
  await page.getByRole("button", { name: "Login as Doctor" }).click();
  await expect(page).toHaveURL(/\/doctor\/dashboard/);
  await expect(page.getByRole("link", { name: "My Appointments" })).toBeVisible();
  await expect(page.getByRole("link", { name: "Billing", exact: true })).toHaveCount(0);
});

test("staff can record a payment and update invoice status", async ({ page }) => {
  await page.goto("/login");
  await page.getByRole("button", { name: "Login as Staff" }).click();
  await page.goto("/staff/billing");

  await page.getByText("INV-2026-003").click();
  await page.getByRole("button", { name: "Process Payment" }).click();
  await page.getByLabel("Amount to pay").fill("750");
  await expect(page.getByLabel("Payment Method")).toHaveValue("Cash");
  await expect(page.getByRole("option", { name: "Card" })).toHaveCount(0);
  await page.getByRole("button", { name: "Confirm Payment" }).click();

  await expect(page.getByText("Payment captured locally and invoice balance updated.")).toBeVisible();
  await expect(page.getByText("Remaining balance").locator("..")).toContainText("$0");
});

test("doctor continues the current active visit and can save notes", async ({ page }) => {
  await page.goto("/login");
  await page.getByRole("button", { name: "Login as Doctor" }).click();
  await page.goto("/doctor/appointments");

  const checkedInAppointment = page.getByRole("button", { name: /Checked-in/ });
  await checkedInAppointment.getByRole("button", { name: "Start Visit", exact: true }).click();
  await expect(page).toHaveURL(/\/doctor\/active-visit/);
  await expect(page.getByRole("heading", { name: "Active Visit" })).toBeVisible();
  await page.getByLabel("Clinical Notes").fill("Updated during e2e visit.");
  await page.getByRole("button", { name: "Save notes" }).click();
  await expect(page.getByText("Notes saved locally and marked pending review.")).toBeVisible();
});

test("login page exposes accessible structure and avoids horizontal overflow", async ({ page }) => {
  await page.goto("/login");
  await expect(page.getByRole("heading", { name: "Welcome back" })).toBeVisible();
  await expect(page.getByLabel("Username or email")).toBeVisible();
  await expect(page.getByLabel("Password")).toBeVisible();
  const hasHorizontalOverflow = await page.evaluate(() => document.documentElement.scrollWidth > document.documentElement.clientWidth);
  expect(hasHorizontalOverflow).toBe(false);
});
