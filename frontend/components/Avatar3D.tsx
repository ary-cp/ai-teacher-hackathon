"use client";

import { useEffect, useRef, useState } from "react";
import { Mic, MicOff, User } from "lucide-react";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import type { Phase } from "@/lib/types";

import { Canvas, useFrame } from "@react-three/fiber";
import { useGLTF, Environment, ContactShadows, OrbitControls } from "@react-three/drei";
import * as THREE from "three";

interface Props {
  levelRef: React.MutableRefObject<number>;
  speaking: boolean;
  muted: boolean;
  onToggleMute: () => void;
  getAudioStream: () => MediaStream | null;
  phase: Phase;
  stepTitle?: string;
}

const PHASE_LABEL: Record<Phase, string> = {
  idle: "Ready", intro: "Introducing", explain: "Teaching", question: "Asking you",
  evaluate: "Checking your answer", remediate: "Re-explaining",
  assessment: "Final quiz", report: "Feedback", done: "Done",
};

const AVATARS = [
  { id: "mr_sharma", file: "/avatar1.glb", scale: 1.2, posY: -1.5, label: "Mr. Sharma" },
  { id: "ms_pooja", file: "/avatar2.glb", scale: 1.2, posY: -1.5, label: "Ms. Pooja" },
  { id: "rahul", file: "/avatar3.glb", scale: 1.2, posY: -1.5, label: "Rahul" },
];

function Model({ levelRef, avatar }: { levelRef: React.MutableRefObject<number>, avatar: typeof AVATARS[0] }) {
  const { scene } = useGLTF(avatar.file);
  const groupRef = useRef<THREE.Group>(null);

  // No manual arm rotation, we will frame the camera tight on the face.

  useFrame(() => {
    const audioLevel = Math.min(1, levelRef.current * 3);
    let handled = false;

    scene.traverse((child: any) => {
      if (child.name === "Head") {
        child.rotation.x = Math.sin(Date.now() / 400) * 0.01 + (audioLevel * 0.03);
        handled = true;
      }
      
      if (child.isMesh && child.morphTargetDictionary) {
        const targetKeys = ["mouthOpen", "viseme_O", "jawOpen", "h_expressions.MouthOpen_h", "h_expressions.AO_a_h", "h_expressions.AE_AA_h"];
        targetKeys.forEach((key) => {
          const index = child.morphTargetDictionary[key];
          if (index !== undefined) {
            child.morphTargetInfluences[index] = THREE.MathUtils.lerp(
               child.morphTargetInfluences[index],
               audioLevel * 0.15, // lowered to 0.15 to completely prevent gaping jaw
               0.5
            );
            handled = true;
          }
        });
      }
    });

    if (!handled && groupRef.current) {
       groupRef.current.scale.y = avatar.scale + (audioLevel * 0.03);
    } else if (groupRef.current) {
       groupRef.current.scale.y = avatar.scale;
    }
  });

  return (
    <group ref={groupRef} position={[0, avatar.posY, 0]} scale={avatar.scale}>
      <primitive object={scene} />
    </group>
  );
}

export function Avatar3D({
  levelRef, speaking, muted, onToggleMute, getAudioStream, phase, stepTitle,
}: Props) {
  const [activeAvatarIndex, setActiveAvatarIndex] = useState(0);
  const avatar = AVATARS[activeAvatarIndex];
  
  useEffect(() => {
    localStorage.setItem("ai_teacher_id", avatar.id);
  }, [avatar.id]);

  return (
    <div className="relative overflow-hidden rounded-xl border shadow-sm w-full h-full min-h-[420px] bg-slate-950 dark:bg-black">
      <div className="absolute inset-0 bg-[radial-gradient(ellipse_at_center,_var(--tw-gradient-stops))] from-indigo-900/40 via-background to-background" />
      
      <Canvas camera={{ position: [0, 0.55, 1.0], fov: 35 }}>
        <ambientLight intensity={0.5} />
        <directionalLight position={[10, 10, 5]} intensity={1.5} />
        <Environment preset="city" />
        <OrbitControls target={[0, 0.5, 0]} enableZoom={false} enablePan={false} maxPolarAngle={Math.PI / 2 + 0.1} minPolarAngle={Math.PI / 2 - 0.2} />
        <Model key={avatar.id} levelRef={levelRef} avatar={avatar} />
        <ContactShadows opacity={0.5} scale={10} blur={2} far={4} color="#1e1b4b" />
      </Canvas>
      
      <div className="absolute left-4 top-4 flex gap-2 z-10">
        <Badge variant={speaking ? "success" : "secondary"} className="shadow-sm">
          {speaking ? "speaking" : PHASE_LABEL[phase]}
        </Badge>
      </div>
      
      <div className="absolute right-4 top-4 flex gap-2 z-10">
        {AVATARS.map((a, i) => (
          <Button 
            key={a.id} 
            size="sm" 
            variant={i === activeAvatarIndex ? "default" : "secondary"} 
            onClick={() => setActiveAvatarIndex(i)}
            title={`Switch to ${a.label}`}
            className="hidden md:flex"
          >
            <User className="h-4 w-4 mr-1" /> {a.label}
          </Button>
        ))}
        <Button size="icon" variant="secondary" onClick={onToggleMute} title="Mute voice">
          {muted ? <MicOff className="h-4 w-4" /> : <Mic className="h-4 w-4" />}
        </Button>
      </div>

      <div className="absolute bottom-0 w-full h-[46px] bg-black/50 backdrop-blur-sm flex items-center justify-center text-white/90 font-medium text-sm z-10 border-t border-white/10">
        {(stepTitle || "AI Teacher").slice(0, 52)}
      </div>
    </div>
  );
}

AVATARS.forEach(a => useGLTF.preload(a.file));
