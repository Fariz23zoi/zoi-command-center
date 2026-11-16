import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";

import { mockFetch } from "../test/helpers";
import { AuthGate } from "./AuthGate";

const CHILD = <p data-testid="app-ready">Aplikasi</p>;
const show = () => render(<AuthGate>{CHILD}</AuthGate>);

afterEach(() => vi.unstubAllGlobals());

describe("AuthGate (mode online)", () => {
  it("auth nonaktif (development/local) → aplikasi langsung tampil", async () => {
    mockFetch({ "/api/auth/status": { enabled: false, ready: true, logged_in: false } });
    show();
    expect(await screen.findByTestId("app-ready")).toBeInTheDocument();
  });

  it("belum setup → form setup token; sesudah dikirim aplikasi terbuka", async () => {
    let ready = false;
    mockFetch({
      "/api/auth/status": () => ({ enabled: true, ready, logged_in: ready }),
      "/api/auth/setup": () => { ready = true; return { ok: true }; },
    });
    show();
    expect(await screen.findByText(/ZOI_SETUP_TOKEN/)).toBeInTheDocument();
    fireEvent.change(screen.getByLabelText("Setup token"), { target: { value: "token-rahasia" } });
    fireEvent.change(screen.getByLabelText("Kata sandi baru"), { target: { value: "kata-sandi-panjang" } });
    fireEvent.click(screen.getByRole("button", { name: "Buat kata sandi" }));
    expect(await screen.findByTestId("app-ready")).toBeInTheDocument();
  });

  it("sudah setup tapi belum masuk → form kata sandi; salah → pesan galat", async () => {
    let logged = false;
    mockFetch({
      "/api/auth/status": () => ({ enabled: true, ready: true, logged_in: logged }),
      "/api/auth/login": (body: { password: string }) => {
        if (body.password !== "benar-sekali") {
          return { status: 401, body: { error: { code: "kata_sandi_salah", message: "Kata sandi salah." } } };
        }
        logged = true;
        return { ok: true };
      },
    });
    show();
    const field = await screen.findByLabelText("Kata sandi");
    fireEvent.change(field, { target: { value: "salah" } });
    fireEvent.click(screen.getByRole("button", { name: "Masuk" }));
    expect(await screen.findByRole("alert")).toHaveTextContent("Kata sandi salah.");
    fireEvent.change(screen.getByLabelText("Kata sandi"), { target: { value: "benar-sekali" } });
    fireEvent.click(screen.getByRole("button", { name: "Masuk" }));
    expect(await screen.findByTestId("app-ready")).toBeInTheDocument();
  });

  it("sesi habis di tengah pemakaian (zoi-unauthorized) → kembali ke halaman masuk", async () => {
    mockFetch({ "/api/auth/status": { enabled: true, ready: true, logged_in: true } });
    show();
    expect(await screen.findByTestId("app-ready")).toBeInTheDocument();
    window.dispatchEvent(new Event("zoi-unauthorized"));
    await waitFor(() => expect(screen.getByLabelText("Kata sandi")).toBeInTheDocument());
  });
});
