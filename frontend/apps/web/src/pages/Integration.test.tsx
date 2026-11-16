import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { MemoryRouter } from "react-router-dom";
import { afterEach, describe, expect, it, vi } from "vitest";

import { mockFetch } from "../test/helpers";
import { IntegrationPage } from "./IntegrationPage";

const bp = (over: object) => ({ available: true, hyperframes: null, narration: null,
  blueprint: { configured: true, original_found: true, copy_exists: false, up_to_date: false, problem: null,
    url: "/blueprint-studio/", ...over } });

afterEach(() => vi.unstubAllGlobals());

describe("Blueprint Studio — tombol buka", () => {
  it("membuat salinan bila belum ada, lalu membuka /blueprint-studio/ di tab baru", async () => {
    const fetchFn = mockFetch({ "/api/production/status": bp({}), "/api/production/blueprint/build": bp({}).blueprint });
    const tab = { location: { href: "" }, close: vi.fn() };
    vi.stubGlobal("open", vi.fn(() => tab));
    render(<MemoryRouter><IntegrationPage adapterName="blueprint_studio" /></MemoryRouter>);
    fireEvent.click(await screen.findByTestId("blueprint-open"));
    await waitFor(() => expect(tab.location.href).toBe("/blueprint-studio/"));
    expect(fetchFn).toHaveBeenCalledWith("/api/production/blueprint/build", expect.objectContaining({ method: "POST" }));
  });

  it("belum dikonfigurasi → tombol mati dengan petunjuk", async () => {
    mockFetch({ "/api/production/status": bp({ configured: false, original_found: false }) });
    render(<MemoryRouter><IntegrationPage adapterName="blueprint_studio" /></MemoryRouter>);
    expect(await screen.findByTestId("blueprint-open")).toBeDisabled();
    expect(screen.getByText(/ZOI_BLUEPRINT_FILE di file .env dengan lokasi/)).toBeInTheDocument();
  });
});
