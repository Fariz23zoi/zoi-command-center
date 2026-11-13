import { render, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";

import { AGENT_STATES, Avatar, STATE_LABELS } from "./index";

describe("Avatar", () => {
  it.each(AGENT_STATES)("menampilkan status %s apa adanya", (state) => {
    const { container } = render(<Avatar state={state} />);
    expect(container.querySelector("[data-state]")?.getAttribute("data-state")).toBe(state);
    expect(screen.getByRole("img")).toHaveAccessibleName(`Avatar ZOI: ${STATE_LABELS[state]}`);
  });

  it("memberi tahu jujur bahwa 3D belum tersedia", () => {
    render(<Avatar state="IDLE" mode="3d" />);
    expect(screen.getByText(/3D tersedia di Phase 2/)).toBeInTheDocument();
  });

  it("status sama persis dengan backend", () => {
    expect(AGENT_STATES).toEqual([
      "IDLE", "LISTENING", "THINKING", "RESEARCHING", "ANALYZING", "PLANNING", "CREATING", "EXECUTING",
      "WAITING_APPROVAL", "SPEAKING", "COMPLETED", "FAILED",
    ]);
  });
});
