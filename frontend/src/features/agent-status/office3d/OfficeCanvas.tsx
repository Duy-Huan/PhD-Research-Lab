import React, { Suspense, useState, useEffect, useRef } from 'react';
import { Canvas } from '@react-three/fiber';
import { OrbitControls } from '@react-three/drei';
import type { AgentOfficeViewModel } from '../../../shared/api/types';
import type { InteractiveLabObjectKind } from '../../../shared/state/uiStore';
import { useI18n } from '../../../shared/state/uiStore';
import { OfficeScene, type LabLightingMode } from './OfficeScene';
import { AlertTriangle, Camera, Sun, Moon, Sparkles, Trees, Users } from 'lucide-react';

interface OfficeCanvasProps {
  agents: AgentOfficeViewModel[];
  selectedAgentId?: string | null;
  selectedLabObject?: InteractiveLabObjectKind;
  topicTitle?: string;
  paperCount?: number;
  missionCount?: number;
  socializeMode?: boolean;
  onToggleSocialize?: () => void;
  fullViewport?: boolean;
  onSelectAgent?: (agent: AgentOfficeViewModel) => void;
  onSelectLabObject?: (obj: InteractiveLabObjectKind) => void;
}

const CAMERA_PRESETS: Array<{
  id: string;
  labelVi: string;
  labelEn: string;
  pos: [number, number, number];
  target: [number, number, number];
}> = [
  {
    id: 'overview',
    labelVi: 'Toàn cảnh',
    labelEn: 'Overview',
    pos: [0, 12.0, 15.0],
    target: [0, 0.8, -1.5],
  },
  {
    id: 'podium',
    labelVi: 'Bảng Đề cương',
    labelEn: 'Brand & Outline',
    pos: [0, 4.2, 1.8],
    target: [0, 2.2, -8.5],
  },
  {
    id: 'library',
    labelVi: 'Thư viện SKB',
    labelEn: 'Library',
    pos: [-4.2, 4.5, 4.0],
    target: [-11.5, 1.8, -0.5],
  },
  {
    id: 'hpc',
    labelVi: 'HPC & OpenCode',
    labelEn: 'HPC Rack',
    pos: [-4.5, 4.2, -1.2],
    target: [-9.5, 1.6, -7.8],
  },
  {
    id: 'review',
    labelVi: 'Bàn Bình duyệt',
    labelEn: 'Review Table',
    pos: [3.8, 4.8, 6.2],
    target: [9.5, 1.0, 2.8],
  },
  {
    id: 'figures',
    labelVi: 'Figure Hologram',
    labelEn: 'Figure Studio',
    pos: [3.8, 4.5, -0.5],
    target: [9.5, 1.0, -4.6],
  },
];

export const OfficeCanvas: React.FC<OfficeCanvasProps> = ({
  agents,
  selectedAgentId,
  selectedLabObject,
  topicTitle,
  paperCount = 0,
  missionCount = 0,
  socializeMode = true,
  onToggleSocialize,
  fullViewport = true,
  onSelectAgent,
  onSelectLabObject,
}) => {
  const { t } = useI18n();
  const [hasWebGlError, setHasWebGlError] = useState(false);
  const [reducedMotion, setReducedMotion] = useState(false);
  const [lightingMode, setLightingMode] = useState<LabLightingMode>('biophilic_green');
  const [activePreset, setActivePreset] = useState<string>('overview');
  const controlsRef = useRef<any>(null);

  useEffect(() => {
    try {
      const mq = window.matchMedia?.('(prefers-reduced-motion: reduce)');
      if (mq?.matches) setReducedMotion(true);
      const canvas = document.createElement('canvas');
      const gl = canvas.getContext('webgl') || canvas.getContext('experimental-webgl');
      if (!gl) setHasWebGlError(true);
    } catch {
      setHasWebGlError(true);
    }
  }, []);

  const applyCameraPreset = (presetId: string) => {
    setActivePreset(presetId);
    const found = CAMERA_PRESETS.find((p) => p.id === presetId);
    if (found && controlsRef.current) {
      const ctrl = controlsRef.current;
      if (ctrl.object?.position) {
        ctrl.object.position.set(...found.pos);
      }
      if (ctrl.target) {
        ctrl.target.set(...found.target);
      }
      ctrl.update?.();
    }
  };

  if (hasWebGlError) {
    return (
      <div
        style={{
          height: fullViewport ? '100%' : 480,
          minHeight: 380,
          background: 'var(--panel)',
          display: 'flex',
          flexDirection: 'column',
          alignItems: 'center',
          justifyContent: 'center',
          borderRadius: fullViewport ? 0 : 12,
          border: '1px solid var(--line)',
          padding: 32,
          textAlign: 'center',
        }}
      >
        <AlertTriangle size={36} color="var(--warn)" style={{ marginBottom: 10 }} />
        <b style={{ fontSize: 15 }}>
          {t('WebGL không được hỗ trợ trên trình duyệt này', 'WebGL is not supported')}
        </b>
      </div>
    );
  }

  const animateAlways =
    (socializeMode || agents.some((a) => a.presence === 'running')) && !reducedMotion;

  const canvasBg =
    lightingMode === 'biophilic_green'
      ? 'radial-gradient(circle at 50% 20%, #d1fae5 0%, #a7f3d0 45%, #bae6fd 100%)'
      : lightingMode === 'daylight'
      ? 'radial-gradient(circle at 50% 25%, #f8fafc 0%, #dbeafe 100%)'
      : lightingMode === 'cyber_science'
      ? 'radial-gradient(circle at 50% 25%, #0f172a 0%, #020617 100%)'
      : 'radial-gradient(circle at 50% 25%, #1c1917 0%, #0c0a09 100%)';

  return (
    <div
      style={{
        width: '100%',
        height: fullViewport ? '100%' : 520,
        minHeight: 420,
        borderRadius: fullViewport ? 0 : 12,
        overflow: 'hidden',
        position: 'relative',
        background: canvasBg,
      }}
    >
      {/* Bottom-Center Floating Camera, Social Mode & Atmosphere Dock */}
      <div
        style={{
          position: 'absolute',
          bottom: 14,
          left: '50%',
          transform: 'translateX(-50%)',
          zIndex: 15,
          display: 'flex',
          alignItems: 'center',
          gap: 5,
          padding: '5px 10px',
          borderRadius: 999,
          background: 'rgba(15, 23, 42, 0.88)',
          backdropFilter: 'blur(12px)',
          border: '1px solid rgba(52, 211, 153, 0.35)',
          boxShadow: '0 10px 30px rgba(0, 0, 0, 0.35)',
          flexWrap: 'wrap',
          maxWidth: '94%',
        }}
      >
        <Camera size={13} color="#34d399" style={{ marginLeft: 4 }} />

        {CAMERA_PRESETS.map((preset) => (
          <button
            key={preset.id}
            type="button"
            onClick={() => applyCameraPreset(preset.id)}
            style={{
              border: 'none',
              borderRadius: 999,
              padding: '4px 9px',
              fontSize: 11,
              fontWeight: activePreset === preset.id ? 700 : 500,
              background:
                activePreset === preset.id ? '#10b981' : 'rgba(255, 255, 255, 0.08)',
              color: activePreset === preset.id ? '#ffffff' : '#cbd5e1',
              cursor: 'pointer',
            }}
          >
            {t(preset.labelVi, preset.labelEn)}
          </button>
        ))}

        <span
          style={{
            width: 1,
            height: 16,
            background: 'rgba(148, 163, 184, 0.25)',
            margin: '0 3px',
          }}
        />

        {/* Toggle Walking & Socializing Mode */}
        {onToggleSocialize && (
          <button
            type="button"
            onClick={onToggleSocialize}
            title={t(
              'Bật/Tắt chế độ Agents đi lại & thảo luận nhóm như người thật',
              'Toggle Agents Walking & Conversing'
            )}
            style={{
              border: 'none',
              borderRadius: 999,
              padding: '4px 9px',
              fontSize: 11,
              fontWeight: 600,
              background: socializeMode ? '#059669' : 'rgba(255, 255, 255, 0.08)',
              color: '#ffffff',
              display: 'inline-flex',
              alignItems: 'center',
              gap: 4,
              cursor: 'pointer',
            }}
          >
            <Users size={12} />
            <span>{socializeMode ? t('Đi lại: BẬT', 'Walk: ON') : t('Đi lại: TẮT', 'Walk: OFF')}</span>
          </button>
        )}

        {/* Lighting Atmosphere Switcher */}
        <button
          type="button"
          onClick={() => setLightingMode('biophilic_green')}
          title={t('Không gian Phòng Lab Xanh', 'Biophilic Green Lab')}
          style={{
            border: 'none',
            borderRadius: 999,
            padding: '4px 8px',
            fontSize: 11,
            background:
              lightingMode === 'biophilic_green' ? '#16a34a' : 'rgba(255, 255, 255, 0.08)',
            color: '#ffffff',
            display: 'inline-flex',
            alignItems: 'center',
            gap: 3,
            cursor: 'pointer',
          }}
        >
          <Trees size={12} /> {t('Lab Xanh', 'Green')}
        </button>
        <button
          type="button"
          onClick={() => setLightingMode('daylight')}
          title={t('Ánh sáng Ban ngày', 'Daylight')}
          style={{
            border: 'none',
            borderRadius: 999,
            padding: '4px 8px',
            fontSize: 11,
            background:
              lightingMode === 'daylight' ? '#0284c7' : 'rgba(255, 255, 255, 0.08)',
            color: '#ffffff',
            display: 'inline-flex',
            alignItems: 'center',
            gap: 3,
            cursor: 'pointer',
          }}
        >
          <Sun size={12} />
        </button>
        <button
          type="button"
          onClick={() => setLightingMode('night_lab')}
          title={t('Phòng Lab Đêm', 'Night Lab')}
          style={{
            border: 'none',
            borderRadius: 999,
            padding: '4px 8px',
            fontSize: 11,
            background:
              lightingMode === 'night_lab' ? '#d97706' : 'rgba(255, 255, 255, 0.08)',
            color: '#ffffff',
            display: 'inline-flex',
            alignItems: 'center',
            gap: 3,
            cursor: 'pointer',
          }}
        >
          <Moon size={12} />
        </button>
        <button
          type="button"
          onClick={() => setLightingMode('cyber_science')}
          title="Cyber Lab"
          style={{
            border: 'none',
            borderRadius: 999,
            padding: '4px 8px',
            fontSize: 11,
            background:
              lightingMode === 'cyber_science' ? '#4f46e5' : 'rgba(255, 255, 255, 0.08)',
            color: '#ffffff',
            display: 'inline-flex',
            alignItems: 'center',
            gap: 3,
            cursor: 'pointer',
          }}
        >
          <Sparkles size={12} />
        </button>
      </div>

      <Canvas
        shadows
        frameloop={animateAlways ? 'always' : 'demand'}
        camera={{ position: [0, 12.0, 15.0], fov: 42 }}
        style={{ width: '100%', height: '100%' }}
        onCreated={({ gl }) => {
          gl.domElement.addEventListener('webglcontextlost', (e) => {
            e.preventDefault();
            setHasWebGlError(true);
          });
        }}
      >
        <Suspense fallback={null}>
          <OfficeScene
            agents={agents}
            selectedAgentId={selectedAgentId}
            selectedLabObject={selectedLabObject}
            lightingMode={lightingMode}
            topicTitle={topicTitle}
            paperCount={paperCount}
            missionCount={missionCount}
            socializeMode={socializeMode}
            onSelectAgent={onSelectAgent}
            onSelectLabObject={onSelectLabObject}
          />
          <OrbitControls
            ref={controlsRef}
            target={[0, 0.8, -1.5]}
            maxPolarAngle={Math.PI / 2.08}
            minDistance={3.5}
            maxDistance={28}
            enableDamping
            dampingFactor={0.08}
          />
        </Suspense>
      </Canvas>
    </div>
  );
};
