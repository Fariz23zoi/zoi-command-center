import { render, screen } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";

import { AGENT_STATES, Avatar, type AvatarControllerRef, STATE_LABELS } from "./index";

describe("Avatar", () => {
  it.each(AGENT_STATES)("menampilkan status %s apa adanya", (state) => {
    const { container } = render(<Avatar state={state} />);
    expect(container.querySelector("[data-state]")?.getAttribute("data-state")).toBe(state);
    expect(screen.getByRole("img")).toHaveAccessibleName(`Avatar ZOI: ${STATE_LABELS[state]}`);
  });

  it("browser tanpa WebGL 2 memakai 2D dan menjelaskan alasannya", () => {
    const onRendererChange = vi.fn();
    const { container } = render(<Avatar state="IDLE" mode="3d" onRendererChange={onRendererChange} />);
    expect(container.querySelector("[data-renderer]")?.getAttribute("data-renderer")).toBe("2d");
    expect(screen.getByText(/tidak mendukung WebGL 2/)).toBeInTheDocument();
    expect(onRendererChange).toHaveBeenCalledWith("2d", expect.stringMatching(/WebGL 2/));
  });

  it("mode 2D tidak menampilkan catatan apa pun", () => {
    render(<Avatar state="IDLE" mode="2d" />);
    expect(screen.queryByText(/tidak mendukung/)).not.toBeInTheDocument();
  });

  it("controller 2D menolak lip-sync dengan jujur", async () => {
    const ref: AvatarControllerRef = { current: null };
    render(<Avatar state="IDLE" mode="2d" controllerRef={ref} />);
    expect(ref.current?.renderer).toBe("2d");
    await expect(ref.current!.speak(new Blob())).rejects.toThrow(/hanya tersedia pada avatar 3D/);
  });

  it("status sama persis dengan backend", () => {
    expect(AGENT_STATES).toEqual([
      "IDLE", "LISTENING", "THINKING", "RESEARCHING", "ANALYZING", "PLANNING", "CREATING", "EXECUTING",
      "WAITING_APPROVAL", "SPEAKING", "COMPLETED", "FAILED",
    ]);
  });
});
