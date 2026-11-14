import "@testing-library/jest-dom/vitest";
import { cleanup } from "@testing-library/react";
import { afterEach, beforeEach, vi } from "vitest";

// jsdom tidak punya WebGL: getContext() mengembalikan null (seperti browser tanpa dukungan) tanpa log "Not implemented".
beforeEach(() => {
  vi.spyOn(HTMLCanvasElement.prototype, "getContext").mockReturnValue(null);
});

afterEach(() => cleanup());
