import React, { useState } from 'react';
import { Html } from '@react-three/drei';
import type { AgentOfficeViewModel } from '../../../shared/api/types';
import type { InteractiveLabObjectKind } from '../../../shared/state/uiStore';
import { useI18n } from '../../../shared/state/uiStore';
import { AgentAvatar } from './AgentAvatar';
import { APP_VERSION } from '../../../shared/version';

export type LabLightingMode = 'biophilic_green' | 'daylight' | 'night_lab' | 'cyber_science';

interface OfficeSceneProps {
  agents: AgentOfficeViewModel[];
  selectedAgentId?: string | null;
  selectedLabObject?: InteractiveLabObjectKind;
  lightingMode?: LabLightingMode;
  topicTitle?: string;
  paperCount?: number;
  missionCount?: number;
  socializeMode?: boolean;
  onSelectAgent?: (agent: AgentOfficeViewModel) => void;
  onSelectLabObject?: (obj: InteractiveLabObjectKind) => void;
}

export const OfficeScene: React.FC<OfficeSceneProps> = ({
  agents,
  selectedAgentId,
  selectedLabObject,
  lightingMode = 'biophilic_green',
  topicTitle,
  paperCount = 0,
  missionCount = 0,
  socializeMode = true,
  onSelectAgent,
  onSelectLabObject,
}) => {
  const [hoveredObj, setHoveredObj] = useState<string | null>(null);
  const { t } = useI18n();

  const isGreen = lightingMode === 'biophilic_green';
  const isNight = lightingMode === 'night_lab';
  const isCyber = lightingMode === 'cyber_science';

  const floorColor = isGreen
    ? '#eef6f0'
    : isCyber
    ? '#0f172a'
    : isNight
    ? '#1e1b18'
    : '#f1ede4';
  const wallColor = isGreen
    ? '#f8fafc'
    : isCyber
    ? '#1e293b'
    : isNight
    ? '#27241f'
    : '#f8f5ee';
  const gridMainColor = isGreen
    ? '#bbf7d0'
    : isCyber
    ? '#1d4ed8'
    : isNight
    ? '#3f3a32'
    : '#d6d3cd';
  const gridSubColor = isGreen
    ? '#dcfce7'
    : isCyber
    ? '#0f2942'
    : isNight
    ? '#2b2822'
    : '#e7e5e0';

  const runningCount = agents.filter((a) => a.presence === 'running').length;

  // Deterministic ergonomic workstation coordinates inside the University Lab Hall
  const getStationTransform = (index: number): { pos: [number, number, number]; rotY: number } => {
    const presetSlots: Array<{ pos: [number, number, number]; rotY: number }> = [
      // Slot 0: PI Podium / Front Center-Left Lead Station
      { pos: [-3.2, 0, -4.4], rotY: 0 },
      // Slot 1: Literature & SKB Wing (West Wing)
      { pos: [-6.4, 0, -1.2], rotY: Math.PI / 6 },
      // Slot 2: OpenScience Lab Bench (Front Center-Right)
      { pos: [3.2, 0, -4.4], rotY: 0 },
      // Slot 3: OpenCode HPC Compute Station (South-West)
      { pos: [-3.8, 0, 2.2], rotY: 0 },
      // Slot 4: Peer Review & Verification Station (South-East)
      { pos: [3.8, 0, 2.2], rotY: 0 },
      // Slot 5: Figure Studio & LaTeX Station (East Wing)
      { pos: [6.4, 0, -1.2], rotY: -Math.PI / 6 },
      // Slot 6+: Additional Parallel Mission Stations
      { pos: [-4.5, 0, 5.4], rotY: 0 },
      { pos: [0, 0, 5.4], rotY: 0 },
      { pos: [4.5, 0, 5.4], rotY: 0 },
    ];
    if (index < presetSlots.length) {
      return presetSlots[index];
    }
    const extraIdx = index - presetSlots.length;
    const row = Math.floor(extraIdx / 4);
    const col = extraIdx % 4;
    return {
      pos: [(col - 1.5) * 3.8, 0, 7.6 + row * 3.4],
      rotY: 0,
    };
  };

  return (
    <>
      {/* ── Bright Biophilic Natural Lighting ── */}
      <ambientLight
        intensity={isGreen ? 1.15 : isCyber ? 0.6 : isNight ? 0.65 : 1.05}
        color={isGreen ? '#f0fdf4' : isCyber ? '#93c5fd' : isNight ? '#fde68a' : '#ffffff'}
      />
      <directionalLight
        position={[10, 20, 12]}
        intensity={isGreen ? 1.55 : isCyber ? 0.85 : isNight ? 0.8 : 1.4}
        color={isGreen ? '#ffffff' : isCyber ? '#60a5fa' : isNight ? '#fed7aa' : '#fffbeb'}
        castShadow
      />
      {/* Skylight Sunbeams */}
      <pointLight position={[0, 6.5, -1.2]} intensity={1.1} color="#34d399" distance={18} />
      <pointLight position={[-8, 4.5, -1]} intensity={0.9} color="#fbbf24" distance={14} />
      <pointLight position={[8, 4.5, -1]} intensity={0.9} color="#38bdf8" distance={14} />

      {/* ── Main University Laboratory Floor (28m x 22m) ── */}
      <mesh rotation={[-Math.PI / 2, 0, 0]} position={[0, 0, 0]} receiveShadow>
        <planeGeometry args={[28, 22]} />
        <meshStandardMaterial color={floorColor} roughness={0.6} metalness={0.04} />
      </mesh>

      <gridHelper args={[28, 28, gridMainColor, gridSubColor]} position={[0, 0.01, 0]} />

      {/* ── Central Biophilic Green Collaboration Courtyard & Discussion Hub (World [0, 0, -1.2]) ── */}
      <group position={[0, 0.02, -1.2]}>
        {/* Circular Moss Green Courtyard Carpet */}
        <mesh rotation={[-Math.PI / 2, 0, 0]} receiveShadow>
          <circleGeometry args={[2.8, 48]} />
          <meshStandardMaterial
            color={isGreen || !isNight ? '#bbf7d0' : '#064e3b'}
            roughness={0.85}
          />
        </mesh>
        {/* Inner Wood Trim Ring */}
        <mesh rotation={[-Math.PI / 2, 0, 0.01]} position={[0, 0.01, 0]}>
          <ringGeometry args={[2.68, 2.82, 48]} />
          <meshStandardMaterial color="#10b981" />
        </mesh>
        {/* Central Collaboration Coffee & Bonsai Table where Agents Meet to Converse */}
        <mesh position={[0, 0.52, 0]} castShadow>
          <cylinderGeometry args={[0.75, 0.75, 0.05, 32]} />
          <meshStandardMaterial color="#f8fafc" roughness={0.25} />
        </mesh>
        <mesh position={[0, 0.26, 0]}>
          <cylinderGeometry args={[0.14, 0.28, 0.52, 16]} />
          <meshStandardMaterial color="#10b981" metalness={0.4} />
        </mesh>
        {/* Center Bonsai Tree in Collaboration Hub */}
        <mesh position={[0, 0.62, 0]}>
          <cylinderGeometry args={[0.16, 0.12, 0.14, 16]} />
          <meshStandardMaterial color="#78350f" />
        </mesh>
        <mesh position={[0, 0.88, 0]} castShadow>
          <sphereGeometry args={[0.28, 16, 16]} />
          <meshStandardMaterial color="#16a34a" roughness={0.6} />
        </mesh>
      </group>

      {/* ── Architectural Back Wall (North) with Vertical Living Green Walls ── */}
      <mesh position={[0, 2.8, -10.2]} receiveShadow>
        <boxGeometry args={[28, 5.6, 0.35]} />
        <meshStandardMaterial color={wallColor} roughness={0.7} />
      </mesh>

      {/* Left & Right Vertical Biophilic Living Green Plant Walls on North Wall */}
      {[-8.2, 8.2].map((xWall, idx) => (
        <group key={`green-wall-${idx}`} position={[xWall, 2.7, -9.95]}>
          <mesh castShadow>
            <boxGeometry args={[4.4, 4.2, 0.14]} />
            <meshStandardMaterial color="#14532d" roughness={0.8} />
          </mesh>
          <mesh position={[0, 0, 0.09]}>
            <boxGeometry args={[4.1, 3.9, 0.08]} />
            <meshStandardMaterial color="#16a34a" roughness={0.9} />
          </mesh>
        </group>
      ))}

      {/* West Wall (Library Wing) */}
      <mesh position={[-13.8, 2.8, 0]} receiveShadow>
        <boxGeometry args={[0.35, 5.6, 22]} />
        <meshStandardMaterial color={wallColor} roughness={0.75} />
      </mesh>

      {/* East Panoramic Botanical Glass Wall */}
      <mesh position={[13.8, 1.0, 0]} receiveShadow>
        <boxGeometry args={[0.3, 2.0, 22]} />
        <meshStandardMaterial color={wallColor} roughness={0.75} />
      </mesh>
      <mesh position={[13.75, 3.5, 0]}>
        <boxGeometry args={[0.08, 3.0, 20]} />
        <meshStandardMaterial
          color="#a7f3d0"
          emissive="#10b981"
          emissiveIntensity={0.18}
          transparent
          opacity={0.38}
        />
      </mesh>

      {/* ── ZONE 1: PhD Research Lab Brand Monument & Interactive PI Smart Chalkboard (`outline`) ── */}
      <group
        position={[0, 0, -8.8]}
        onClick={(e) => {
          e.stopPropagation();
          onSelectLabObject?.('outline');
        }}
        onPointerOver={(e) => {
          e.stopPropagation();
          setHoveredObj('outline');
          document.body.style.cursor = 'pointer';
        }}
        onPointerOut={() => {
          setHoveredObj(null);
          document.body.style.cursor = 'default';
        }}
      >
        {/* Raised Oak Stage Platform */}
        <mesh position={[0, 0.12, 0.4]} receiveShadow castShadow>
          <boxGeometry args={[10.2, 0.24, 2.6]} />
          <meshStandardMaterial color="#b45309" roughness={0.5} />
        </mesh>

        {/* Panoramic Smart Board Frame */}
        <mesh position={[0, 2.65, -0.95]} castShadow>
          <boxGeometry args={[9.2, 3.1, 0.14]} />
          <meshStandardMaterial
            color={selectedLabObject === 'outline' || hoveredObj === 'outline' ? '#10b981' : '#064e3b'}
            roughness={0.3}
            metalness={0.3}
          />
        </mesh>
        <mesh position={[0, 2.65, -0.86]}>
          <planeGeometry args={[8.8, 2.8]} />
          <meshStandardMaterial
            color="#062c22"
            emissive="#059669"
            emissiveIntensity={0.25}
            roughness={0.25}
          />
        </mesh>

        {/* Prominent PhD Research Lab Brand & Logo + Interactive Outline Trigger */}
        <Html position={[0, 2.7, -0.8]} transform distanceFactor={10.5} zIndexRange={[5, 0]}>
          <div
            onClick={(e) => {
              e.stopPropagation();
              onSelectLabObject?.('outline');
            }}
            style={{
              width: 610,
              padding: '14px 22px',
              background: 'linear-gradient(135deg, rgba(6, 78, 59, 0.96) 0%, rgba(15, 23, 42, 0.95) 100%)',
              border: `2px solid ${
                selectedLabObject === 'outline' || hoveredObj === 'outline'
                  ? '#fbbf24'
                  : '#10b981'
              }`,
              borderRadius: 14,
              color: '#f8fafc',
              fontFamily: 'var(--sans)',
              cursor: 'pointer',
              boxShadow: '0 10px 30px rgba(0,0,0,0.35)',
              display: 'flex',
              alignItems: 'center',
              justifyContent: 'space-between',
              gap: 16,
            }}
          >
            <div style={{ display: 'flex', alignItems: 'center', gap: 14 }}>
              <img
                src="/img/logo-64.png"
                alt="PhD Research Lab Logo"
                width={52}
                height={52}
                style={{
                  borderRadius: 12,
                  border: '2px solid #34d399',
                  background: '#ffffff',
                  padding: 3,
                }}
              />
              <div style={{ textAlign: 'left' }}>
                <div
                  style={{
                    fontSize: 10.5,
                    letterSpacing: '0.12em',
                    textTransform: 'uppercase',
                    color: '#6ee7b7',
                    fontWeight: 700,
                  }}
                >
                  OpenScience Autonomous University Lab · v{APP_VERSION}
                </div>
                <div style={{ fontSize: 20, fontWeight: 800, color: '#ffffff', letterSpacing: '-0.02em' }}>
                  PhD Research Lab
                </div>
                <div style={{ fontSize: 11.5, color: '#cbd5e1', marginTop: 2 }}>
                  {topicTitle || t('Click để mở Đề cương 5 cấp độ (Outline) & Nhiệm vụ Tự hành', 'Open the 5-level outline and autonomous missions')}
                </div>
              </div>
            </div>

            <div
              style={{
                display: 'flex',
                flexDirection: 'column',
                gap: 4,
                textAlign: 'right',
                fontSize: 11,
                background: 'rgba(255,255,255,0.08)',
                padding: '8px 12px',
                borderRadius: 10,
                border: '1px solid rgba(52, 211, 153, 0.35)',
              }}
            >
              <span>
                📚 Papers: <b style={{ color: '#6ee7b7' }}>{paperCount}</b>
              </span>
              <span>
                🚀 Missions: <b style={{ color: '#38bdf8' }}>{missionCount}</b>
              </span>
              <span>
                🤖 Active Agents: <b style={{ color: '#fbbf24' }}>{runningCount}/{agents.length}</b>
              </span>
              <span style={{ fontSize: 10, color: '#a7f3d0', fontWeight: 700 }}>
                {t('[Click: Xem Đề cương & Missions]', '[Open Outline & Missions]')}
              </span>
            </div>
          </div>
        </Html>
      </group>

      {/* ── ZONE 2: Interactive Library Bookshelves (`library` - West Wall) ── */}
      <group
        position={[-12.6, 0, -0.5]}
        onClick={(e) => {
          e.stopPropagation();
          onSelectLabObject?.('library');
        }}
        onPointerOver={(e) => {
          e.stopPropagation();
          setHoveredObj('library');
          document.body.style.cursor = 'pointer';
        }}
        onPointerOut={() => {
          setHoveredObj(null);
          document.body.style.cursor = 'default';
        }}
      >
        {[-4.5, -1.5, 1.5, 4.5].map((zPos, i) => (
          <group key={`bookshelf-${i}`} position={[0, 0, zPos]}>
            <mesh position={[0, 1.85, 0]} castShadow receiveShadow>
              <boxGeometry args={[0.8, 3.7, 2.3]} />
              <meshStandardMaterial
                color={
                  selectedLabObject === 'library' || hoveredObj === 'library'
                    ? '#047857'
                    : '#78350f'
                }
                roughness={0.55}
              />
            </mesh>
            {[0.6, 1.2, 1.8, 2.4, 3.0].map((yShelf, sIdx) => (
              <mesh key={sIdx} position={[0.24, yShelf, 0]}>
                <boxGeometry args={[0.38, 0.36, 2.0]} />
                <meshStandardMaterial
                  color={
                    ['#10b981', '#0284c7', '#f59e0b', '#8b5cf6', '#ec4899'][
                      (i + sIdx) % 5
                    ]
                  }
                  roughness={0.45}
                />
              </mesh>
            ))}
          </group>
        ))}

        {/* Floating Interactive Library Label */}
        <Html position={[0.8, 3.9, 0]} center distanceFactor={15} zIndexRange={[8, 0]}>
          <div
            onClick={(e) => {
              e.stopPropagation();
              onSelectLabObject?.('library');
            }}
            style={{
              padding: '6px 12px',
              borderRadius: 999,
              background:
                selectedLabObject === 'library'
                  ? 'rgba(5, 150, 105, 0.96)'
                  : 'rgba(15, 23, 42, 0.88)',
              color: '#ffffff',
              border: '1.5px solid #10b981',
              fontSize: 11.5,
              fontWeight: 700,
              whiteSpace: 'nowrap',
              cursor: 'pointer',
              boxShadow: '0 4px 14px rgba(0,0,0,0.3)',
            }}
          >
            {t(`📚 Thư viện SKB (${paperCount} bài báo) · Click để tra cứu`, `📚 SKB Library (${paperCount} papers) · Browse references`)}
          </div>
        </Html>
      </group>

      {/* ── ZONE 3: Interactive HPC GPU & OpenCode Cluster (`hpc_opencode` - North-West Corner) ── */}
      <group
        position={[-9.6, 0, -7.8]}
        onClick={(e) => {
          e.stopPropagation();
          onSelectLabObject?.('hpc_opencode');
        }}
        onPointerOver={(e) => {
          e.stopPropagation();
          setHoveredObj('hpc_opencode');
          document.body.style.cursor = 'pointer';
        }}
        onPointerOut={() => {
          setHoveredObj(null);
          document.body.style.cursor = 'default';
        }}
      >
        {[-1.6, -0.5, 0.6, 1.7].map((xOff, rIdx) => (
          <group key={`rack-${rIdx}`} position={[xOff, 0, 0]}>
            <mesh position={[0, 1.5, 0]} castShadow>
              <boxGeometry args={[0.92, 3.0, 1.1]} />
              <meshStandardMaterial
                color={
                  selectedLabObject === 'hpc_opencode' || hoveredObj === 'hpc_opencode'
                    ? '#065f46'
                    : '#1e293b'
                }
                metalness={0.7}
                roughness={0.25}
              />
            </mesh>
            {[0.6, 1.1, 1.6, 2.1, 2.6].map((yLed, lIdx) => (
              <mesh key={lIdx} position={[0, yLed, 0.56]}>
                <planeGeometry args={[0.7, 0.08]} />
                <meshStandardMaterial
                  color="#10b981"
                  emissive="#10b981"
                  emissiveIntensity={0.95}
                />
              </mesh>
            ))}
          </group>
        ))}

        <Html position={[0, 3.4, 0.4]} center distanceFactor={15} zIndexRange={[8, 0]}>
          <div
            onClick={(e) => {
              e.stopPropagation();
              onSelectLabObject?.('hpc_opencode');
            }}
            style={{
              padding: '6px 12px',
              borderRadius: 999,
              background:
                selectedLabObject === 'hpc_opencode'
                  ? 'rgba(5, 150, 105, 0.96)'
                  : 'rgba(15, 23, 42, 0.88)',
              color: '#ffffff',
              border: '1.5px solid #38bdf8',
              fontSize: 11.5,
              fontWeight: 700,
              whiteSpace: 'nowrap',
              cursor: 'pointer',
              boxShadow: '0 4px 14px rgba(0,0,0,0.3)',
            }}
          >
            {t('🖥️ Cụm HPC & OpenCode Parallel · Click mở Runtime', '🖥️ HPC & OpenCode Parallel · Open Runtime')}
          </div>
        </Html>
      </group>

      {/* ── ZONE 4: Interactive Peer Review Roundtable (`roundtable_review` - East Wing) ── */}
      <group
        position={[9.5, 0, 2.8]}
        onClick={(e) => {
          e.stopPropagation();
          onSelectLabObject?.('roundtable_review');
        }}
        onPointerOver={(e) => {
          e.stopPropagation();
          setHoveredObj('roundtable_review');
          document.body.style.cursor = 'pointer';
        }}
        onPointerOut={() => {
          setHoveredObj(null);
          document.body.style.cursor = 'default';
        }}
      >
        <mesh position={[0, 0.74, 0]} castShadow receiveShadow>
          <cylinderGeometry args={[1.75, 1.75, 0.08, 32]} />
          <meshStandardMaterial
            color={
              selectedLabObject === 'roundtable_review' || hoveredObj === 'roundtable_review'
                ? '#10b981'
                : '#d4a373'
            }
            roughness={0.4}
          />
        </mesh>
        <mesh position={[0, 0.36, 0]}>
          <cylinderGeometry args={[0.25, 0.45, 0.72, 16]} />
          <meshStandardMaterial color="#334155" metalness={0.5} />
        </mesh>
        {/* Glass Whiteboard */}
        <mesh position={[2.2, 1.65, 0]} rotation={[0, -Math.PI / 2, 0]}>
          <boxGeometry args={[2.9, 1.6, 0.06]} />
          <meshStandardMaterial
            color="#d1fae5"
            emissive="#10b981"
            emissiveIntensity={0.22}
            transparent
            opacity={0.8}
          />
        </mesh>

        <Html position={[0, 2.2, 0]} center distanceFactor={15} zIndexRange={[8, 0]}>
          <div
            onClick={(e) => {
              e.stopPropagation();
              onSelectLabObject?.('roundtable_review');
            }}
            style={{
              padding: '6px 12px',
              borderRadius: 999,
              background:
                selectedLabObject === 'roundtable_review'
                  ? 'rgba(5, 150, 105, 0.96)'
                  : 'rgba(15, 23, 42, 0.88)',
              color: '#ffffff',
              border: '1.5px solid #ec4899',
              fontSize: 11.5,
              fontWeight: 700,
              whiteSpace: 'nowrap',
              cursor: 'pointer',
              boxShadow: '0 4px 14px rgba(0,0,0,0.3)',
            }}
          >
            {t('🏆 Bàn Hội đồng Bình duyệt R1–R3 · Click mở Review', '🏆 R1–R3 Peer Review Table · Open Review')}
          </div>
        </Html>
      </group>

      {/* ── ZONE 5: Interactive Figure Studio Hologram Table (`figure_studio` - North-East Wing) ── */}
      <group
        position={[9.5, 0, -4.6]}
        onClick={(e) => {
          e.stopPropagation();
          onSelectLabObject?.('figure_studio');
        }}
        onPointerOver={(e) => {
          e.stopPropagation();
          setHoveredObj('figure_studio');
          document.body.style.cursor = 'pointer';
        }}
        onPointerOut={() => {
          setHoveredObj(null);
          document.body.style.cursor = 'default';
        }}
      >
        <mesh position={[0, 0.82, 0]} castShadow>
          <boxGeometry args={[2.4, 0.1, 1.4]} />
          <meshStandardMaterial color="#1e293b" metalness={0.5} />
        </mesh>
        <mesh position={[0, 0.88, 0]} rotation={[-Math.PI / 2, 0, 0]}>
          <planeGeometry args={[2.1, 1.15]} />
          <meshStandardMaterial
            color="#38bdf8"
            emissive="#0ea5e9"
            emissiveIntensity={0.65}
          />
        </mesh>
        {/* 3D Floating Hologram Bars */}
        {[-0.6, -0.2, 0.2, 0.6].map((bx, bIdx) => (
          <mesh key={bIdx} position={[bx, 1.15 + bIdx * 0.08, 0]}>
            <boxGeometry args={[0.18, 0.35 + bIdx * 0.16, 0.18]} />
            <meshStandardMaterial
              color="#34d399"
              emissive="#10b981"
              emissiveIntensity={0.7}
              transparent
              opacity={0.85}
            />
          </mesh>
        ))}

        <Html position={[0, 2.1, 0]} center distanceFactor={15} zIndexRange={[8, 0]}>
          <div
            onClick={(e) => {
              e.stopPropagation();
              onSelectLabObject?.('figure_studio');
            }}
            style={{
              padding: '6px 12px',
              borderRadius: 999,
              background:
                selectedLabObject === 'figure_studio'
                  ? 'rgba(5, 150, 105, 0.96)'
                  : 'rgba(15, 23, 42, 0.88)',
              color: '#ffffff',
              border: '1.5px solid #a855f7',
              fontSize: 11.5,
              fontWeight: 700,
              whiteSpace: 'nowrap',
              cursor: 'pointer',
              boxShadow: '0 4px 14px rgba(0,0,0,0.3)',
            }}
          >
            {t('📊 Bàn Hologram Figure Studio · Click thiết kế Đồ thị', '📊 Figure Studio Hologram · Design Figures')}
          </div>
        </Html>
      </group>

      {/* ── Lush Biophilic Indoor Trees & Botanical Planters Across the Lab ── */}
      {[
        [-11.2, 0, 7.8],
        [11.2, 0, 7.8],
        [11.2, 0, -7.8],
        [-5.8, 0, -7.8],
        [5.8, 0, -7.8],
        [-9.2, 0, 4.2],
      ].map(([px, py, pz], idx) => (
        <group key={`tree-${idx}`} position={[px, py, pz]}>
          {/* Terracotta / Modern Planter */}
          <mesh position={[0, 0.4, 0]} castShadow>
            <cylinderGeometry args={[0.45, 0.34, 0.8, 16]} />
            <meshStandardMaterial color="#d4a373" roughness={0.7} />
          </mesh>
          {/* Tree Trunk */}
          <mesh position={[0, 1.1, 0]} castShadow>
            <cylinderGeometry args={[0.08, 0.12, 1.1, 10]} />
            <meshStandardMaterial color="#78350f" roughness={0.8} />
          </mesh>
          {/* Lush Multi-Sphere Green Canopy */}
          <mesh position={[0, 1.85, 0]} castShadow>
            <sphereGeometry args={[0.78, 18, 18]} />
            <meshStandardMaterial color="#16a34a" roughness={0.65} />
          </mesh>
          <mesh position={[0.35, 2.15, 0.2]} castShadow>
            <sphereGeometry args={[0.55, 16, 16]} />
            <meshStandardMaterial color="#22c55e" roughness={0.65} />
          </mesh>
          <mesh position={[-0.3, 2.05, -0.2]} castShadow>
            <sphereGeometry args={[0.58, 16, 16]} />
            <meshStandardMaterial color="#15803d" roughness={0.65} />
          </mesh>
        </group>
      ))}

      {/* ── Render All University Lab Workstations & Articulated Walking/Talking Researchers ── */}
      {agents.map((agent, index) => {
        const { pos, rotY } = getStationTransform(index);
        return (
          <AgentAvatar
            key={agent.agentId}
            agent={agent}
            index={index}
            position={pos}
            rotationY={rotY}
            isSelected={selectedAgentId === agent.agentId}
            socializeMode={socializeMode}
            onClick={() => onSelectAgent?.(agent)}
          />
        );
      })}
    </>
  );
};
