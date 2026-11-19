import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { MemoryRouter, Route, Routes } from "react-router-dom";
import { afterEach, describe, expect, it, vi } from "vitest";

import { mockFetch } from "../test/helpers";
import { ArtifactViewerPage, ArtifactsPage } from "./ArtifactsPage";
import { CodePage } from "./CodePage";

afterEach(() => vi.unstubAllGlobals());

const ART = { id: "abc123def456", judul: "Kalkulator BMI", versi: 2, dibuat: 1, updated: 1_763_000_000, sumber: "ai",
  bytes: 100, provider: "nvidia", mock: false, url: "/artefak/abc123def456", raw_url: "/artefak-raw/abc123def456/",
  riwayat: [] };

describe("Artefak", () => {
  it("daftar artefak tampil; tombol AI aktif setelah permintaan diisi", async () => {
    mockFetch({ "/api/artifacts": { items: [ART] } });
    render(<MemoryRouter><ArtifactsPage /></MemoryRouter>);
    expect(await screen.findByText("Kalkulator BMI")).toBeInTheDocument();
    expect(screen.getByTestId("art-generate")).toBeDisabled();
    fireEvent.change(screen.getByTestId("art-request"), { target: { value: "kuis tata surya" } });
    expect(screen.getByTestId("art-generate")).toBeEnabled();
  });

  it("penampil memakai iframe sandbox tanpa allow-same-origin", async () => {
    mockFetch({ "/api/artifacts/abc123def456": ART });
    render(<MemoryRouter initialEntries={["/artefak/abc123def456"]}><Routes>
      <Route path="/artefak/:id" element={<ArtifactViewerPage />} /></Routes></MemoryRouter>);
    const frame = await screen.findByTestId("art-frame");
    expect(frame.getAttribute("sandbox")).toContain("allow-scripts");
    expect(frame.getAttribute("sandbox")).not.toContain("allow-same-origin");
    expect(frame.getAttribute("src")).toBe("/artefak-raw/abc123def456/?v=2");
  });
});

describe("Code", () => {
  it("menampilkan permintaan izin dan mengirim keputusan", async () => {
    const waiting = { id: "s1", project: "demo", status: "waiting", allow_all: false, task_id: "t", provider: "nvidia",
      pending: { alat: "jalankan", args: { perintah: "python halo.py" } },
      steps: [{ jenis: "pengguna", waktu: 1, teks: "buat halo" }] };
    const fetchFn = mockFetch({
      "/api/code/projects": { items: [{ name: "demo", files: 1, updated: 1 }] },
      "/api/code/projects/demo/files": { items: [{ path: "halo.py", bytes: 10 }] },
      "/api/code/sessions": waiting,
      "/api/code/sessions/s1": waiting,
      "/api/code/sessions/s1/izin": { ...waiting, status: "running", pending: null },
    });
    render(<MemoryRouter><CodePage /></MemoryRouter>);
    expect(await screen.findByText("halo.py")).toBeInTheDocument();
    fireEvent.change(screen.getByTestId("code-input"), { target: { value: "buat halo" } });
    fireEvent.click(screen.getByTestId("code-send"));
    expect(await screen.findByTestId("code-approve")).toHaveTextContent("python halo.py");
    fireEvent.click(screen.getByTestId("code-allow"));
    await waitFor(() => expect(fetchFn.mock.calls.some(([u]) => String(u).endsWith("/izin"))).toBe(true));
    const call = fetchFn.mock.calls.find(([u]) => String(u).endsWith("/izin"));
    expect(JSON.parse(String((call?.[1] as RequestInit).body))).toEqual({ setuju: true, semua: false });
  });
});
