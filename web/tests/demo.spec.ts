import { test, expect } from "@playwright/test";
import fs from "node:fs";
import path from "node:path";
const shots = path.resolve("../demo/screenshots");
const pause = async (page: any) => {
  if (process.env.RECORD) await page.waitForTimeout(2600);
};
test("standalone journey: overview, peers and both assortment demos", async ({
  page,
}) => {
  fs.mkdirSync(shots, { recursive: true });
  const errors: string[] = [];
  page.on("pageerror", (e) => errors.push(e.message));
  await page.goto("/");
  await expect(page.getByRole("heading", { name: /Know what to/ })).toBeVisible();
  await expect(page.locator(".phone")).toHaveCount(0);
  await page.screenshot({
    path: path.join(shots, "landing.png"),
    fullPage: true,
  });
  await pause(page);
  await page
    .getByRole("link", { name: "Enter demo", exact: false })
    .last()
    .click();
  await expect(
    page.getByRole("heading", { name: "A clearer view of your shop." }),
  ).toBeVisible();
  await expect(page.locator(".metric").first()).toContainText("₹22,888");
  await page.screenshot({
    path: path.join(shots, "hypermarket-overview.png"),
    fullPage: true,
  });
  await pause(page);
  const weekly = page.waitForResponse((r) =>
    r.url().includes("/v2/dashboard/hypermarket?period=week"),
  );
  await page.getByRole("button", { name: "Week", exact: true }).click();
  await weekly;
  await expect(page.locator(".window-label")).toContainText("2026-09-26");
  const monthly = page.waitForResponse((r) =>
    r.url().includes("/v2/dashboard/hypermarket?period=month"),
  );
  await page.getByRole("button", { name: "Month", exact: true }).click();
  await monthly;
  await pause(page);
  await page
    .locator(".insight-tile")
    .first()
    .getByRole("button", { name: "Evidence", exact: true })
    .click();
  await expect(page.getByRole("dialog")).toContainText("Calculation receipt");
  await expect(page.getByRole("dialog")).toContainText("most units sold");
  await pause(page);
  await page.getByRole("button", { name: "Close calculation" }).click();
  await page.getByRole("button", { name: "Inventory", exact: true }).click();
  await expect(page.getByRole("table")).toContainText(
    "Digestive biscuits 200 g",
  );
  await page
    .getByRole("button", { name: "Review sample supplier bill" })
    .click();
  await expect(
    page.getByRole("heading", { name: "Review supplier invoice" }),
  ).toBeVisible();
  await page.getByLabel("Invoice reference").fill("E2E-HYPER-FIXED-001");
  await page.getByLabel("Invoice product").selectOption("hypermarket-01");
  await page.getByLabel("Invoice quantity").fill("40");
  await page.getByLabel("Invoice unit cost").fill("430");
  await page
    .getByRole("button", { name: "Confirm quantities & import" })
    .click();
  await expect(
    page.getByRole("button", { name: "Imported into simulated inventory" }),
  ).toBeVisible();
  await pause(page);
  await page.getByRole("button", { name: "Close invoice" }).click();
  await page
    .getByRole("row")
    .filter({ hasText: "Digestive biscuits 200 g" })
    .getByRole("button", { name: "Try replacement" })
    .click();
  await expect(page.getByLabel("Remove product")).toHaveValue("hypermarket-09");
  await page.getByRole("button", { name: "Run on digital twin" }).click();
  await expect(page.locator(".trial-result")).toContainText(
    "Millet cookies 150 g",
    { timeout: 30000 },
  );
  await expect(page.locator(".result-stats")).toContainText(
    "Modeled incremental revenue",
  );
  await page.locator(".trial-result").scrollIntoViewIfNeeded();
  await page.screenshot({
    path: path.join(shots, "hypermarket-twin.png"),
    fullPage: true,
  });
  await pause(page);
  await page
    .getByRole("heading", { name: "Substitution, made explicit" })
    .scrollIntoViewIfNeeded();
  await pause(page);
  await page
    .getByRole("button", { name: "Show the math", exact: true })
    .click();
  await expect(page.getByRole("dialog")).toContainText("paired draws");
  await expect(page.getByRole("dialog")).toContainText("outside");
  await pause(page);
  await page.getByRole("button", { name: "Close calculation" }).click();
  await page.getByRole("button", { name: "Inspect lookalikes" }).click();
  await expect(page.locator(".peer-metrics").first()).toContainText("30", {
    timeout: 30000,
  });
  await expect(
    page.getByRole("heading", {
      name: "Same product ≠ same family ≠ an interchangeable substitute.",
    }),
  ).toBeVisible();
  await pause(page);
  await page.getByLabel("Choose merchant").selectOption("restaurant");
  await expect(page.locator(".chat-context")).toContainText(
    "Annapurna Kitchen",
  );
  await page.getByRole("button", { name: "Overview", exact: true }).click();
  const day = page.waitForResponse((r) =>
    r.url().includes("/v2/dashboard/restaurant?period=day"),
  );
  await page.getByRole("button", { name: "Day", exact: true }).click();
  await day;
  await expect(page.locator(".metric").first()).toContainText("₹21,530");
  await page.screenshot({
    path: path.join(shots, "restaurant-overview.png"),
    fullPage: true,
  });
  await pause(page);
  await page
    .getByRole("button", { name: /What should replace my dead stock/ })
    .click();
  await expect(page.locator(".ranking-row")).toHaveCount(2, { timeout: 30000 });
  await expect(page.locator(".trial-result")).toContainText("Cream pasta");
  await expect(page.getByLabel("Remove product")).toHaveValue("restaurant-09");
  await expect(page.getByLabel("Replacement product")).toHaveValue(
    "restaurant-11",
  );
  await expect(page.locator(".quote")).toContainText("₹5,500");
  await expect(
    page.getByRole("heading", {
      name: "Recipe constraints are part of the restaurant twin.",
    }),
  ).toBeVisible();
  await page.locator(".trial-result").scrollIntoViewIfNeeded();
  await page.screenshot({
    path: path.join(shots, "restaurant-twin.png"),
    fullPage: true,
  });
  await pause(page);
  await page
    .getByRole("heading", {
      name: "Recipe constraints are part of the restaurant twin.",
    })
    .scrollIntoViewIfNeeded();
  await pause(page);
  await page.getByRole("button", { name: "Overview", exact: true }).click();
  await page
    .getByLabel("Ask Pi")
    .fill("Which products sold most this week and what customers bought them?");
  await page.getByRole("button", { name: "Send question" }).click();
  await expect(page.locator(".message.assistant").last()).toContainText(
    "recorded revenue",
    { timeout: 30000 },
  );
  await expect(page.locator(".message.assistant").last()).toContainText(
    "not demographics",
  );
  await pause(page);
  await page.getByRole("button", { name: "Start voice recording" }).click();
  await expect(page.getByRole("status")).toContainText("server-side key");
  await page
    .getByRole("button", { name: "Data & integrations", exact: true })
    .click();
  await expect(
    page.getByRole("heading", { name: "Integration status" }),
  ).toBeVisible();
  await pause(page);
  expect(errors).toEqual([]);
});
test("regulars, tool-backed insights and the inventory filter", async ({ page }) => {
  await page.goto("/demo");
  await expect(page.locator(".metric").nth(2)).toContainText("Regular customers");
  await expect(page.getByText("Average bill")).toHaveCount(0);
  await expect(page.getByText("Returning bills")).toHaveCount(0);
  await expect(page.locator(".rhythm-row").first()).toContainText("Milk 1 L");
  await expect(page.locator(".rhythm-row").first()).toContainText("Every day");
  await expect(page.locator(".insight-tile")).toHaveCount(6);
  await expect(page.locator(".tool-chip").first()).toContainText("insight.most_sold");
  const refreshed = page.waitForResponse((r) => r.url().includes("/refresh") && r.ok());
  await page.getByRole("button", { name: "Refresh", exact: true }).click();
  await refreshed;
  await expect(page.locator(".ai-overview-head")).toContainText("manual refresh");
  // the same tool answers in chat
  await page
    .locator(".insight-tile")
    .filter({ hasText: "REPLENISH SOON" })
    .getByRole("button", { name: "Ask Pi" })
    .click();
  await expect(page.locator(".message.assistant").last()).toContainText("more to reach 14 days", {
    timeout: 30000,
  });
  await page.getByRole("button", { name: "Inventory", exact: true }).click();
  await page.getByRole("button", { name: /Replenish soon/ }).click();
  await expect(page.locator("tbody tr")).toHaveCount(2);
  await expect(page.locator("tbody")).toContainText("Potato chips 50 g");
  await expect(page.locator("tbody")).toContainText("Oats 1 kg");
  await page.getByRole("button", { name: /^No recorded sales/ }).click();
  await expect(page.locator("tbody tr")).toHaveCount(1);
  await expect(page.locator("tbody")).toContainText("Digestive biscuits 200 g");
});
test("decision lab shows a limited payments-only view and a fuller item-level one", async ({
  page,
}) => {
  await page.goto("/demo");
  await page.getByRole("button", { name: "Decision lab", exact: true }).click();
  await expect(page.getByText("Limited view · payments only")).toBeVisible();
  await expect(page.locator(".capability.locked")).toHaveCount(5);
  await expect(page.locator(".main-content")).toContainText("Takings, last 7 days");
  await expect(page.locator(".main-content")).not.toContainText("Digestive biscuits");
  await page.getByRole("button", { name: /Item-level bills/ }).first().click();
  await expect(page.getByRole("heading", { name: "Decisions waiting for you" })).toBeVisible();
  await expect(page.locator(".decision-row").first()).toContainText("Replenish soon");
  await page.getByRole("button", { name: "Open replenish list" }).click();
  await expect(page.locator("tbody tr")).toHaveCount(2);
});
test("small-screen standalone dashboard and apparel switch", async ({
  page,
}) => {
  await page.setViewportSize({ width: 390, height: 844 });
  await page.goto("/");
  await page
    .getByRole("link", { name: "Enter demo", exact: false })
    .last()
    .click();
  await expect(page.locator(".metrics")).toBeVisible();
  await page.getByLabel("Choose merchant").selectOption("apparel");
  await expect(page.locator(".chat-context")).toContainText("Thread & Co.");
  await expect(page.locator(".metric").first()).toContainText("₹37,043");
  expect(
    await page.evaluate(
      () => document.documentElement.scrollWidth > window.innerWidth + 1,
    ),
  ).toBe(false);
  await page.screenshot({
    path: path.join(shots, "apparel-mobile.png"),
    fullPage: true,
  });
});

test("configured speech UI uses mocked STT and explicit TTS without auto-send", async ({
  page,
}) => {
  await page.addInitScript(() => {
    class MockRecorder {
      static isTypeSupported() {
        return true;
      }
      state = "inactive";
      ondataavailable: ((event: { data: Blob }) => void) | null = null;
      onstop: (() => void) | null = null;
      start() {
        this.state = "recording";
      }
      stop() {
        this.state = "inactive";
        this.ondataavailable?.({
          data: new Blob(["offline microphone fixture"], {
            type: "audio/webm",
          }),
        });
        this.onstop?.();
      }
    }
    Object.defineProperty(window, "MediaRecorder", { value: MockRecorder });
    Object.defineProperty(navigator, "mediaDevices", {
      value: {
        getUserMedia: async () => ({ getTracks: () => [{ stop: () => {} }] }),
      },
    });
    HTMLMediaElement.prototype.play = async () => {};
  });
  await page.route("**/api/v2/merchants", async (route) => {
    const response = await route.fetch();
    const body = await response.json();
    body.voice.enabled = true;
    await route.fulfill({ json: body });
  });
  let sttCalls = 0,
    ttsCalls = 0;
  await page.route("**/api/v2/voice/stt", async (route) => {
    sttCalls++;
    expect(route.request().method()).toBe("POST");
    expect(route.request().postData()).toContain("unknown");
    await route.fulfill({
      json: {
        transcript: "Give me today sales overview",
        language_code: "en-IN",
        request_id: "offline-stt",
      },
    });
  });
  await page.route("**/api/v2/voice/tts", async (route) => {
    ttsCalls++;
    expect(route.request().postDataJSON().text).toContain("recorded revenue");
    expect(route.request().postDataJSON().language).toBe("en-IN");
    await route.fulfill({
      contentType: "audio/wav",
      body: Buffer.from("RIFF0000WAVEoffline"),
    });
  });
  await page.goto("/demo");
  await expect(page.locator(".metrics")).toBeVisible();
  await page.getByRole("button", { name: "Start voice recording" }).click();
  await expect(page.getByRole("status")).toContainText("Listening");
  await page.getByRole("button", { name: "Stop voice recording" }).click();
  await expect(page.getByLabel("Ask Pi")).toHaveValue(
    "Give me today sales overview",
  );
  await expect(page.locator(".message.user")).toHaveCount(0);
  expect(ttsCalls).toBe(0);
  await page.getByRole("button", { name: "Send question" }).click();
  await expect(page.locator(".message.assistant").last()).toContainText(
    "recorded revenue",
  );
  // TTS follows the answer language even if the next-question selection changes.
  await page.getByLabel("Voice language").selectOption("hi-IN");
  await page.getByRole("button", { name: "Read answer aloud" }).click();
  await expect(page.getByRole("status")).toContainText("Sarvam audio playing");
  expect(sttCalls).toBe(1);
  expect(ttsCalls).toBe(1);
});

test("repricing: exact break-even, withheld forecast on one-price history, supported forecast on the pilot", async ({ page }) => {
  await page.goto("/demo");
  await page.getByRole("button", { name: "Inventory", exact: true }).click();
  await page.getByRole("row").filter({ hasText: "Rice 5 kg" }).getByRole("button", { name: "Change price" }).click();
  await expect(page.getByRole("heading", { name: "Change a price" })).toBeVisible();
  await expect(page.locator(".fact-row")).toContainText("Insufficient evidence");
  await page.getByLabel("Proposed price").fill("500");
  await page.getByRole("button", { name: "Check this price" }).click();
  await expect(page.locator(".price-headline")).toContainText("you need at least 146 sales");
  await expect(page.locator(".price-headline")).toContainText("cannot yet estimate");
  await expect(page.locator(".forecast-grid")).toHaveCount(0);
  await expect(page.locator(".withheld")).toContainText("Demand forecast withheld");
  // merchant-supplied volume: 130 x 90 / 70 = 167.1, so 168 sales
  await page.getByText("Stock, costs and your own numbers").click();
  await page.getByLabel("Expected units").fill("130");
  await page.getByRole("button", { name: "Check this price" }).click();
  await expect(page.locator(".price-headline")).toContainText("at least 168 sales");
  await page.getByRole("button", { name: "Show calculation" }).first().click();
  await expect(page.getByRole("dialog")).toContainText("Gross contribution");
  await page.getByRole("button", { name: "Close calculation" }).click();
  // an assumption is labelled as one
  await page.getByLabel("What if customers react this strongly?").check().catch(async () => {
    await page.getByText("What if customers react this strongly?").click();
  });
  await page.getByLabel("Expected units").fill("");
  await page.getByRole("button", { name: "Check this price" }).click();
  await expect(page.locator(".assumption-tag")).toContainText("assumption-based scenario");
  await expect(page.locator(".price-result")).toContainText("Insufficient evidence");
  // pilot: randomized price test supports a forecast
  await page.getByRole("button", { name: "Price-test pilot" }).click();
  await page.getByLabel("Product to reprice").selectOption("pilot-02");
  await page.getByLabel("Proposed price").fill("140");
  await page.getByRole("button", { name: "Check this price" }).click();
  await expect(page.locator(".forecast-grid")).toBeVisible();
  await expect(page.locator(".price-headline")).toContainText("Our estimate");
  await expect(page.locator(".evidence-card")).toContainText("Randomized price test (synthetic data)");
  await page.getByRole("button", { name: "Compare prices" }).click();
  await expect(page.locator(".price-table tbody tr").first()).toBeVisible();
  expect(await page.locator(".price-table tbody tr").count()).toBeGreaterThan(5);
  await expect(page.locator(".price-table tr.current")).toHaveCount(1);
  await expect(page.locator(".price-chart")).toBeVisible();
  // an item whose history was not randomized is only ever a scenario
  await page.getByLabel("Product to reprice").selectOption("pilot-04");
  await page.getByLabel("Proposed price").fill("240");
  await page.getByRole("button", { name: "Check this price" }).click();
  await expect(page.locator(".price-headline")).toContainText("treat this as a scenario");
  await expect(page.locator(".price-result")).not.toContainText("Likely improves");
  // and one with a single short price change gets no forecast
  await page.getByLabel("Product to reprice").selectOption("pilot-05");
  await page.getByLabel("Proposed price").fill("42");
  await page.getByRole("button", { name: "Check this price" }).click();
  await expect(page.locator(".withheld")).toBeVisible();
  await expect(page.locator(".plan-card")).toContainText("A small price trial would settle this");
});

test("repricing through chat opens the same evidence-backed result", async ({ page }) => {
  await page.goto("/demo");
  await page.getByLabel("Ask Pi").fill("If I reduce Rice 5 kg from ₹520 to ₹500, will I make more profit?");
  await page.getByRole("button", { name: "Send question" }).click();
  await expect(page.locator(".message.assistant").last()).toContainText("at least 146 sales", { timeout: 30000 });
  await expect(page.locator(".message.assistant").last()).toContainText("Evidence: Insufficient evidence");
  await expect(page.locator(".price-headline")).toContainText("146 sales");
  await page.getByLabel("Ask Pi").fill("Compare ₹480, ₹500, ₹520 and ₹540 for Rice 5 kg for the next seven days");
  await page.getByRole("button", { name: "Send question" }).click();
  await expect(page.locator(".price-table tbody tr")).toHaveCount(4, { timeout: 30000 });
  await expect(page.locator(".price-table")).toContainText("withheld");
});

test("price panel fits a phone screen", async ({ page }) => {
  await page.setViewportSize({ width: 390, height: 844 });
  await page.goto("/demo");
  await page.getByRole("button", { name: "Digital twin", exact: true }).click();
  await page.getByRole("button", { name: "Change a price" }).click();
  await page.getByRole("button", { name: "Price-test pilot" }).click();
  await page.getByRole("button", { name: "Compare prices" }).click();
  await expect(page.locator(".price-table")).toBeVisible();
  expect(await page.evaluate(() => document.documentElement.scrollWidth > window.innerWidth + 1)).toBe(false);
});