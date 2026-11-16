import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { MemoryRouter } from "react-router-dom";
import { afterEach, describe, expect, it, vi } from "vitest";

import { mockFetch } from "../test/helpers";
import { SettingsPage } from "./SettingsPage";

afterEach(() => vi.unstubAllGlobals());

describe("Settings › Cadangan data", () => {
  it("unduh menunjuk ke /api/backup/download; pulihkan butuh konfirmasi", async () => {
    const fetchFn = mockFetch({
      "/api/backup/restore": { ok: true, note: "Data dipulihkan. Rahasia tidak ikut arsip." },
    });
    render(<MemoryRouter><SettingsPage /></MemoryRouter>);
    const block = await screen.findByTestId("backup-block");
    expect(block).toHaveTextContent("tidak pernah");
    expect(screen.getByTestId("backup-download")).toHaveAttribute("href", "/api/backup/download");
    const file = new File(["zip"], "zoi-backup.zip", { type: "application/zip" });
    fireEvent.change(screen.getByTestId("backup-file"), { target: { files: [file] } });
    expect(screen.queryByTestId("backup-restore")).not.toBeInTheDocument();
    fireEvent.click(screen.getByRole("button", { name: /Pulihkan dari zoi-backup.zip/ }));
    fireEvent.click(screen.getByTestId("backup-restore"));
    await waitFor(() => expect(fetchFn).toHaveBeenCalledWith("/api/backup/restore",
      expect.objectContaining({ method: "POST" })));
    expect(await screen.findByRole("status")).toHaveTextContent("Data dipulihkan");
  });
});
