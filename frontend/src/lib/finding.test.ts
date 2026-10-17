import { describe, expect, it } from "vitest";
import {
  bandCode,
  confidenceText,
  contextRange,
  groupCitations,
  halfYearLabel,
  monthLabels,
  ooniTestName,
  paragraphs,
  periodLabel,
  preTransitionSentence,
  splitKeyPhrase,
  stableSentence,
} from "./finding";

describe("paragraphs", () => {
  it("splits on blank lines and trims", () => {
    expect(paragraphs("One.\n\nTwo.\n  \nThree.\n")).toEqual(["One.", "Two.", "Three."]);
  });
  it("keeps a single line break inside a paragraph", () => {
    expect(paragraphs("a\nb")).toEqual(["a\nb"]);
  });
});

describe("splitKeyPhrase", () => {
  const teaser = "The week read STABLE with HIGH confidence, as it happened.";
  it("splits around an exact substring", () => {
    expect(splitKeyPhrase(teaser, "read STABLE with HIGH confidence")).toEqual({
      before: "The week ",
      mark: "read STABLE with HIGH confidence",
      after: ", as it happened.",
    });
  });
  it("returns null for a null or empty phrase", () => {
    expect(splitKeyPhrase(teaser, null)).toBeNull();
    expect(splitKeyPhrase(teaser, "")).toBeNull();
  });
  it("returns null when the phrase is not in the teaser", () => {
    expect(splitKeyPhrase(teaser, "something else")).toBeNull();
  });
  it("handles a phrase that contains quotes", () => {
    const t = 'Weeks before 2008 read "STABLE (insufficient data)" by default.';
    expect(splitKeyPhrase(t, '"STABLE (insufficient data)"')?.mark).toBe('"STABLE (insufficient data)"');
  });
});

describe("groupCitations", () => {
  const c = (url: string, claim: string, citation = `cite ${url}`) => ({ url, claim, citation });
  it("groups by URL in first-appearance order and de-duplicates claims", () => {
    const groups = groupCitations([c("b", "x"), c("a", "y"), c("b", "z"), c("b", "x")]);
    expect(groups.map((g) => g.url)).toEqual(["b", "a"]);
    expect(groups[0]?.claims).toEqual(["x", "z"]);
  });
  it("is empty for no citations", () => {
    expect(groupCitations([])).toEqual([]);
  });
});

describe("halfYearLabel and periodLabel", () => {
  it("labels a half-year", () => {
    expect(halfYearLabel("2024-01-01", "2024-06-30")).toBe("January – June 2024");
    expect(halfYearLabel("2022-07-01", "2022-12-31")).toBe("July – December 2022");
  });
  it("says This week for weekly cards", () => {
    expect(periodLabel({ period_grain: "week", period_start: "2024-06-22", period_end: "2024-06-28" })).toBe(
      "This week",
    );
    expect(periodLabel({ period_grain: "week", period_start: null, period_end: null })).toBe("This week");
  });
  it("uses the dates for half-year cards, and nothing when they are missing", () => {
    expect(periodLabel({ period_grain: "half_year", period_start: "2024-01-01", period_end: "2024-06-30" })).toBe(
      "January – June 2024",
    );
    expect(periodLabel({ period_grain: "half_year", period_start: null, period_end: null })).toBe("");
  });
});

describe("contextRange", () => {
  it("is 91 days either side", () => {
    expect(contextRange("2024-06-22")).toEqual({ from: "2024-03-23", to: "2024-09-21" });
  });
  it("crosses a year boundary", () => {
    expect(contextRange("2008-01-19")).toEqual({ from: "2007-10-20", to: "2008-04-19" });
  });
});

describe("bandCode", () => {
  it("maps bands to colour token letters", () => {
    expect(bandCode("NORMAL")).toBe("n");
    expect(bandCode("ELEVATED")).toBe("e");
    expect(bandCode("SEVERE")).toBe("s");
    expect(bandCode("UNKNOWN")).toBe("u");
  });
});

describe("state wording", () => {
  it("gives the spec sentence only for STABLE with usable data", () => {
    expect(stableSentence({ regime_state: "STABLE", confidence_level: "HIGH" })).toMatch(/^STABLE: no regime rule/);
    expect(stableSentence({ regime_state: "STABLE", confidence_level: "INSUFFICIENT_DATA" })).toBeNull();
    expect(stableSentence({ regime_state: "CRISIS", confidence_level: "HIGH" })).toBeNull();
  });
  it("builds the pre-transition sentence", () => {
    expect(preTransitionSentence("REPRESSION")).toBe(
      "Raised: would have entered REPRESSION if the next week also qualified.",
    );
    expect(preTransitionSentence(null)).toBeNull();
  });
  it("words the confidence level, and omits it for unscored weeks", () => {
    expect(confidenceText({ regime_state: "CRISIS", confidence_level: "HIGH" })).toBe("High confidence");
    expect(confidenceText({ regime_state: "CRISIS", confidence_level: "MEDIUM" })).toBe("Medium confidence");
    expect(confidenceText({ regime_state: "STABLE", confidence_level: "INSUFFICIENT_DATA" })).toBeNull();
  });
});

describe("monthLabels", () => {
  it("labels the first week with a year, and January with a year", () => {
    const weeks = ["2023-12-02", "2023-12-09", "2023-12-16", "2023-12-23", "2023-12-30", "2024-01-06", "2024-02-03"];
    const labels = monthLabels(weeks, 50);
    expect(labels.get(0)).toBe("Dec 2023");
    expect(labels.get(5)).toBe("Jan 2024");
    expect(labels.get(6)).toBe("Feb");
  });
  it("skips a label that would sit too close to the last one", () => {
    const labels = monthLabels(["2024-01-27", "2024-02-03", "2024-02-10"], 10);
    expect([...labels.keys()]).toEqual([0]);
  });
});

describe("ooniTestName", () => {
  it("maps known tests to display names", () => {
    expect(ooniTestName("whatsapp")).toBe("WhatsApp");
    expect(ooniTestName("facebook_messenger")).toBe("Facebook Messenger");
    expect(ooniTestName("web_connectivity")).toBe("Web Connectivity");
    expect(ooniTestName("signal")).toBe("Signal");
    expect(ooniTestName("telegram")).toBe("Telegram");
  });
  it("capitalises unknown names", () => {
    expect(ooniTestName("dnscheck")).toBe("Dnscheck");
  });
});
