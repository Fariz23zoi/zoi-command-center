/* Kantor isometrik 3D low-poly tempat avatar ZOI bekerja (React Three Fiber, MIT).
   Ringan untuk laptop RAM 7 GB / iGPU: geometri primitif, tanpa tekstur & bayangan, maks ±30 fps, berhenti saat tab
   tersembunyi, DPR ≤ 1.5. FPS terlalu rendah → onFallback (kembali ke avatar 2D). */
import type { AgentState } from "@zoi/avatar";
import { Canvas, useFrame, useThree } from "@react-three/fiber";
import { useEffect, useRef } from "react";
import type { Group, Mesh, MeshStandardMaterial, OrthographicCamera } from "three";

import { ZONE_OF, ZONES, type ZoneId } from "./zones";

const C = { floor: "#34345a", wall: "#45457a", wood: "#8f7cc4", desk: "#5a5a8c", screen: "#8b5cf6", accent: "#a78bfa",
  booth: "#6d6ab8", sofa: "#7c5cf0", shelf: "#5d5490", plant: "#22c55e", board: "#1e1b4b" };

function Box({ p, s, c, e }: { p: [number, number, number]; s: [number, number, number]; c: string; e?: number }) {
  return (
    <mesh position={p}>
      <boxGeometry args={s} />
      <meshStandardMaterial color={c} emissive={e ? c : "#000"} emissiveIntensity={e ?? 0} flatShading />
    </mesh>
  );
}

function Plant({ p }: { p: [number, number, number] }) {
  return (
    <group position={p}>
      <Box p={[0, 0.2, 0]} s={[0.3, 0.4, 0.3]} c="#4b4b63" />
      <mesh position={[0, 0.65, 0]}><icosahedronGeometry args={[0.32, 0]} /><meshStandardMaterial color={C.plant} flatShading /></mesh>
    </group>
  );
}

/** Perabot statis per zona. */
function Office() {
  return (
    <group>
      <Box p={[0, -0.05, 0]} s={[13, 0.1, 9]} c={C.floor} />
      <Box p={[0, 0.9, -4.55]} s={[13, 1.9, 0.1]} c={C.wall} />
      <Box p={[-6.55, 0.9, 0]} s={[0.1, 1.9, 9.2]} c={C.wall} />
      {/* Hot desks */}
      {[-1.4, 0, 1.4].map((x) => (
        <group key={x} position={[x, 0, -2.6]}>
          <Box p={[0, 0.45, 0]} s={[1.1, 0.08, 0.7]} c={C.desk} />
          <Box p={[0, 0.22, 0]} s={[0.08, 0.45, 0.08]} c="#3d3d5c" />
          <Box p={[0, 0.78, -0.22]} s={[0.7, 0.42, 0.05]} c={C.screen} e={0.6} />
        </group>
      ))}
      {/* Phone booths */}
      {[-5.6, -4.4].map((x) => (
        <group key={x} position={[x, 0, -3.3]}>
          <Box p={[0, 1, 0]} s={[1, 2, 0.08]} c={C.booth} />
          <Box p={[-0.46, 1, 0.45]} s={[0.08, 2, 0.9]} c={C.booth} />
          <Box p={[0.46, 1, 0.45]} s={[0.08, 2, 0.9]} c={C.booth} />
          <Box p={[0, 2.02, 0.45]} s={[1, 0.06, 0.9]} c={C.booth} />
          <Box p={[0, 1.8, 0.05]} s={[0.4, 0.06, 0.04]} c="#22c55e" e={0.8} />
        </group>
      ))}
      {/* Meeting room */}
      <group position={[4.3, 0, -2.6]}>
        <Box p={[0, 0.45, 0.3]} s={[2.6, 0.08, 1]} c={C.wood} />
        <Box p={[0, 0.22, 0.3]} s={[0.2, 0.45, 0.6]} c="#3d3d5c" />
        <Box p={[0, 1.2, -1.85]} s={[2.2, 1, 0.06]} c="#111122" />
        <Box p={[0, 1.2, -1.81]} s={[2, 0.85, 0.02]} c="#8b5cf6" e={0.35} />
        <Box p={[-2, 0.9, -0.3]} s={[0.08, 1.8, 3.2]} c="#2a2a44" />
      </group>
      {/* Task board + printer */}
      <group position={[1.6, 0, 2.6]}>
        <Box p={[0, 1.1, -0.1]} s={[1.8, 1.2, 0.08]} c={C.board} />
        {[-0.55, 0, 0.55].map((x, i) => (
          <Box key={x} p={[x, 1.2 - i * 0.12, -0.04]} s={[0.4, 0.3, 0.02]} c={["#22d3ee", "#fbbf24", "#a78bfa"][i]} e={0.5} />
        ))}
        <Box p={[0, 0.1, -0.1]} s={[0.12, 0.2, 0.12]} c="#3d3d5c" />
        <Box p={[1.4, 0.35, 0.1]} s={[0.7, 0.7, 0.55]} c="#18181f" />
      </group>
      {/* Library corner */}
      <group position={[4.8, 0, 2.5]}>
        {[0, 1].map((i) => (
          <group key={i} position={[i * 1.1 - 0.5, 0, -1.2]}>
            <Box p={[0, 0.8, 0]} s={[1, 1.6, 0.35]} c={C.shelf} />
            {[0.35, 0.8, 1.25].map((y, j) => <Box key={y} p={[0, y, 0.1]} s={[0.85, 0.28, 0.2]} c={["#a78bfa", "#6366f1", "#22d3ee"][(i + j) % 3]} />)}
          </group>
        ))}
        <mesh position={[0.3, 0.3, 0.4]}><cylinderGeometry args={[0.35, 0.35, 0.05, 16]} /><meshStandardMaterial color={C.wood} /></mesh>
      </group>
      {/* Lounge */}
      <group position={[-4.3, 0, 2.4]}>
        <Box p={[0, 0.25, 0]} s={[2, 0.4, 0.8]} c={C.sofa} />
        <Box p={[0, 0.55, -0.35]} s={[2, 0.5, 0.15]} c={C.sofa} />
        <Box p={[0, 0.2, 1.1]} s={[0.9, 0.08, 0.6]} c={C.wood} />
      </group>
      <Plant p={[-6, 0, 0.5]} />
      <Plant p={[2.9, 0, -3.9]} />
      <Plant p={[-2.4, 0, 3.6]} />
    </group>
  );
}

/** Robot ZOI: tubuh kapsul, kepala bulat dengan visor bercahaya, antena. Melayang (tanpa kaki) agar animasi sederhana. */
function Robot({ zone, state }: { zone: ZoneId; state: AgentState }) {
  const root = useRef<Group>(null);
  const head = useRef<Group>(null);
  const visor = useRef<Mesh>(null);
  const antenna = useRef<Mesh>(null);
  const target = ZONES[zone].spot;

  useFrame(({ clock }, dt) => {
    const g = root.current;
    if (!g) return;
    const t = clock.elapsedTime;
    const dx = target[0] - g.position.x, dz = target[1] - g.position.z;
    const dist = Math.hypot(dx, dz);
    const walking = dist > 0.05;
    if (walking) {
      const step = Math.min(dist, dt * 2.4);
      g.position.x += (dx / dist) * step;
      g.position.z += (dz / dist) * step;
      g.rotation.y = Math.atan2(dx, dz);
    } else {
      const face = ZONES[zone].face;
      g.rotation.y += (face - g.rotation.y) * Math.min(1, dt * 4);
    }
    g.position.y = 0.15 + Math.sin(t * (walking ? 9 : 2)) * (walking ? 0.05 : 0.04);
    if (head.current) {
      head.current.rotation.z = state === "LISTENING" ? 0.25 : state === "THINKING" || state === "PLANNING" ? Math.sin(t * 1.5) * 0.15 : 0;
      head.current.rotation.x = state === "ANALYZING" || state === "RESEARCHING" ? 0.3 : 0;
    }
    const pulse = state === "SPEAKING" ? 0.8 + Math.abs(Math.sin(t * 12)) * 1.6
      : state === "THINKING" || state === "PLANNING" ? 0.6 + Math.sin(t * 4) * 0.4 : 0.9;
    if (visor.current) (visor.current.material as MeshStandardMaterial).emissiveIntensity = pulse;
    if (antenna.current) (antenna.current.material as MeshStandardMaterial).emissiveIntensity = 0.6 + Math.sin(t * 6) * 0.6;
  });

  const eye = state === "FAILED" ? "#f87171" : state === "COMPLETED" ? "#4ade80" : "#c4b5fd";
  return (
    <group ref={root} position={[ZONES.lounge.spot[0], 0.15, ZONES.lounge.spot[1]]}>
      <mesh position={[0, 0.55, 0]}><capsuleGeometry args={[0.28, 0.45, 4, 10]} /><meshStandardMaterial color="#e9e7ff" flatShading /></mesh>
      <mesh position={[0, 0.62, 0.22]}><boxGeometry args={[0.26, 0.22, 0.06]} /><meshStandardMaterial color="#8b5cf6" emissive="#8b5cf6" emissiveIntensity={0.7} /></mesh>
      <group ref={head} position={[0, 1.15, 0]}>
        <mesh><icosahedronGeometry args={[0.32, 1]} /><meshStandardMaterial color="#f4f3ff" flatShading /></mesh>
        <mesh ref={visor} position={[0, 0.02, 0.22]}><boxGeometry args={[0.44, 0.16, 0.14]} /><meshStandardMaterial color="#1e1b4b" emissive={eye} emissiveIntensity={0.9} /></mesh>
        <mesh position={[0, 0.38, 0]}><cylinderGeometry args={[0.02, 0.02, 0.2, 6]} /><meshStandardMaterial color="#9292a8" /></mesh>
        <mesh ref={antenna} position={[0, 0.5, 0]}><sphereGeometry args={[0.06, 8, 8]} /><meshStandardMaterial color="#a78bfa" emissive="#a78bfa" /></mesh>
      </group>
      {[-1, 1].map((side) => (
        <mesh key={side} position={[side * 0.36, 0.6, 0]} rotation={[0, 0, side * 0.25]}>
          <capsuleGeometry args={[0.07, 0.3, 3, 6]} /><meshStandardMaterial color="#d8d5f5" flatShading />
        </mesh>
      ))}
      <mesh position={[0, 0.05, 0]} rotation={[-Math.PI / 2, 0, 0]}><circleGeometry args={[0.35, 16]} /><meshBasicMaterial color="#8b5cf6" transparent opacity={0.35} /></mesh>
    </group>
  );
}

/** Kamera isometrik yang menyesuaikan zoom dengan ukuran kanvas. */
function IsoCamera() {
  const get = useThree((s) => s.get);
  const size = useThree((s) => s.size);
  useEffect(() => {
    const cam = get().camera as OrthographicCamera;
    cam.zoom = Math.max(18, Math.min(size.width / 13, size.height / 8.2));
    cam.position.set(10, 9, 10);
    cam.lookAt(0, 0, 0);
    cam.updateProjectionMatrix();
  }, [get, size]);
  return null;
}

/** Batas ±30 fps (frameloop "demand") dan pengukur FPS untuk fallback otomatis. */
function Throttle({ onSlow }: { onSlow(fps: number): void }) {
  const { invalidate } = useThree();
  const frames = useRef(0);
  useFrame(() => { frames.current += 1; });
  useEffect(() => {
    const tick = setInterval(() => { if (!document.hidden) invalidate(); }, 33);
    const started = performance.now();
    const check = setTimeout(() => {
      const fps = (frames.current * 1000) / (performance.now() - started);
      if (fps < 12) onSlow(Math.round(fps));
    }, 6000);
    return () => { clearInterval(tick); clearTimeout(check); };
  }, [invalidate, onSlow]);
  return null;
}

export interface OfficeSceneProps { state: AgentState; onFallback(reason: string): void }

export default function OfficeScene({ state, onFallback }: OfficeSceneProps) {
  const zone = ZONE_OF[state];
  return (
    <Canvas orthographic frameloop="demand" dpr={[1, 1.5]} gl={{ antialias: true, powerPreference: "low-power" }}
      camera={{ position: [10, 9, 10], near: 0.1, far: 100 }} data-testid="office-canvas"
      onCreated={({ gl }) => gl.setClearColor("#08080d", 0)}>
      <IsoCamera />
      <Throttle onSlow={(fps) => onFallback(`Kantor 3D terlalu berat untuk perangkat ini (${fps} fps) — memakai avatar 2D.`)} />
      <ambientLight intensity={1.6} />
      <directionalLight position={[6, 10, 4]} intensity={2.4} />
      <pointLight position={[0, 3, 0]} intensity={30} color="#a78bfa" distance={12} />
      <Office />
      <Robot zone={zone} state={state} />
    </Canvas>
  );
}
