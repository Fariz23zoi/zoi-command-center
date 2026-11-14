import { describe, expect, it } from "vitest";

import { effectiveAvatarMode } from "./avatarMode";

describe("effectiveAvatarMode", () => {
  it("server 2D selalu menang", () => {
    expect(effectiveAvatarMode("2d", "3d")).toBe("2d");
  });
  it("preferensi otomatis mengikuti server", () => {
    expect(effectiveAvatarMode("3d", "auto")).toBe("3d");
    expect(effectiveAvatarMode(undefined, undefined)).toBe("auto");
  });
  it("preferensi eksplisit dipakai bila server tidak memaksa", () => {
    expect(effectiveAvatarMode("auto", "2d")).toBe("2d");
    expect(effectiveAvatarMode("auto", "3d")).toBe("3d");
  });
});
