import { test, expect } from "@playwright/test";
test("sign in, inspect real-shaped API data, and submit an idempotent transfer", async ({
  page,
}) => {
  const source = "11111111-1111-4111-8111-111111111111",
    destination = "22222222-2222-4222-8222-222222222222";
  let sent: Record<string, unknown> | null = null;
  await page.route("**/api/**", async (route) => {
    const url = new URL(route.request().url());
    const path = url.pathname;
    let data: unknown = {};
    if (path.endsWith("/auth/login"))
      data = { access_token: "test", refresh_token: "test" };
    else if (path.endsWith("/customers/me"))
      data = {
        id: "c1",
        first_name: "Alex",
        last_name: "Morgan",
        email: "alex@example.com",
        kyc_status: "verified",
      };
    else if (path.endsWith("/accounts/me"))
      data = [
        {
          id: source,
          account_name: "Everyday spending",
          account_number: "CHK-1234567890",
          account_type: "checking",
          account_status: "active",
          currency_code: "CAD",
        },
      ];
    else if (path.endsWith("/balance")) data = { balance: "12500.00" };
    else if (path.endsWith("/transactions/transfer")) {
      sent = route.request().postDataJSON();
      data = { id: "tx1", status: "completed" };
    } else if (path.endsWith("/transactions") || path.endsWith("/cards"))
      data = [];
    await route.fulfill({ json: data });
  });
  await page.goto("/");
  await page.getByLabel("Email address").fill("alex@example.com");
  await page
    .getByLabel("Password", { exact: true })
    .fill("TestingPassword123!");
  await page.getByRole("button", { name: "Sign in", exact: true }).click();
  await expect(
    page.getByRole("heading", { name: "Welcome back, Alex." }),
  ).toBeVisible();
  await expect(page.getByText("$12,500.00").first()).toBeVisible();
  await page.screenshot({path:'test-results/dashboard.png',fullPage:true});
  await page.getByRole("button", { name: "Move money", exact: true }).click();
  await page.getByLabel("Recipient account ID").fill(destination);
  await page.getByLabel("Amount", { exact: true }).fill("100.00");
  await page.getByRole("button", { name: "Confirm transfer" }).click();
  await expect(page.getByRole("dialog")).not.toBeVisible();
  expect(sent).toMatchObject({
    amount: "100.00",
    from_account_id: source,
    to_account_id: destination,
  });
  expect(sent!["idempotency_key"]).toBeTruthy();
});

test("mobile sign-in is usable and service errors are visible", async ({
  page,
}) => {
  await page.setViewportSize({ width: 390, height: 844 });
  await page.route("**/api/auth/login", (route) =>
    route.fulfill({
      status: 503,
      json: { detail: "The banking service is unavailable." },
    }),
  );
  await page.goto("/");
  await page.getByLabel("Email address").fill("alex@example.com");
  await page
    .getByLabel("Password", { exact: true })
    .fill("TestingPassword123!");
  await page.getByRole("button", { name: "Sign in", exact: true }).click();
  await expect(page.getByRole("alert").filter({hasText:"The banking service"})).toContainText("unavailable");
  await page.screenshot({path:'test-results/mobile-login.png',fullPage:true});
  expect(
    await page.evaluate(
      () => document.documentElement.scrollWidth <= window.innerWidth,
    ),
  ).toBe(true);
});
