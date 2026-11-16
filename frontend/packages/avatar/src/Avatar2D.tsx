import type { AgentState } from "./states";
import { STATE_LABELS } from "./states";
import "./avatar2d.css";

type Mouth = "rest" | "talk" | "smile" | "frown" | "flat" | "open";

const MOUTH: Record<AgentState, Mouth> = {
  IDLE: "rest", LISTENING: "flat", THINKING: "flat", RESEARCHING: "flat", ANALYZING: "flat",
  PLANNING: "flat", CREATING: "rest", EXECUTING: "flat", WAITING_APPROVAL: "open", SPEAKING: "talk",
  COMPLETED: "smile", FAILED: "frown",
};

const MOUTH_PATH: Record<Mouth, string> = {
  rest: "M 84 134 Q 100 142 116 134",
  smile: "M 80 130 Q 100 150 120 130",
  frown: "M 82 140 Q 100 128 118 140",
  flat: "M 86 136 L 114 136",
  open: "M 90 134 Q 100 146 110 134 Q 100 140 90 134",
  talk: "M 84 134 Q 100 150 116 134 Q 100 140 84 134",
};

export interface Avatar2DProps {
  state: AgentState;
  size?: number;
}

/** Avatar 2D berbasis SVG + CSS: hampir tanpa beban GPU. Setiap tampilan berasal dari status nyata. */
export function Avatar2D({ state, size = 220 }: Avatar2DProps) {
  const mouth = MOUTH[state];
  return (
    <figure className="zoi-avatar2d" data-state={state} style={{ width: size }}>
      <svg viewBox="0 0 200 200" width={size} height={size} role="img" aria-label={`Avatar ZOI: ${STATE_LABELS[state]}`}>
        <circle className="zoi-ring" cx="100" cy="100" r="94" />
        <circle className="zoi-head" cx="100" cy="100" r="72" />
        <g className="zoi-eyes">
          <ellipse className="zoi-eye" cx="76" cy="92" rx="9" ry="11" />
          <ellipse className="zoi-eye" cx="124" cy="92" rx="9" ry="11" />
        </g>
        <path className={`zoi-mouth zoi-mouth-${mouth}`} d={MOUTH_PATH[mouth]} />
        {state === "WAITING_APPROVAL" && <text className="zoi-mark" x="150" y="58">?</text>}
      </svg>
      <figcaption className="zoi-avatar-label">{STATE_LABELS[state]}</figcaption>
    </figure>
  );
}
