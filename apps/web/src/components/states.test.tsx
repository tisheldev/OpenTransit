import { act, render, screen } from "@testing-library/react";
import type { ReactNode } from "react";
import userEvent from "@testing-library/user-event";
import { afterEach, describe, expect, it, vi } from "vitest";
import { UI_STATES } from "../api/classify";
import { I18nProvider } from "../i18n/I18nProvider";
import { en } from "../i18n/en";
import { he } from "../i18n/he";
import type { Lang } from "../i18n/messages";
import { Empty, ErrorState, Loading, StaleDataBanner, TestDataBanner, Unavailable } from "./states";

const renderIn = (lang: Lang, ui: ReactNode) => render(<I18nProvider initialLang={lang}>{ui}</I18nProvider>);

afterEach(() => vi.useRealTimers());

describe("state components", () => {
  it("announce loading politely", () => {
    renderIn("he", <Loading />);
    expect(screen.getByRole("status")).toHaveTextContent(he["state.loading"]);
    expect(screen.getByRole("status")).toHaveAttribute("aria-busy", "true");
  });

  it("show empty results as a calm status, not an error", () => {
    renderIn("en", <Empty kind="noRoute" />);
    expect(screen.getByRole("status")).toHaveTextContent(en["state.empty.noRoute"]);
    expect(screen.queryByRole("alert")).toBeNull();
  });

  it("say live data is unavailable rather than empty", () => {
    renderIn("he", <Unavailable kind="live" />);
    expect(screen.getByRole("note")).toHaveTextContent("זמנים בזמן אמת והתראות אינם זמינים");
  });

  it("name unavailable search categories inline", () => {
    renderIn("en", <Unavailable kind="category" categories={["poi", "address"]} />);
    expect(screen.getByRole("note")).toHaveTextContent("Place, Address");
  });

  it("fall back when coverage is unknown outside the service window", () => {
    renderIn("he", <ErrorState state="outside_window" />);
    expect(screen.getByRole("alert")).toHaveTextContent(he["error.outside_window.noDates"]);
  });

  it.each(UI_STATES.filter((state) => state !== "outside_window"))("render the %s error in both languages", (state) => {
    const { unmount } = renderIn("he", <ErrorState state={state} />);
    expect(screen.getByRole("alert")).toHaveTextContent(he[`error.${state}`]);
    unmount();
    renderIn("en", <ErrorState state={state} />);
    expect(screen.getByRole("alert")).toHaveTextContent(en[`error.${state}`]);
  });

  it("show the coverage dates outside the service window", () => {
    renderIn(
      "en",
      <ErrorState state="outside_window" coverage={{ from: "2026-09-30T00:00:00+03:00", until: "2026-10-31T00:00:00+02:00" }} />,
    );
    expect(screen.getByRole("alert")).toHaveTextContent("Choose between Wed 30 Sept and Sat 31 Oct");
  });

  it("offer retry only for transient states", async () => {
    const onRetry = vi.fn();
    const { unmount } = renderIn("en", <ErrorState state="temporarily_unavailable" onRetry={onRetry} />);
    await userEvent.click(screen.getByRole("button", { name: en["state.retry"] }));
    expect(onRetry).toHaveBeenCalledOnce();
    unmount();
    renderIn("en", <ErrorState state="not_found" onRetry={onRetry} />);
    expect(screen.queryByRole("button")).toBeNull();
  });

  it("honour Retry-After before allowing a retry", () => {
    vi.useFakeTimers();
    renderIn("en", <ErrorState state="rate_limited" retryAfterSeconds={2} onRetry={() => {}} />);
    expect(screen.getByRole("button")).toBeDisabled();
    expect(screen.getByRole("button")).toHaveTextContent("try again in 2 s");
    act(() => vi.advanceTimersByTime(2_500));
    expect(screen.getByRole("button")).toBeEnabled();
    expect(screen.getByRole("button")).toHaveTextContent(en["state.retry"]);
  });

  it("label test data and stale data", () => {
    renderIn("he", (
      <>
        <TestDataBanner />
        <StaleDataBanner />
      </>
    ));
    const notes = screen.getAllByRole("note").map((note) => note.textContent);
    expect(notes).toEqual([he["banner.testData"], he["banner.staleData"]]);
  });
});
