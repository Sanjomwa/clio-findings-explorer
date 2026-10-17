import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import ThemeSwitch from "./ThemeSwitch";

beforeEach(() => {
  document.documentElement.setAttribute("data-theme", "light");
  window.localStorage.clear();
});
afterEach(() => vi.restoreAllMocks());

describe("ThemeSwitch", () => {
  it("reflects the current theme in aria-pressed", () => {
    render(<ThemeSwitch />);
    expect(screen.getByRole("button", { name: "Light" })).toHaveAttribute("aria-pressed", "true");
    expect(screen.getByRole("button", { name: "Dark" })).toHaveAttribute("aria-pressed", "false");
  });

  it("sets data-theme, updates aria-pressed and persists the choice", async () => {
    render(<ThemeSwitch />);
    await userEvent.click(screen.getByRole("button", { name: "Dark" }));
    expect(document.documentElement).toHaveAttribute("data-theme", "dark");
    expect(screen.getByRole("button", { name: "Dark" })).toHaveAttribute("aria-pressed", "true");
    expect(screen.getByRole("button", { name: "Light" })).toHaveAttribute("aria-pressed", "false");
    expect(window.localStorage.getItem("cfe-theme")).toBe("dark");
  });

  it("still works when localStorage throws", async () => {
    vi.spyOn(Storage.prototype, "setItem").mockImplementation(() => {
      throw new Error("blocked");
    });
    vi.spyOn(Storage.prototype, "getItem").mockImplementation(() => {
      throw new Error("blocked");
    });
    render(<ThemeSwitch />);
    await userEvent.click(screen.getByRole("button", { name: "Dark" }));
    expect(document.documentElement).toHaveAttribute("data-theme", "dark");
    expect(screen.getByRole("button", { name: "Dark" })).toHaveAttribute("aria-pressed", "true");
  });
});
