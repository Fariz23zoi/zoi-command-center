import type { PublicConfig } from "@zoi/api-client";
import { vi } from "vitest";

export function config(overrides: Partial<PublicConfig> = {}): PublicConfig {
  return {
    version: "0.1.0", mode: "development", banner: "DEVELOPMENT MODE — jawaban AI adalah MOCK, bukan AI sungguhan",
    provider: "mock", is_mock: true, ollama_url: null, ollama_model: null, avatar_mode: "auto", host: "127.0.0.1",
    port: 8000, base_url: "http://127.0.0.1:8000", data_dir: "/data", warnings: [], migration_backup: null,
    config_source: ".env", ...overrides,
  };
}

/** fetch tiruan: memetakan path API ke respons JSON. */
/** Rute bisa berupa nilai langsung, atau fungsi (menerima body permintaan) yang mengembalikan nilai.
 *  Nilai berbentuk { status, body } dipakai untuk menjawab dengan kode HTTP selain 200. */
export function mockFetch(routes: Record<string, unknown>) {
  const fn = vi.fn(async (input: RequestInfo | URL, init?: RequestInit) => {
    const path = typeof input === "string" ? input : input.toString();
    const key = Object.keys(routes).find((k) => path === k || path.startsWith(k + "?"));
    let body = key ? routes[key] : { error: { message: "tidak ada" } };
    if (typeof body === "function") {
      body = body(init?.body ? JSON.parse(init.body as string) : undefined);
    }
    const shaped = body as { status?: number; body?: unknown };
    if (shaped && typeof shaped.status === "number" && "body" in shaped) {
      return new Response(JSON.stringify(shaped.body), { status: shaped.status });
    }
    return new Response(JSON.stringify(body), { status: key ? 200 : 404 });
  });
  vi.stubGlobal("fetch", fn);
  return fn;
}

export class FakeWebSocket {
  static instances: FakeWebSocket[] = [];
  onopen: (() => void) | null = null;
  onmessage: ((m: { data: string }) => void) | null = null;
  onclose: (() => void) | null = null;
  constructor(public url: string) { FakeWebSocket.instances.push(this); }
  emit(event: unknown) { this.onmessage?.({ data: JSON.stringify(event) }); }
  close() { this.onclose?.(); }
}
