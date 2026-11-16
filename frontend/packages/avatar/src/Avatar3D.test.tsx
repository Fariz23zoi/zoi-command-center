import { act, render, screen } from "@testing-library/react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import type { AvatarControllerRef } from "./controller";

const instances: FakeAvatar[] = [];
let resolveReady: () => void;

class FakeAvatar {
  opts: { avatarUrl: string; modelUrl: string };
  ready: Promise<void>;
  setStatus = vi.fn();
  setAvatar = vi.fn(() => Promise.resolve());
  speak = vi.fn(() => Promise.resolve());
  stopSpeaking = vi.fn();
  dispose = vi.fn();
  constructor(opts: { avatarUrl: string; modelUrl: string }) {
    this.opts = opts;
    this.ready = new Promise((r) => { resolveReady = r; });
    instances.push(this);
  }
}

vi.mock("@interviewflowai/talking-avatar", () => ({ TalkingAvatar: FakeAvatar }));
vi.mock("./benchmark", async (orig) => ({ ...(await orig<object>()), measureFps: vi.fn(() => Promise.resolve(12)) }));

const { default: Avatar3D } = await import("./Avatar3D");

describe("Avatar3D", () => {
  beforeEach(() => { instances.length = 0; });
  afterEach(() => localStorage.clear());

  it("memuat aset dari folder lokal, meneruskan status, dan dibuang saat unmount", async () => {
    const ref: AvatarControllerRef = { current: null };
    const { rerender, unmount } = render(
      <Avatar3D state="IDLE" character="male" assetBase="/avatar-assets" size={180} benchmark={false}
        controllerRef={ref} onFallback={vi.fn()} />);
    const avatar = instances[0];
    expect(avatar.opts.avatarUrl).toBe("/avatar-assets/male.glb");
    expect(avatar.opts.modelUrl).toBe("/avatar-assets/viseme-model.bin");
    expect(screen.getByText("Memuat avatar 3D…")).toBeInTheDocument();

    await act(async () => resolveReady());
    expect(screen.queryByText("Memuat avatar 3D…")).not.toBeInTheDocument();

    rerender(<Avatar3D state="THINKING" character="male" assetBase="/avatar-assets" size={180} benchmark={false}
      controllerRef={ref} onFallback={vi.fn()} />);
    expect(avatar.setStatus).toHaveBeenLastCalledWith("thinking");

    rerender(<Avatar3D state="THINKING" character="female" assetBase="/avatar-assets" size={180} benchmark={false}
      controllerRef={ref} onFallback={vi.fn()} />);
    expect(avatar.setAvatar).toHaveBeenCalledWith("/avatar-assets/female.glb");

    const blob = new Blob();
    await ref.current!.speak(blob);
    expect(avatar.speak).toHaveBeenCalledWith(blob);

    unmount();
    expect(avatar.dispose).toHaveBeenCalled();
    expect(ref.current).toBeNull();
  });

  it("FPS di bawah batas → fallback ke 2D dan hasil disimpan", async () => {
    const onFallback = vi.fn();
    render(<Avatar3D state="IDLE" character="female" assetBase="/a" size={180} benchmark onFallback={onFallback} />);
    await act(async () => resolveReady());
    await act(async () => undefined);
    expect(onFallback).toHaveBeenCalledWith(expect.stringMatching(/sekitar 12 fps/));
    expect(localStorage.getItem("zoi.avatar.fps.v1")).toBe("12.0");
  });
});
