// Takes the README screenshots of the live production site.
// Run it with the docker command in ops/screenshots/README.md.
import { chromium } from "playwright";

const BASE = process.env.BASE_URL ?? "https://cfe-frontend-prod-qf6bvfuxjq-ew.a.run.app";
const OUT = process.env.OUT_DIR ?? "/out";

const shots = [
  { file: "ledger-light.png", path: "/", theme: "light", width: 1280, height: 800 },
  { file: "ledger-dark.png", path: "/", theme: "dark", width: 1280, height: 800 },
  { file: "finding-light.png", path: "/findings/finance-bill-2024", theme: "light", width: 1280, height: 1400 },
  { file: "finding-phone-dark.png", path: "/findings/finance-bill-2024", theme: "dark", width: 390, height: 844 },
];

const browser = await chromium.launch();
for (const s of shots) {
  const context = await browser.newContext({
    viewport: { width: s.width, height: s.height },
    deviceScaleFactor: 1,
  });
  await context.addInitScript((theme) => localStorage.setItem("cfe-theme", theme), s.theme);
  const page = await context.newPage();
  await page.goto(BASE + s.path, { waitUntil: "networkidle" });
  await page.evaluate(() => document.fonts.ready);
  await page.screenshot({ path: `${OUT}/${s.file}`, type: "png" });
  await context.close();
  console.log("saved", s.file);
}
await browser.close();
