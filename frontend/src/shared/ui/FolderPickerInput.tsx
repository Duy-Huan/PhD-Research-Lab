import React, { useState } from 'react';
import { useI18n } from '../state/uiStore';
import { api } from '../api/client';
import { FolderOpen, FolderTree, RefreshCw } from 'lucide-react';
import { FolderBrowserModal } from './FolderBrowserModal';

export interface FolderPickerInputProps {
  value: string;
  onChange: (value: string) => void;
  placeholder?: string;
  disabled?: boolean;
  dialogTitle?: string;
  style?: React.CSSProperties;
  inputStyle?: React.CSSProperties;
  required?: boolean;
  id?: string;
  name?: string;
}

export const FolderPickerInput: React.FC<FolderPickerInputProps> = ({
  value,
  onChange,
  placeholder,
  disabled = false,
  dialogTitle,
  style,
  inputStyle,
  required = false,
  id,
  name,
}) => {
  const { t } = useI18n();
  const [showModal, setShowModal] = useState(false);
  const [isPickingOS, setIsPickingOS] = useState(false);

  const handleDirectOSPick = async () => {
    if (disabled || isPickingOS) return;
    try {
      setIsPickingOS(true);
      const res = await api.post<{ path: string; canceled: boolean; ok?: boolean }>('/api/system/pick-folder', {
        initial_dir: value || '',
        title: dialogTitle || t('Chọn thư mục từ máy tính', 'Select folder from computer'),
      });
      if (res && res.path && !res.canceled) {
        onChange(res.path);
      }
    } catch (err) {
      // If OS dialog failed (e.g. headless or error), smoothly open the in-app browser modal
      setShowModal(true);
    } finally {
      setIsPickingOS(false);
    }
  };

  return (
    <div
      style={{
        display: 'flex',
        alignItems: 'center',
        gap: 6,
        width: '100%',
        ...style,
      }}
    >
      <input
        id={id}
        name={name}
        className="input"
        value={value}
        onChange={(e) => onChange(e.target.value)}
        placeholder={placeholder}
        disabled={disabled}
        required={required}
        style={{
          flex: 1,
          fontFamily: 'var(--mono)',
          fontSize: 12,
          borderRadius: 8,
          minWidth: 0,
          ...inputStyle,
        }}
      />

      <div style={{ display: 'inline-flex', alignItems: 'center', gap: 4, flexShrink: 0 }}>
        {/* Direct OS Folder Picker Dialog */}
        <button
          type="button"
          className="btn sm ghost"
          onClick={handleDirectOSPick}
          disabled={disabled || isPickingOS}
          title={t(
            'Mở hộp thoại chọn thư mục trực tiếp từ máy tính',
            'Open native OS folder dialog from computer'
          )}
          style={{
            borderRadius: 8,
            padding: '6px 10px',
            display: 'inline-flex',
            alignItems: 'center',
            gap: 5,
            fontSize: 12,
            fontWeight: 500,
          }}
        >
          {isPickingOS ? (
            <RefreshCw size={13} className="spin" color="var(--accent)" />
          ) : (
            <FolderOpen size={14} color="var(--accent)" />
          )}
          <span>{isPickingOS ? t('Đang chọn…', 'Browsing…') : t('Duyệt máy', 'Browse')}</span>
        </button>

        {/* In-app Tree Browser Modal */}
        <button
          type="button"
          className="btn sm ghost"
          onClick={() => setShowModal(true)}
          disabled={disabled}
          title={t('Xem và duyệt cây thư mục trên máy tính', 'Browse computer folder tree')}
          style={{
            borderRadius: 8,
            padding: '6px 8px',
            display: 'inline-flex',
            alignItems: 'center',
            justifyContent: 'center',
          }}
        >
          <FolderTree size={14} color="var(--fg)" />
        </button>
      </div>

      {/* Interactive Folder Browser Modal */}
      <FolderBrowserModal
        isOpen={showModal}
        onClose={() => setShowModal(false)}
        onSelect={(path) => onChange(path)}
        initialPath={value}
        title={dialogTitle}
      />
    </div>
  );
};
