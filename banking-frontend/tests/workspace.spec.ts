import { test, expect } from "@playwright/test";

test("customer submits identity files as multipart uploads", async ({
  page,
}) => {
  const uploads: string[] = [];
  let submitted: Record<string, unknown> | undefined;
  await page.route("**/api/**", async (route) => {
    const path = new URL(route.request().url()).pathname;
    let data: unknown = [];
    if (path.endsWith("/auth/login"))
      data = { access_token: "customer", refresh_token: "customer" };
    else if (path.endsWith("/customers/me"))
      data = {
        id: "customer",
        first_name: "Alex",
        last_name: "Morgan",
        email: "alex@example.com",
        kyc_status: "pending",
      };
    else if (path.endsWith("/kyc/attachments")) {
      expect(route.request().headers()["content-type"]).toContain(
        "multipart/form-data; boundary=",
      );
      const body = route.request().postData() || "";
      const role = body.includes("\r\nselfie\r\n") ? "selfie" : "front";
      uploads.push(role);
      data = { reference: `attachment:${role}` };
    } else if (path.endsWith("/kyc/documents")) {
      submitted = route.request().postDataJSON();
      data = { id: "document", verification_status: "pending" };
    }
    await route.fulfill({ json: data });
  });
  await page.goto("/");
  await page.getByLabel("Email address").fill("alex@example.com");
  await page
    .getByLabel("Password", { exact: true })
    .fill("TestingPassword123!");
  await page.getByRole("button", { name: "Sign in", exact: true }).click();
  await page.getByRole("button", { name: "Identity", exact: true }).click();
  await page.getByRole("button", { name: "Submit identity details" }).click();
  await page.getByLabel("Document number").fill("TEST-123");
  const file = {
    name: "test.png",
    mimeType: "image/png",
    buffer: Buffer.from("test fixture"),
  };
  await page.getByLabel("Document front", { exact: false }).setInputFiles(file);
  await page.getByLabel("Selfie (PNG or JPEG, up to 5 MB)").setInputFiles(file);
  await page
    .getByRole("button", { name: "Submit for review", exact: true })
    .click();
  await expect(page.getByRole("dialog")).not.toBeVisible();
  expect(uploads).toEqual(["front", "selfie"]);
  expect(submitted).toMatchObject({
    document_number: "TEST-123",
    document_front_url: "attachment:front",
    selfie_url: "attachment:selfie",
  });
});

test("staff can page through customers, assess risk and review AML transfers", async ({
  page,
}) => {
  let assessed: unknown;
  let decision: unknown;
  let searched = false;
  await page.route("**/api/**", async (route) => {
    const url = new URL(route.request().url());
    const path = url.pathname;
    let data: unknown = [];
    if (path.endsWith("/auth/admin/login"))
      data = { access_token: "staff", refresh_token: "staff" };
    else if (path.endsWith("/admin/me"))
      data = {
        id: "staff",
        first_name: "Sam",
        last_name: "Staff",
        role: "compliance",
        email: "staff@example.com",
      };
    else if (path.endsWith("/summary"))
      data = {
        customers: 26,
        accounts: 26,
        pending_transfers: 1,
        pending_kyc: 0,
      };
    else if (path.endsWith("/admin/customers")) {
      searched = url.searchParams.get("q") === "next@example.com";
      data =
        url.searchParams.get("offset") === "25" || searched
          ? [
              {
                id: "customer-25",
                email: "next@example.com",
                customer_status: "active",
                risk_score: 0,
                risk_level: "low",
                kyc_status: "verified",
              },
            ]
          : Array.from({ length: 25 }, (_, i) => ({
              id: `customer-${i}`,
              email: `person${i}@example.com`,
              customer_status: "active",
              risk_score: 0,
              risk_level: "low",
              kyc_status: "verified",
            }));
    } else if (path.endsWith("/risk")) {
      assessed = route.request().postDataJSON();
      data = { risk_score: 65, risk_level: "medium" };
    } else if (path.endsWith("/admin/aml"))
      data = [
        {
          id: "check-1",
          customer_id: "customer-25",
          transaction_id: "transaction-1",
          risk_level: "medium",
          risk_score: 65,
          resolution: "review",
          flags_triggered: ["high_amount"],
        },
      ];
    else if (path.endsWith("/review/approve")) {
      decision = route.request().postDataJSON();
      data = { status: "completed" };
    }
    await route.fulfill({ json: data });
  });
  await page.goto("/");
  await page.getByRole("button", { name: "Staff sign in" }).click();
  await page.getByLabel("Email address").fill("staff@example.com");
  await page
    .getByLabel("Password", { exact: true })
    .fill("TestingPassword123!");
  await page.getByRole("button", { name: "Sign in", exact: true }).click();
  await page.getByRole("button", { name: "Customers", exact: true }).click();
  await page.getByRole("button", { name: "Next", exact: true }).click();
  await expect(
    page.getByText("next@example.com", { exact: true }),
  ).toBeVisible();
  await page.getByLabel("Search customers").fill("next@example.com");
  await page.getByRole("button", { name: "Search", exact: true }).click();
  await expect(page.getByText("Page 1", { exact: true })).toBeVisible();
  await page.getByLabel("Decision reason").fill("Updated screening assessment");
  await page.getByRole("button", { name: "Assess risk", exact: true }).click();
  await page.getByLabel("Risk score (0–100)").fill("65");
  await page.getByRole("button", { name: "Save changes", exact: true }).click();
  await expect(
    page.getByRole("status").filter({ hasText: "Change saved" }),
  ).toBeVisible();
  expect(assessed).toEqual({
    score: 65,
    reason: "Updated screening assessment",
  });
  expect(searched).toBe(true);
  await page.getByRole("button", { name: "AML checks", exact: true }).click();
  await page.getByLabel("Decision reason").fill("Source of funds reviewed");
  await page
    .getByRole("button", { name: "Approve transfer", exact: true })
    .click();
  await expect(
    page.getByRole("status").filter({ hasText: "Change saved" }),
  ).toBeVisible();
  expect(decision).toEqual({ notes: "Source of funds reviewed" });
  await page.screenshot({ path: "test-results/staff-aml.png", fullPage: true });
});
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
  await page.screenshot({ path: "test-results/dashboard.png", fullPage: true });
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
  await expect(
    page.getByRole("alert").filter({ hasText: "The banking service" }),
  ).toContainText("unavailable");
  await page.screenshot({
    path: "test-results/mobile-login.png",
    fullPage: true,
  });
  expect(
    await page.evaluate(
      () => document.documentElement.scrollWidth <= window.innerWidth,
    ),
  ).toBe(true);
});
