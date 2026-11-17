import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { MemoryRouter } from "react-router-dom";
import { afterEach, describe, expect, it, vi } from "vitest";

import { mockFetch } from "../test/helpers";
import { UpdateBanner, UpdatePage } from "./UpdatePage";

const latest = { version: "1.3.0", name: "ZOI 1.3.0", notes: "- fitur baru", published_at: null, url: null,
  zip_url: "z", sha_url: "s", size: 5_000_000 };
const st = (over: object) => ({ enabled: true, repo: "Fariz23zoi/zoi-command-center", current: "1.2.4", latest,
  update_available: true, checked_at: "2026-11-17T00:00:00Z", error: null, phase: "idle", can_install: true,
  install_note: null, ...over });

afterEach(() => vi.unstubAllGlobals());

describe("Update", () => {
  it("menampilkan versi baru dan memasang setelah konfirmasi", async () => {
    const fetchFn = mockFetch({ "/api/update/status": st({}), "/api/update/install": st({ phase: "applying" }) });
    vi.stubGlobal("confirm", vi.fn(() => true));
    render(<MemoryRouter><UpdatePage /></MemoryRouter>);
    expect(await screen.findByTestId("update-current")).toHaveTextContent("1.2.4");
    expect(screen.getByText("- fitur baru")).toBeInTheDocument();
    fireEvent.click(screen.getByTestId("update-install"));
    await waitFor(() => expect(fetchFn).toHaveBeenCalledWith("/api/update/install", expect.objectContaining({ method: "POST" })));
    expect(await screen.findByText(/sedang dipasang di jendela baru/)).toBeInTheDocument();
  });

  it("banner hanya muncul bila ada update", async () => {
    mockFetch({ "/api/update/status": st({ update_available: false }) });
    const { container } = render(<MemoryRouter><UpdateBanner /></MemoryRouter>);
    await waitFor(() => expect(container).toBeEmptyDOMElement());
  });
});
