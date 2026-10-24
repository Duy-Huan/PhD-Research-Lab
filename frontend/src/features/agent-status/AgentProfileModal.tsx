import React, { useState, useEffect } from 'react';
import { useUIStore, useI18n } from '../../shared/state/uiStore';
import type { AgentOfficeViewModel } from '../../shared/api/types';
import { UserCheck, RotateCcw, X, Sparkles, Palette, MessageSquare, Briefcase, FileText, Bot } from 'lucide-react';

interface AgentProfileModalProps {
  agent: AgentOfficeViewModel | null;
  isOpen: boolean;
  onClose: () => void;
}

const PRESET_COLORS = [
  { nameVi: 'Xanh Navy Học thuật', nameEn: 'Royal Academic Navy', hex: '#1e3a8a' },
  { nameVi: 'Xanh Ngọc Công nghệ', nameEn: 'Emerald Tech', hex: '#065f46' },
  { nameVi: 'Nâu Oxford Tweed', nameEn: 'Warm Oxford Tweed', hex: '#78350f' },
  { nameVi: 'Áo Blouse Trắng Lab', nameEn: 'Crisp Lab White', hex: '#ffffff' },
  { nameVi: 'Đỏ Rượu Burgundy', nameEn: 'Senior Burgundy', hex: '#7f1d1d' },
  { nameVi: 'Tím Nghệ thuật', nameEn: 'Creative Violet', hex: '#5b21b6' },
  { nameVi: 'Xanh Lam Cyber', nameEn: 'Cyber Blue', hex: '#0284c7' },
  { nameVi: 'Vàng Hổ phách', nameEn: 'Amber Gold', hex: '#d97706' },
  { nameVi: 'Hồng San hô', nameEn: 'Coral Rose', hex: '#e11d48' },
  { nameVi: 'Xám Than chì', nameEn: 'Dark Charcoal', hex: '#1e293b' },
];

export const AgentProfileModal: React.FC<AgentProfileModalProps> = ({ agent, isOpen, onClose }) => {
  const { t, language } = useI18n();
  const agentProfiles = useUIStore((s) => s.agentProfiles);
  const updateAgentProfile = useUIStore((s) => s.updateAgentProfile);
  const resetAgentProfile = useUIStore((s) => s.resetAgentProfile);

  const existingProfile = agent ? agentProfiles[agent.agentId] : undefined;

  const [customName, setCustomName] = useState('');
  const [customTitle, setCustomTitle] = useState('');
  const [customBio, setCustomBio] = useState('');
  const [customGreeting, setCustomGreeting] = useState('');
  const [customColor, setCustomColor] = useState('');

  // Sync state when agent or modal opens
  useEffect(() => {
    if (agent) {
      const p = agentProfiles[agent.agentId];
      setCustomName(p?.customName || '');
      setCustomTitle(p?.customTitle || '');
      setCustomBio(p?.customBio || '');
      setCustomGreeting(p?.customGreeting || '');
      setCustomColor(p?.customColor || '');
    }
  }, [agent, agentProfiles, isOpen]);

  if (!isOpen || !agent) return null;

  const activeDisplayName = customName.trim() || agent.displayName;
  const activeRole = customTitle.trim() || agent.role;
  const activeGreeting = customGreeting.trim() || agent.speechBubble || '';
  const activeCoatColor = customColor.trim() || '#1e3a8a';

  const handleSave = () => {
    updateAgentProfile(agent.agentId, {
      customName: customName.trim() || undefined,
      customTitle: customTitle.trim() || undefined,
      customBio: customBio.trim() || undefined,
      customGreeting: customGreeting.trim() || undefined,
      customColor: customColor.trim() || undefined,
    });
    onClose();
  };

  const handleReset = () => {
    resetAgentProfile(agent.agentId);
    setCustomName('');
    setCustomTitle('');
    setCustomBio('');
    setCustomGreeting('');
    setCustomColor('');
  };

  return (
    <div
      style={{
        position: 'fixed',
        inset: 0,
        zIndex: 100,
        background: 'rgba(0, 0, 0, 0.75)',
        backdropFilter: 'blur(6px)',
        display: 'flex',
        alignItems: 'center',
        justifyContent: 'center',
        padding: 16,
      }}
      onClick={(e) => {
        if (e.target === e.currentTarget) onClose();
      }}
      role="dialog"
      aria-modal="true"
      aria-labelledby="agent-profile-modal-title"
    >
      <div
        style={{
          width: '100%',
          maxWidth: 620,
          maxHeight: '92vh',
          background: 'var(--panel)',
          color: 'var(--text)',
          borderRadius: 14,
          border: '1px solid var(--line)',
          boxShadow: '0 20px 45px rgba(0,0,0,0.45)',
          display: 'flex',
          flexDirection: 'column',
          overflow: 'hidden',
          animation: 'fadeIn 0.15s ease-out',
        }}
      >
        {/* Modal Header */}
        <div
          style={{
            padding: '16px 20px',
            borderBottom: '1px solid var(--line)',
            display: 'flex',
            alignItems: 'center',
            justifyContent: 'space-between',
            background: 'var(--bg-2)',
          }}
        >
          <div style={{ display: 'flex', alignItems: 'center', gap: 10 }}>
            <div
              style={{
                width: 38,
                height: 38,
                borderRadius: '50%',
                background: activeCoatColor,
                display: 'flex',
                alignItems: 'center',
                justifyContent: 'center',
                color: activeCoatColor === '#ffffff' ? '#0f172a' : '#ffffff',
                boxShadow: '0 2px 8px rgba(0,0,0,0.25)',
                border: '2px solid rgba(255,255,255,0.3)',
              }}
            >
              <Bot size={20} />
            </div>
            <div>
              <h2
                id="agent-profile-modal-title"
                style={{ margin: 0, fontSize: 16, fontWeight: 700 }}
              >
                {t('Hồ sơ Cá nhân & Đặt tên riêng cho AI Agent', 'AI Agent Personal Profile & Custom Name')}
              </h2>
              <div className="muted" style={{ fontSize: 12 }}>
                {t('Tùy biến tên gọi, vai trò, màu trang phục 3D & phong cách giao tiếp', 'Customize name, role, 3D outfit color & greeting persona')}
              </div>
            </div>
          </div>
          <button
            type="button"
            className="btn ghost sm"
            onClick={onClose}
            aria-label={t('Đóng', 'Close')}
            style={{ padding: 6, borderRadius: '50%' }}
          >
            <X size={18} />
          </button>
        </div>

        {/* Modal Body */}
        <div
          style={{
            padding: '18px 20px',
            overflowY: 'auto',
            display: 'flex',
            flexDirection: 'column',
            gap: 16,
          }}
        >
          {/* Live Preview Card */}
          <div
            style={{
              padding: '14px 16px',
              borderRadius: 12,
              background: 'linear-gradient(135deg, rgba(6, 78, 59, 0.35) 0%, rgba(15, 23, 42, 0.6) 100%)',
              border: '1.5px solid rgba(52, 211, 153, 0.35)',
              display: 'flex',
              flexDirection: 'column',
              gap: 10,
            }}
          >
            <div
              style={{
                display: 'flex',
                alignItems: 'center',
                justifyContent: 'space-between',
                fontSize: 11,
                color: '#6ee7b7',
                fontWeight: 600,
                textTransform: 'uppercase',
                letterSpacing: '0.05em',
              }}
            >
              <span style={{ display: 'flex', alignItems: 'center', gap: 5 }}>
                <Sparkles size={13} />
                {t('Xem trước hiển thị thực tế trong phòng Lab 3D', 'Live 3D University Lab Preview')}
              </span>
              <span
                style={{
                  background: 'rgba(16, 185, 129, 0.25)',
                  padding: '2px 8px',
                  borderRadius: 999,
                  color: '#a7f3d0',
                }}
              >
                {agent.engine}
              </span>
            </div>

            <div style={{ display: 'flex', alignItems: 'center', gap: 14 }}>
              {/* 3D Avatar Mini Badge */}
              <div
                style={{
                  width: 52,
                  height: 52,
                  borderRadius: 12,
                  background: activeCoatColor,
                  border: '2px solid rgba(255,255,255,0.4)',
                  display: 'flex',
                  alignItems: 'center',
                  justifyContent: 'center',
                  color: activeCoatColor === '#ffffff' ? '#0f172a' : '#ffffff',
                  boxShadow: '0 4px 12px rgba(0,0,0,0.3)',
                  flexShrink: 0,
                }}
              >
                <Bot size={28} />
              </div>

              <div style={{ flex: 1, minWidth: 0 }}>
                <div
                  style={{
                    fontSize: 15,
                    fontWeight: 700,
                    color: '#f8fafc',
                    display: 'flex',
                    alignItems: 'center',
                    gap: 6,
                  }}
                >
                  <span className="ellipsis">{activeDisplayName}</span>
                  {customName.trim() && (
                    <span
                      style={{
                        fontSize: 10,
                        background: '#10b981',
                        color: '#064e3b',
                        padding: '1px 6px',
                        borderRadius: 999,
                        fontWeight: 700,
                      }}
                    >
                      {t('Đã đổi tên', 'Custom')}
                    </span>
                  )}
                </div>
                <div
                  className="ellipsis"
                  style={{ fontSize: 12, color: '#cbd5e1', marginTop: 2 }}
                >
                  {activeRole}
                </div>
              </div>
            </div>

            {/* Speech Bubble Preview */}
            {activeGreeting && (
              <div
                style={{
                  padding: '7px 12px',
                  borderRadius: 8,
                  background: 'rgba(255, 255, 255, 0.95)',
                  color: '#0f172a',
                  border: `1.5px solid ${activeCoatColor}`,
                  fontSize: 12,
                  lineHeight: 1.35,
                  fontWeight: 500,
                  display: 'flex',
                  alignItems: 'center',
                  gap: 6,
                }}
              >
                <span>💬</span>
                <span className="ellipsis">"{activeGreeting}"</span>
              </div>
            )}
          </div>

          {/* Form Field 1: Custom Name */}
          <div style={{ display: 'flex', flexDirection: 'column', gap: 6 }}>
            <label
              htmlFor="agent-custom-name"
              style={{
                fontSize: 13,
                fontWeight: 600,
                display: 'flex',
                alignItems: 'center',
                gap: 6,
              }}
            >
              <UserCheck size={14} color="var(--accent)" />
              {t('Tên riêng theo sở thích của bạn', 'Custom Name / Nickname')}
            </label>
            <input
              id="agent-custom-name"
              type="text"
              value={customName}
              onChange={(e) => setCustomName(e.target.value)}
              placeholder={t(
                'Nhập tên riêng (ví dụ: GS. Minh Trí, Dr. Sherlock, Alice...)',
                'Enter custom name (e.g., Prof. Minh Tri, Dr. Sherlock, Alice...)'
              )}
              style={{
                padding: '9px 12px',
                borderRadius: 8,
                border: '1px solid var(--line)',
                background: 'var(--bg)',
                color: 'var(--text)',
                fontSize: 13.5,
              }}
            />
            <div className="muted" style={{ fontSize: 11.5 }}>
              {t('Tên mặc định gốc:', 'Original default name:')}{' '}
              <b style={{ color: 'var(--text)' }}>{agent.displayName}</b>
            </div>
          </div>

          {/* Form Field 2: Custom Title / Role */}
          <div style={{ display: 'flex', flexDirection: 'column', gap: 6 }}>
            <label
              htmlFor="agent-custom-title"
              style={{
                fontSize: 13,
                fontWeight: 600,
                display: 'flex',
                alignItems: 'center',
                gap: 6,
              }}
            >
              <Briefcase size={14} color="var(--accent)" />
              {t('Chức danh / Vai trò hiển thị', 'Custom Role / Academic Title')}
            </label>
            <input
              id="agent-custom-title"
              type="text"
              value={customTitle}
              onChange={(e) => setCustomTitle(e.target.value)}
              placeholder={t(
                'Nhập vai trò hiển thị trong phòng Lab...',
                'Enter role displayed in the lab...'
              )}
              style={{
                padding: '9px 12px',
                borderRadius: 8,
                border: '1px solid var(--line)',
                background: 'var(--bg)',
                color: 'var(--text)',
                fontSize: 13.5,
              }}
            />
            <div className="muted" style={{ fontSize: 11.5 }}>
              {t('Vai trò mặc định:', 'Default role:')}{' '}
              <span style={{ color: 'var(--text)' }}>{agent.role}</span>
            </div>
          </div>

          {/* Form Field 3: Custom Bio / Persona */}
          <div style={{ display: 'flex', flexDirection: 'column', gap: 6 }}>
            <label
              htmlFor="agent-custom-bio"
              style={{
                fontSize: 13,
                fontWeight: 600,
                display: 'flex',
                alignItems: 'center',
                gap: 6,
              }}
            >
              <FileText size={14} color="var(--accent)" />
              {t('Tính cách & Phong cách nghiên cứu', 'Personality & Research Persona')}
            </label>
            <textarea
              id="agent-custom-bio"
              rows={3}
              value={customBio}
              onChange={(e) => setCustomBio(e.target.value)}
              placeholder={t(
                'Mô tả tính cách, phong cách phản biện hoặc ghi chú cá nhân cho Agent này...',
                'Describe persona, critique style, or personal notes for this Agent...'
              )}
              style={{
                padding: '9px 12px',
                borderRadius: 8,
                border: '1px solid var(--line)',
                background: 'var(--bg)',
                color: 'var(--text)',
                fontSize: 13,
                resize: 'vertical',
                fontFamily: 'inherit',
              }}
            />
            {agent.personality && (
              <div className="muted" style={{ fontSize: 11.5 }}>
                {t('Tính cách mặc định:', 'Default persona:')}{' '}
                <span style={{ color: 'var(--text)' }}>{agent.personality}</span>
              </div>
            )}
          </div>

          {/* Form Field 4: Custom Speech Bubble / Greeting */}
          <div style={{ display: 'flex', flexDirection: 'column', gap: 6 }}>
            <label
              htmlFor="agent-custom-greeting"
              style={{
                fontSize: 13,
                fontWeight: 600,
                display: 'flex',
                alignItems: 'center',
                gap: 6,
              }}
            >
              <MessageSquare size={14} color="var(--accent)" />
              {t('Câu thoại / Lời chào 3D mặc định', 'Custom 3D Speech Bubble / Greeting')}
            </label>
            <input
              id="agent-custom-greeting"
              type="text"
              value={customGreeting}
              onChange={(e) => setCustomGreeting(e.target.value)}
              placeholder={t(
                'Câu nói xuất hiện trên đầu Agent khi đứng trong Lab...',
                'Speech bubble appearing above Agent in the 3D lab...'
              )}
              style={{
                padding: '9px 12px',
                borderRadius: 8,
                border: '1px solid var(--line)',
                background: 'var(--bg)',
                color: 'var(--text)',
                fontSize: 13.5,
              }}
            />
          </div>

          {/* Form Field 5: Outfit Coat Color Picker */}
          <div style={{ display: 'flex', flexDirection: 'column', gap: 8 }}>
            <div
              style={{
                display: 'flex',
                alignItems: 'center',
                justifyContent: 'space-between',
              }}
            >
              <label
                style={{
                  fontSize: 13,
                  fontWeight: 600,
                  display: 'flex',
                  alignItems: 'center',
                  gap: 6,
                }}
              >
                <Palette size={14} color="var(--accent)" />
                {t('Màu áo trang phục 3D', '3D Outfit Coat Color')}
              </label>
              {customColor && (
                <button
                  type="button"
                  className="btn ghost sm"
                  onClick={() => setCustomColor('')}
                  style={{ fontSize: 11.5, padding: '2px 8px' }}
                >
                  {t('Đặt lại màu gốc', 'Reset color')}
                </button>
              )}
            </div>

            <div style={{ display: 'flex', flexWrap: 'wrap', gap: 8 }}>
              {PRESET_COLORS.map((preset) => {
                const isSelected = (customColor || '').toLowerCase() === preset.hex.toLowerCase();
                const label = language === 'vi' ? preset.nameVi : preset.nameEn;
                return (
                  <button
                    key={preset.hex}
                    type="button"
                    title={label}
                    onClick={() => setCustomColor(preset.hex)}
                    style={{
                      width: 32,
                      height: 32,
                      borderRadius: 8,
                      background: preset.hex,
                      border: isSelected
                        ? '2.5px solid var(--accent)'
                        : preset.hex === '#ffffff'
                        ? '1px solid #cbd5e1'
                        : '1px solid transparent',
                      boxShadow: isSelected
                        ? '0 0 0 2px var(--panel), 0 2px 8px rgba(0,0,0,0.3)'
                        : '0 1px 3px rgba(0,0,0,0.15)',
                      cursor: 'pointer',
                      transform: isSelected ? 'scale(1.12)' : 'scale(1)',
                      transition: 'transform 0.15s ease',
                      display: 'flex',
                      alignItems: 'center',
                      justifyContent: 'center',
                      color: preset.hex === '#ffffff' ? '#0f172a' : '#ffffff',
                    }}
                  >
                    {isSelected && <span style={{ fontSize: 14, fontWeight: 700 }}>✓</span>}
                  </button>
                );
              })}

              {/* Native Color Picker for custom choice */}
              <label
                title={t('Chọn mã màu tùy ý khác', 'Choose custom hex color')}
                style={{
                  width: 32,
                  height: 32,
                  borderRadius: 8,
                  border: '1px dashed var(--line)',
                  background: 'var(--bg-2)',
                  display: 'flex',
                  alignItems: 'center',
                  justifyContent: 'center',
                  cursor: 'pointer',
                  overflow: 'hidden',
                  position: 'relative',
                }}
              >
                <Palette size={15} color="var(--muted)" />
                <input
                  type="color"
                  value={customColor || '#1e3a8a'}
                  onChange={(e) => setCustomColor(e.target.value)}
                  style={{
                    position: 'absolute',
                    opacity: 0,
                    width: '100%',
                    height: '100%',
                    cursor: 'pointer',
                  }}
                />
              </label>
            </div>
          </div>
        </div>

        {/* Modal Footer */}
        <div
          style={{
            padding: '14px 20px',
            borderTop: '1px solid var(--line)',
            display: 'flex',
            alignItems: 'center',
            justifyContent: 'space-between',
            background: 'var(--bg-2)',
          }}
        >
          <div>
            {existingProfile && (
              <button
                type="button"
                className="btn ghost sm"
                onClick={handleReset}
                style={{ color: '#ef4444', gap: 5 }}
              >
                <RotateCcw size={13} />
                {t('Khôi phục mặc định', 'Reset to Default')}
              </button>
            )}
          </div>
          <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
            <button
              type="button"
              className="btn ghost sm"
              onClick={onClose}
            >
              {t('Hủy', 'Cancel')}
            </button>
            <button
              type="button"
              className="btn accent sm"
              onClick={handleSave}
              style={{ fontWeight: 600, padding: '7px 16px' }}
            >
              {t('Lưu Hồ sơ', 'Save Profile')}
            </button>
          </div>
        </div>
      </div>
    </div>
  );
};
