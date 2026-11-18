import { fireEvent, render, screen } from "@testing-library/react";
import { MemoryRouter } from "react-router-dom";
import { afterEach, describe, expect, it, vi } from "vitest";

import { mockFetch } from "../test/helpers";
import { rng } from "../thumbnail/render";
import { ThumbnailPage } from "./ThumbnailPage";

afterEach(() => vi.unstubAllGlobals());

const HOOK = {
  baris: [{ teks: "Pernah nggak sih,", ukuran: "sedang", warna: "hitam", kotak: "putih" },
    { teks: "NGGAK MAU", ukuran: "besar", warna: "pink", kotak: "tanpa" }],
  bubble: ["GILA!"], aksen: "pink", provider: "nvidia", is_mock: false,
};

describe("Thumbnail otomatis", () => {
  it("tombol aktif setelah topik diisi; teks hook dari AI ZOI bisa diedit", async () => {
    const fetchFn = mockFetch({ "/api/thumbnail/hook": HOOK });
    render(<MemoryRouter><ThumbnailPage /></MemoryRouter>);
    const go = screen.getByTestId("thumb-generate");
    expect(go).toBeDisabled();
    fireEvent.change(screen.getByTestId("thumb-topik"), { target: { value: "susah menolak teman" } });
    fireEvent.click(go);
    expect(await screen.findAllByTestId("thumb-line")).toHaveLength(2);
    expect(screen.getByTestId("thumb-canvas")).toBeInTheDocument();
    expect(screen.getByText(/AI ZOI \(nvidia\)/)).toBeInTheDocument();
    const call = fetchFn.mock.calls.find(([url]) => String(url).includes("/api/thumbnail/hook"));
    expect(JSON.parse(String((call?.[1] as RequestInit).body))).toEqual({ topik: "susah menolak teman", rasio: "9:16" });
    fireEvent.change(screen.getByLabelText("Baris 2"), { target: { value: "OGAH!" } });
    expect(screen.getByLabelText("Baris 2")).toHaveValue("OGAH!");
  });

  it("acak gaya deterministik per seed", () => {
    const a = rng(42), b = rng(42);
    expect([a(), a(), a()]).toEqual([b(), b(), b()]);
  });
});
