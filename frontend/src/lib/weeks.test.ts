import { describe, expect, it } from "vitest";
import {
  cellKey,
  confidenceLine,
  dayOfYear,
  gridColumn,
  gridRow,
  hasDatePrefix,
  isInsufficient,
  monthYear,
  numberWord,
  parseUtc,
  range,
  recId,
  stateLabel,
  titleNoDate,
} from "./weeks";

describe("grid position", () => {
  it("puts 1997-01-11 in row 0, column 1", () => {
    expect(gridRow("1997-01-11", 1997)).toBe(0);
    expect(gridColumn("1997-01-11")).toBe(1);
  });
  it("puts 2024-06-22 in column 24 (leap year, day 173)", () => {
    expect(dayOfYear(parseUtc("2024-06-22"))).toBe(173);
    expect(gridColumn("2024-06-22")).toBe(24);
  });
  it("never exceeds column 52", () => {
    expect(gridColumn("2024-12-31")).toBe(52);
    expect(gridColumn("2025-12-31")).toBe(52);
  });
  it("parses as UTC regardless of the local zone", () => {
    expect(parseUtc("2024-06-22").toISOString()).toBe("2024-06-22T00:00:00.000Z");
  });
});

describe("labels", () => {
  it("builds the record id", () => {
    expect(recId("2024-06-22")).toBe("KE·2024·W25");
    expect(recId("1997-01-11")).toBe("KE·1997·W02");
  });
  it("formats a same-month range short", () => {
    expect(range("2024-06-22")).toBe("22–28 Jun 2024");
  });
  it("formats a range crossing a month in long form", () => {
    expect(range("2024-06-29")).toBe("29 Jun 2024 – 5 Jul 2024");
  });
  it("formats a range crossing a year in long form", () => {
    expect(range("2022-12-31")).toBe("31 Dec 2022 – 6 Jan 2023");
  });
  it("gives the abbreviated month and year", () => {
    expect(monthYear("2024-06-22")).toBe("Jun 2024");
  });
});

describe("insufficient data", () => {
  it("is true only for STABLE with INSUFFICIENT_DATA", () => {
    expect(isInsufficient({ regime_state: "STABLE", confidence_level: "INSUFFICIENT_DATA" })).toBe(true);
    expect(isInsufficient({ regime_state: "ESCALATION", confidence_level: "INSUFFICIENT_DATA" })).toBe(false);
    expect(isInsufficient({ regime_state: "STABLE", confidence_level: "HIGH" })).toBe(false);
  });
  it("picks the colour key, state label and confidence line", () => {
    const unscored = { regime_state: "STABLE", confidence_level: "INSUFFICIENT_DATA" } as const;
    const esc = { regime_state: "ESCALATION", confidence_level: "INSUFFICIENT_DATA" } as const;
    const crisis = { regime_state: "CRISIS", confidence_level: "MEDIUM" } as const;
    expect(cellKey(unscored)).toBe("I");
    expect(cellKey(esc)).toBe("E");
    expect(stateLabel(unscored)).toBe("STABLE (insufficient data)");
    expect(confidenceLine(unscored)).toBeNull();
    expect(confidenceLine(esc)).toBe("Insufficient data");
    expect(confidenceLine(crisis)).toBe("Medium confidence");
  });
});

describe("words and titles", () => {
  it("spells out one to nine", () => {
    expect(numberWord(5)).toBe("five");
    expect(numberWord(9)).toBe("nine");
    expect(numberWord(12)).toBe("12");
  });
  it("strips a date prefix and capitalises", () => {
    const t = "22–28 June 2024: protest and suppression both SEVERE";
    expect(hasDatePrefix(t)).toBe(true);
    expect(titleNoDate(t)).toBe("Protest and suppression both SEVERE");
  });
  it("leaves a title without a prefix alone", () => {
    expect(hasDatePrefix("Telegram far above baseline")).toBe(false);
    expect(titleNoDate("Telegram far above baseline")).toBe("Telegram far above baseline");
  });
});
