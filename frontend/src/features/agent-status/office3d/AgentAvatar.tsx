import React, { useRef, useState } from 'react';
import { useFrame } from '@react-three/fiber';
import { Html } from '@react-three/drei';
import type { Group, Mesh } from 'three';
import type { AgentOfficeViewModel } from '../../../shared/api/types';

interface AgentAvatarProps {
  agent: AgentOfficeViewModel;
  index: number;
  position: [number, number, number];
  rotationY?: number;
  isSelected?: boolean;
  socializeMode?: boolean;
  onClick?: () => void;
}

// Distinct character appearance profiles by archetype
function getCharacterAppearance(archetype?: string, index = 0) {
  switch (archetype) {
    case 'pi':
      return {
        coatColor: '#1e3a8a', // Royal Navy Academic Blazer
        shirtColor: '#f8fafc',
        tieColor: '#f59e0b', // Gold tie
        pantsColor: '#1e293b',
        skinColor: '#f1c27d',
        hairColor: '#cbd5e1', // Distinguished silver hair
        eyewear: 'gold_glasses' as const,
        hat: 'none' as const,
      };
    case 'feynman':
      return {
        coatColor: '#78350f', // Warm Oxford Tweed Jacket
        shirtColor: '#fef3c7',
        tieColor: '#10b981', // Emerald tie
        pantsColor: '#3f3f46',
        skinColor: '#ffdbac',
        hairColor: '#451a03',
        eyewear: 'round_glasses' as const,
        hat: 'beret' as const,
      };
    case 'openscience':
      return {
        coatColor: '#ffffff', // Crisp White Lab Coat
        shirtColor: '#06b6d4',
        tieColor: '#0284c7',
        pantsColor: '#334155',
        skinColor: '#e0ac69',
        hairColor: '#1c1917',
        eyewear: 'safety_goggles' as const,
        hat: 'none' as const,
      };
    case 'opencode':
      return {
        coatColor: '#065f46', // Emerald Tech Hoodie
        shirtColor: '#10b981',
        tieColor: '#34d399',
        pantsColor: '#0f172a',
        skinColor: '#f1c27d',
        hairColor: '#09090b',
        eyewear: 'cyber_visor' as const,
        hat: 'headphones' as const,
      };
    case 'reviewer':
      return {
        coatColor: '#7f1d1d', // Burgundy Senior Reviewer Suit
        shirtColor: '#f8fafc',
        tieColor: '#fbbf24',
        pantsColor: '#18181b',
        skinColor: '#c68642',
        hairColor: '#27272a',
        eyewear: 'gold_glasses' as const,
        hat: 'none' as const,
      };
    case 'figure_fellow':
      return {
        coatColor: '#5b21b6', // Creative Violet Studio Vest
        shirtColor: '#ddd6fe',
        tieColor: '#ec4899',
        pantsColor: '#1e1b4b',
        skinColor: '#ffdbac',
        hairColor: '#9a3412',
        eyewear: 'round_glasses' as const,
        hat: 'beret' as const,
      };
    default: {
      const palette = ['#047857', '#0369a1', '#4338ca', '#b45309'];
      return {
        coatColor: palette[index % palette.length],
        shirtColor: '#f8fafc',
        tieColor: '#38bdf8',
        pantsColor: '#1e293b',
        skinColor: '#f1c27d',
        hairColor: '#27272a',
        eyewear: 'round_glasses' as const,
        hat: 'none' as const,
      };
    }
  }
}

export const AgentAvatar: React.FC<AgentAvatarProps> = ({
  agent,
  index,
  position,
  rotationY = 0,
  isSelected = false,
  socializeMode = true,
  onClick,
}) => {
  const characterRef = useRef<Group>(null);
  const headRef = useRef<Group>(null);
  const leftArmRef = useRef<Mesh>(null);
  const rightArmRef = useRef<Mesh>(null);
  const leftLegRef = useRef<Mesh>(null);
  const rightLegRef = useRef<Mesh>(null);
  const haloRef = useRef<Mesh>(null);
  const [hovered, setHovered] = useState(false);
  const [isTalkingNow, setIsTalkingNow] = useState(false);

  const isRunning = agent.presence === 'running';
  const isWaiting = agent.presence === 'awaiting_approval';
  const isFailed = agent.presence === 'failed';

  const appearance = getCharacterAppearance(agent.archetype, index);

  // Social meeting spots in world space (central green collaboration hub)
  const meetingAngle = (index * Math.PI * 2) / 6;
  const worldMeetX = Math.cos(meetingAngle) * 1.45;
  const worldMeetZ = -1.2 + Math.sin(meetingAngle) * 1.45;

  // Convert world meeting point to local offset relative to this station's position & rotation
  const dxWorld = worldMeetX - position[0];
  const dzWorld = worldMeetZ - position[2];
  const cosR = Math.cos(-rotationY);
  const sinR = Math.sin(-rotationY);
  const localMeetX = dxWorld * cosR - dzWorld * sinR;
  const localMeetZ = dxWorld * sinR + dzWorld * cosR;

  useFrame((state) => {
    const t = state.clock.elapsedTime;
    const phaseOffset = index * 1.7;

    if (haloRef.current) {
      haloRef.current.rotation.z = t * 0.9;
    }

    if (!characterRef.current) return;

    // Determine whether character is walking/socializing or working at desk
    // In socializeMode, agents alternate between working at their desk and walking to the central hub to discuss
    const cycle = (t * 0.22 + phaseOffset) % 12; // 12-second smooth cycle
    let walkFactor = 0; // 0 = at desk, 1 = at central discussion circle
    let isMoving = false;

    if (socializeMode) {
      if (cycle < 3.5) {
        // Working at desk
        walkFactor = 0;
        isMoving = false;
      } else if (cycle < 5.5) {
        // Walking from desk to central discussion hub
        walkFactor = (cycle - 3.5) / 2.0;
        isMoving = true;
      } else if (cycle < 9.5) {
        // Conversing with colleagues at central hub
        walkFactor = 1;
        isMoving = false;
      } else if (cycle < 11.5) {
        // Walking back to desk
        walkFactor = 1 - (cycle - 9.5) / 2.0;
        isMoving = true;
      } else {
        walkFactor = 0;
        isMoving = false;
      }
    }

    // Smooth step interpolation
    const smooth = walkFactor * walkFactor * (3 - 2 * walkFactor);
    const homeX = 0;
    const homeZ = 0.58;

    const curX = homeX + (localMeetX - homeX) * smooth;
    const curZ = homeZ + (localMeetZ - homeZ) * smooth;

    characterRef.current.position.x = curX;
    characterRef.current.position.z = curZ;

    // Bobbing height when walking
    characterRef.current.position.y = isMoving ? Math.abs(Math.sin(t * 9)) * 0.045 : 0;

    // Face direction of movement or face center when conversing
    if (isMoving) {
      const dirX = localMeetX - homeX;
      const dirZ = localMeetZ - homeZ;
      const targetRot =
        cycle < 6 ? Math.atan2(dirX, dirZ) : Math.atan2(-dirX, -dirZ);
      characterRef.current.rotation.y = targetRot;
    } else if (smooth > 0.8) {
      // Face toward the center of the discussion circle (world [0, -1.2])
      const toCenterX = -localMeetX;
      const toCenterZ = -localMeetZ;
      characterRef.current.rotation.y = Math.atan2(toCenterX, toCenterZ);
    } else {
      // Face desk monitors (-Z in local space -> rotation.y = Math.PI)
      characterRef.current.rotation.y = Math.PI;
    }

    const conversing = smooth > 0.75 || isRunning;
    if (conversing !== isTalkingNow && Math.floor(t * 2) % 2 === 0) {
      setIsTalkingNow(conversing);
    }

    // Leg swing animation
    if (leftLegRef.current && rightLegRef.current) {
      if (isMoving) {
        leftLegRef.current.rotation.x = Math.sin(t * 9) * 0.55;
        rightLegRef.current.rotation.x = -Math.sin(t * 9) * 0.55;
      } else {
        leftLegRef.current.rotation.x = 0;
        rightLegRef.current.rotation.x = 0;
      }
    }

    // Arm gesture / typing animation
    if (leftArmRef.current && rightArmRef.current) {
      if (isMoving) {
        leftArmRef.current.rotation.x = -Math.sin(t * 9) * 0.45;
        rightArmRef.current.rotation.x = Math.sin(t * 9) * 0.45;
      } else if (smooth > 0.75) {
        // Expressive conversation hand gestures
        leftArmRef.current.rotation.x = -0.45 + Math.sin(t * 5 + index) * 0.25;
        rightArmRef.current.rotation.x = -0.35 + Math.cos(t * 4.5 + index) * 0.25;
      } else if (isRunning) {
        // Fast keyboard typing
        leftArmRef.current.rotation.x = -0.65 + Math.sin(t * 12) * 0.09;
        rightArmRef.current.rotation.x = -0.65 + Math.cos(t * 12) * 0.09;
      } else {
        leftArmRef.current.rotation.x = -0.35;
        rightArmRef.current.rotation.x = -0.35;
      }
    }

    // Head nod & look around when conversing
    if (headRef.current) {
      if (smooth > 0.75 || isRunning) {
        headRef.current.rotation.y = Math.sin(t * 2.2 + index) * 0.24;
        headRef.current.rotation.x = Math.sin(t * 4.5 + index) * 0.08;
      } else {
        headRef.current.rotation.y = Math.sin(t * 0.6 + index) * 0.08;
        headRef.current.rotation.x = 0;
      }
    }
  });

  // Status color palette
  let statusColor = '#10b981'; // bright green active feel
  let screenGlow = '#059669';
  let statusLabel: string = agent.activity || 'Ready';

  if (isRunning) {
    statusColor = '#10b981';
    screenGlow = '#10b981';
    statusLabel = `Active · ${agent.activity}`;
  } else if (isWaiting) {
    statusColor = '#f59e0b';
    screenGlow = '#d97706';
    statusLabel = 'Awaiting Approval';
  } else if (isFailed) {
    statusColor = '#ef4444';
    screenGlow = '#dc2626';
    statusLabel = 'Attention Needed';
  } else {
    statusColor = '#22c55e';
    screenGlow = '#0284c7';
  }

  return (
    <group
      position={position}
      rotation={[0, rotationY, 0]}
      onClick={(e) => {
        e.stopPropagation();
        onClick?.();
      }}
      onPointerOver={(e) => {
        e.stopPropagation();
        setHovered(true);
        document.body.style.cursor = 'pointer';
      }}
      onPointerOut={() => {
        setHovered(false);
        document.body.style.cursor = 'default';
      }}
    >
      {/* ── Workstation Desk (Natural Light Oak + White Steel for Bright Biophilic Lab) ── */}
      <mesh position={[0, 0.74, 0]} castShadow receiveShadow>
        <boxGeometry args={[1.8, 0.06, 0.88]} />
        <meshStandardMaterial color="#d4a373" roughness={0.45} metalness={0.05} />
      </mesh>
      {/* Desk Legs */}
      {[
        [-0.82, 0.37, -0.35],
        [0.82, 0.37, -0.35],
        [-0.82, 0.37, 0.35],
        [0.82, 0.37, 0.35],
      ].map(([lx, ly, lz], i) => (
        <mesh key={i} position={[lx, ly, lz]} castShadow>
          <boxGeometry args={[0.06, 0.74, 0.06]} />
          <meshStandardMaterial color="#e2e8f0" metalness={0.5} roughness={0.3} />
        </mesh>
      ))}

      {/* Small Potted Green Succulent on every Desk */}
      <group position={[-0.7, 0.79, -0.22]}>
        <mesh position={[0, 0.04, 0]}>
          <cylinderGeometry args={[0.06, 0.05, 0.09, 12]} />
          <meshStandardMaterial color="#f8fafc" roughness={0.3} />
        </mesh>
        <mesh position={[0, 0.12, 0]}>
          <sphereGeometry args={[0.075, 12, 12]} />
          <meshStandardMaterial color="#16a34a" roughness={0.6} />
        </mesh>
      </group>

      {/* Dual Curved Monitors */}
      <group position={[-0.3, 1.06, -0.2]} rotation={[0, 0.16, 0]}>
        <mesh castShadow>
          <boxGeometry args={[0.58, 0.36, 0.03]} />
          <meshStandardMaterial color="#1e293b" roughness={0.4} />
        </mesh>
        <mesh position={[0, 0, 0.018]}>
          <planeGeometry args={[0.54, 0.32]} />
          <meshStandardMaterial
            color={screenGlow}
            emissive={screenGlow}
            emissiveIntensity={isRunning ? 0.85 : 0.35}
          />
        </mesh>
      </group>

      <group position={[0.3, 1.06, -0.2]} rotation={[0, -0.16, 0]}>
        <mesh castShadow>
          <boxGeometry args={[0.58, 0.36, 0.03]} />
          <meshStandardMaterial color="#1e293b" roughness={0.4} />
        </mesh>
        <mesh position={[0, 0, 0.018]}>
          <planeGeometry args={[0.54, 0.32]} />
          <meshStandardMaterial
            color="#0ea5e9"
            emissive="#0284c7"
            emissiveIntensity={0.45}
          />
        </mesh>
      </group>

      {/* Ergonomic Mesh Chair */}
      <group position={[0, 0, 0.74]}>
        <mesh position={[0, 0.22, 0]}>
          <cylinderGeometry args={[0.04, 0.04, 0.42, 10]} />
          <meshStandardMaterial color="#64748b" metalness={0.6} />
        </mesh>
        <mesh position={[0, 0.44, 0]} castShadow>
          <boxGeometry args={[0.48, 0.06, 0.46]} />
          <meshStandardMaterial color="#334155" roughness={0.7} />
        </mesh>
        <mesh position={[0, 0.8, 0.21]} rotation={[-0.08, 0, 0]} castShadow>
          <boxGeometry args={[0.44, 0.68, 0.06]} />
          <meshStandardMaterial color="#0f766e" roughness={0.6} />
        </mesh>
      </group>

      {/* ── Articulated Walking & Conversing 3D Researcher Character ── */}
      <group ref={characterRef} position={[0, 0, 0.58]} rotation={[0, Math.PI, 0]}>
        {/* Selection / Active Floor Ring under Character */}
        {(isSelected || hovered || isRunning) && (
          <mesh ref={haloRef} rotation={[-Math.PI / 2, 0, 0]} position={[0, 0.02, 0]}>
            <ringGeometry args={[0.45, 0.56, 32]} />
            <meshBasicMaterial
              color={isSelected ? '#f97316' : statusColor}
              transparent
              opacity={isSelected || hovered ? 0.95 : 0.55}
            />
          </mesh>
        )}

        {/* Left & Right Articulated Legs */}
        <mesh ref={leftLegRef} position={[-0.11, 0.32, 0]} castShadow>
          <boxGeometry args={[0.13, 0.56, 0.14]} />
          <meshStandardMaterial color={appearance.pantsColor} roughness={0.7} />
        </mesh>
        <mesh ref={rightLegRef} position={[0.11, 0.32, 0]} castShadow>
          <boxGeometry args={[0.13, 0.56, 0.14]} />
          <meshStandardMaterial color={appearance.pantsColor} roughness={0.7} />
        </mesh>

        {/* Torso (Role-specific Outfit) */}
        <mesh position={[0, 0.84, 0]} castShadow>
          <boxGeometry args={[0.42, 0.54, 0.24]} />
          <meshStandardMaterial color={appearance.coatColor} roughness={0.55} />
        </mesh>
        {/* Inner Shirt / Collar */}
        <mesh position={[0, 0.94, 0.125]}>
          <boxGeometry args={[0.18, 0.28, 0.015]} />
          <meshStandardMaterial color={appearance.shirtColor} />
        </mesh>
        {/* Tie / Lanyard Badge */}
        <mesh position={[0, 0.88, 0.135]}>
          <boxGeometry args={[0.06, 0.24, 0.015]} />
          <meshStandardMaterial color={appearance.tieColor} />
        </mesh>

        {/* Left & Right Articulated Arms */}
        <mesh ref={leftArmRef} position={[-0.27, 0.84, 0.05]} castShadow>
          <boxGeometry args={[0.11, 0.42, 0.11]} />
          <meshStandardMaterial color={appearance.coatColor} roughness={0.55} />
        </mesh>
        <mesh ref={rightArmRef} position={[0.27, 0.84, 0.05]} castShadow>
          <boxGeometry args={[0.11, 0.42, 0.11]} />
          <meshStandardMaterial color={appearance.coatColor} roughness={0.55} />
        </mesh>

        {/* Head, Hair, & Role Eyewear */}
        <group ref={headRef} position={[0, 1.28, 0]}>
          <mesh castShadow>
            <sphereGeometry args={[0.175, 20, 20]} />
            <meshStandardMaterial color={appearance.skinColor} roughness={0.45} />
          </mesh>
          {/* Hair */}
          <mesh position={[0, 0.05, -0.02]}>
            <sphereGeometry args={[0.182, 16, 16, 0, Math.PI * 2, 0, Math.PI * 0.58]} />
            <meshStandardMaterial color={appearance.hairColor} roughness={0.8} />
          </mesh>

          {/* Optional Beret or Headphones */}
          {appearance.hat === 'beret' && (
            <mesh position={[0.02, 0.16, 0]} rotation={[0.1, 0, -0.15]}>
              <cylinderGeometry args={[0.15, 0.17, 0.06, 16]} />
              <meshStandardMaterial color={appearance.coatColor} />
            </mesh>
          )}
          {appearance.hat === 'headphones' && (
            <mesh position={[0, 0.02, 0]}>
              <torusGeometry args={[0.185, 0.025, 10, 24, Math.PI]} />
              <meshStandardMaterial color="#10b981" metalness={0.6} />
            </mesh>
          )}

          {/* Eyewear (Front of face is +Z in character local space) */}
          <mesh position={[0, 0.02, 0.16]}>
            <boxGeometry args={[0.22, 0.055, 0.03]} />
            <meshStandardMaterial
              color={
                appearance.eyewear === 'safety_goggles'
                  ? '#38bdf8'
                  : appearance.eyewear === 'cyber_visor'
                  ? '#10b981'
                  : '#fbbf24'
              }
              emissive={
                appearance.eyewear === 'cyber_visor'
                  ? '#10b981'
                  : appearance.eyewear === 'safety_goggles'
                  ? '#0284c7'
                  : '#000000'
              }
              emissiveIntensity={0.45}
              metalness={0.8}
              roughness={0.2}
            />
          </mesh>
        </group>

        {/* Floating Nameplate + Live Speech Bubble above Character */}
        <Html position={[0, 1.78, 0]} center distanceFactor={14} zIndexRange={[12, 0]}>
          <div
            onClick={(e) => {
              e.stopPropagation();
              onClick?.();
            }}
            style={{
              display: 'flex',
              flexDirection: 'column',
              alignItems: 'center',
              gap: 4,
              cursor: 'pointer',
              userSelect: 'none',
              fontFamily: 'var(--sans)',
            }}
          >
            {/* Live Speech Bubble when conversing or hovered/selected */}
            {(isTalkingNow || hovered || isSelected) && agent.speechBubble && (
              <div
                style={{
                  maxWidth: 220,
                  padding: '5px 9px',
                  borderRadius: 10,
                  background: 'rgba(255, 255, 255, 0.96)',
                  color: '#0f172a',
                  border: '1.5px solid #10b981',
                  boxShadow: '0 4px 14px rgba(0,0,0,0.18)',
                  fontSize: 10.5,
                  lineHeight: 1.35,
                  fontWeight: 500,
                  textAlign: 'center',
                }}
              >
                💬 {agent.speechBubble}
              </div>
            )}

            {/* Character Badge */}
            <div
              style={{
                background: isSelected
                  ? 'rgba(6, 78, 59, 0.96)'
                  : 'rgba(15, 23, 42, 0.88)',
                backdropFilter: 'blur(8px)',
                color: '#f8fafc',
                padding: '4px 10px',
                borderRadius: 999,
                border: `1.5px solid ${isSelected ? '#fbbf24' : statusColor}`,
                boxShadow: '0 4px 12px rgba(0,0,0,0.3)',
                whiteSpace: 'nowrap',
                transform: hovered || isSelected ? 'scale(1.08)' : 'scale(1)',
                transition: 'transform 0.15s ease',
              }}
            >
              <div
                style={{
                  display: 'flex',
                  alignItems: 'center',
                  gap: 5,
                  fontSize: 11,
                  fontWeight: 700,
                }}
              >
                <span
                  style={{
                    width: 7,
                    height: 7,
                    borderRadius: '50%',
                    background: statusColor,
                    display: 'inline-block',
                  }}
                />
                <span>{agent.displayName}</span>
                <span
                  style={{
                    fontSize: 9,
                    padding: '1px 5px',
                    borderRadius: 999,
                    background: 'rgba(16, 185, 129, 0.25)',
                    color: '#6ee7b7',
                  }}
                >
                  {agent.engine}
                </span>
              </div>
              <div style={{ fontSize: 9.5, color: '#cbd5e1', textAlign: 'center' }}>
                {statusLabel}
              </div>
            </div>
          </div>
        </Html>
      </group>
    </group>
  );
};
