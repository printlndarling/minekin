import { act, renderHook, waitFor } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";
import { useHashRoute } from "./useHashRoute";

afterEach(() => {
  vi.restoreAllMocks();
  window.history.replaceState(null, "", "/");
});

describe("dashboard page history", () => {
  it("preserves Gateway query parameters and adds no duplicate entry for the current page", () => {
    window.history.replaceState(null, "", "/?adapter=gateway&gateway=%2Fgateway#task");
    const push = vi.spyOn(window.history, "pushState");
    const { result } = renderHook(() => useHashRoute());
    act(() => result.current[1]("config"));
    expect(result.current[0]).toBe("config");
    expect(window.location.search).toBe("?adapter=gateway&gateway=%2Fgateway");
    expect(push).toHaveBeenCalledTimes(1);
    act(() => result.current[1]("config"));
    expect(push).toHaveBeenCalledTimes(1);
  });

  it("follows browser back and forward without recreating the initial page", async () => {
    window.history.replaceState(null, "", "/?adapter=mock#task");
    const { result } = renderHook(() => useHashRoute());
    act(() => result.current[1]("timeline"));
    act(() => result.current[1]("alerts"));
    act(() => window.history.back());
    await waitFor(() => expect(result.current[0]).toBe("timeline"));
    act(() => window.history.back());
    await waitFor(() => expect(result.current[0]).toBe("task"));
    act(() => window.history.forward());
    await waitFor(() => expect(result.current[0]).toBe("timeline"));
    expect(window.location.search).toBe("?adapter=mock");
  });

  it("uses replacement only to establish an initial fragment", () => {
    window.history.replaceState(null, "", "/?adapter=mock");
    const push = vi.spyOn(window.history, "pushState");
    const { result } = renderHook(() => useHashRoute("recipes"));
    expect(result.current[0]).toBe("recipes");
    expect(window.location.hash).toBe("#recipes");
    expect(push).not.toHaveBeenCalled();
  });
});
