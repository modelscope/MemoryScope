import assert from "node:assert/strict";
import fs from "node:fs";
import path from "node:path";
import test from "node:test";
import { fileURLToPath } from "node:url";

const repositoryRoot = path.resolve(path.dirname(fileURLToPath(import.meta.url)), "../..");
const homePage = fs.readFileSync(path.join(repositoryRoot, "docs/.vitepress/theme/HomePage.vue"), "utf8");
const trafficPage = fs.readFileSync(path.join(repositoryRoot, "docs/.vitepress/theme/TrafficPage.vue"), "utf8");

test("home dark-mode selectors keep their component target when scoped styles compile", () => {
  assert.doesNotMatch(homePage, /:global\(\.dark\)\s+/);
  assert.match(homePage, /:global\(html\.dark \.reme-home\)/);
  assert.match(homePage, /:global\(html\.dark \.home-stage::before\)/);
});

test("embedded traffic dashboards follow the selected site theme", () => {
  for (const component of [homePage, trafficPage]) {
    assert.match(component, /theme=\$\{isDark\.value \? "dark" : "light"\}/);
  }
});

test("the home overview action opens the localized project README", () => {
  assert.match(homePage, /localLink\(`\/\$\{lang\}\/overview`\)/);
});
