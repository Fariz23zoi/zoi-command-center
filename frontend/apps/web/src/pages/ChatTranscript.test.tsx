import type { ChatMessageInfo } from "@zoi/api-client";
import { render, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";

import { ChatTranscript } from "./ChatTranscript";

const base: ChatMessageInfo = {
  id: "a1", conversation_id: "c1", role: "assistant", content: "Jawaban.", provider: "ollama", model: "qwen3:4b",
  is_mock: false, status: "complete", error: null, created_at: null,
};

describe("ChatTranscript", () => {
  it("proses berpikir dilipat dan terpisah dari jawaban", () => {
    render(<ChatTranscript messages={[{ ...base, thinking: "Menimbang." }]} />);
    const details = screen.getByTestId("msg-thinking");
    expect(details).not.toHaveAttribute("open");
    expect(details).toHaveTextContent("Menimbang.");
    expect(screen.getByText("Jawaban.")).toBeInTheDocument();
  });

  it("jawaban yang dihentikan diberi label", () => {
    render(<ChatTranscript messages={[{ ...base, status: "stopped", content: "Sebagian" }]} />);
    expect(screen.getByTestId("stopped-badge")).toHaveTextContent("dihentikan");
  });
});
