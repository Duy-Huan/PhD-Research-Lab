import React, { useState, useEffect, useCallback, useMemo, useRef } from 'react';
import {
  ReactFlow,
  Background,
  Controls,
  type Node,
  type Edge,
  type Connection,
  addEdge,
  applyNodeChanges,
  applyEdgeChanges,
  type OnNodesChange,
  type OnEdgesChange,
  type OnConnect,
} from '@xyflow/react';
import '@xyflow/react/dist/style.css';
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import { useUIStore, useI18n } from '../../shared/state/uiStore';
import { api } from '../../shared/api/client';
import {
  HarnessToolSpec,
  CustomHarnessWorkflow,
  HarnessExecutionReport,
} from '../../shared/api/types';
import { HarnessNodeComponent } from './HarnessNodeComponent';
import {
  Play,
  Save,
  Plus,
  RefreshCw,
  ExternalLink,
  Layers,
  Sliders,
  CheckCircle2,
  XCircle,
  FileDown,
  Info,
  ChevronRight,
  Sparkles,
  Bot,
  Zap,
  ArrowLeft,
  Maximize2,
  X,
} from 'lucide-react';

interface CustomHarnessStudioProps {
  topicId?: string;
  onSwitchToAutomated?: () => void;
  isFullSpace?: boolean;
}

export const CustomHarnessStudio: React.FC<CustomHarnessStudioProps> = ({
  topicId,
  onSwitchToAutomated,
  isFullSpace,
}) => {
  const queryClient = useQueryClient();
  const { t } = useI18n();
  const { setMainView, open3DOffice, openHarnessStudio, mainView } = useUIStore();
  const fullSpaceActive = isFullSpace ?? (mainView === 'harness');
  const [paletteOpen, setPaletteOpen] = useState<boolean>(true);
  const [inspectorOpen, setInspectorOpen] = useState<boolean>(true);
  const reactFlowWrapper = useRef<HTMLDivElement>(null);

  // Studio mode: 'manual' (this canvas) vs 'automated' (agent teams)
  const [studioMode, setStudioMode] = useState<'manual' | 'automated'>('manual');

  // Selected workflow & template state
  const [selectedWorkflowId, setSelectedWorkflowId] = useState<string>('hw-preset-llm-eval');
  const [workflowName, setWorkflowName] = useState<string>('');
  const [workflowDesc, setWorkflowDesc] = useState<string>('');
  const [selectedNodeId, setSelectedNodeId] = useState<string | null>(null);

  // Nodes & Edges state for ReactFlow
  const [nodes, setNodes] = useState<Node[]>([]);
  const [edges, setEdges] = useState<Edge[]>([]);

  // Execution report state
  const [latestReport, setLatestReport] = useState<HarnessExecutionReport | null>(null);
  const [showReportModal, setShowReportModal] = useState<boolean>(false);

  // Fetch tools catalog
  const { data: toolsData } = useQuery<{ tools: HarnessToolSpec[] }>({
    queryKey: ['harness-tools'],
    queryFn: () => api.get<{ tools: HarnessToolSpec[] }>('/api/harness/tools'),
  });

  // Fetch saved workflows
  const { data: workflowsData, isLoading: isWfLoading } = useQuery<{
    workflows: CustomHarnessWorkflow[];
  }>({
    queryKey: ['harness-workflows', topicId],
    queryFn: () =>
      api.get<{ workflows: CustomHarnessWorkflow[] }>(
        `/api/harness/workflows${topicId ? `?topic_id=${topicId}` : ''}`
      ),
  });

  const tools = toolsData?.tools || [];
  const workflows = workflowsData?.workflows || [];

  // Register custom node types for ReactFlow
  const nodeTypes = useMemo(
    () => ({
      harnessNode: HarnessNodeComponent,
    }),
    []
  );

  // Delete node helper
  const handleDeleteNode = useCallback((nodeId: string) => {
    setNodes((nds) => nds.filter((n) => n.id !== nodeId));
    setEdges((eds) => eds.filter((e) => e.source !== nodeId && e.target !== nodeId));
    setSelectedNodeId((cur) => (cur === nodeId ? null : cur));
  }, []);

  // Load a workflow into the canvas
  const loadWorkflowIntoCanvas = useCallback(
    (wf: CustomHarnessWorkflow) => {
      setSelectedWorkflowId(wf.id);
      setWorkflowName(wf.name);
      setWorkflowDesc(wf.description || '');
      setSelectedNodeId(null);
      setLatestReport(null);

      const flowNodes: Node[] = (wf.nodes || []).map((n) => ({
        id: n.id,
        type: 'harnessNode',
        position: n.position || { x: 100, y: 100 },
        data: {
          ...n.data,
          onDelete: handleDeleteNode,
        },
      }));

      const flowEdges: Edge[] = (wf.edges || []).map((e) => ({
        id: e.id,
        source: e.source,
        target: e.target,
        animated: true,
        style: { stroke: 'var(--accent)', strokeWidth: 2 },
      }));

      setNodes(flowNodes);
      setEdges(flowEdges);
    },
    [handleDeleteNode]
  );

  // Initial load of first preset
  useEffect(() => {
    if (workflows.length > 0 && (!selectedWorkflowId || selectedWorkflowId === 'hw-preset-llm-eval')) {
      const target = workflows.find((w) => w.id === selectedWorkflowId) || workflows[0];
      if (target) {
        loadWorkflowIntoCanvas(target);
      }
    }
  }, [workflows, selectedWorkflowId, loadWorkflowIntoCanvas]);

  // ReactFlow event handlers
  const onNodesChange: OnNodesChange = useCallback(
    (changes) => setNodes((nds) => applyNodeChanges(changes, nds)),
    []
  );

  const onEdgesChange: OnEdgesChange = useCallback(
    (changes) => setEdges((eds) => applyEdgeChanges(changes, eds)),
    []
  );

  const onConnect: OnConnect = useCallback(
    (params: Connection) =>
      setEdges((eds) =>
        addEdge(
          {
            ...params,
            animated: true,
            style: { stroke: 'var(--accent)', strokeWidth: 2 },
          },
          eds
        )
      ),
    []
  );

  const onNodeClick = useCallback((_: React.MouseEvent, node: Node) => {
    setSelectedNodeId(node.id);
  }, []);

  // Drag and Drop from tool palette onto canvas
  const onDragStart = (event: React.DragEvent, toolId: string) => {
    event.dataTransfer.setData('application/harness-tool', toolId);
    event.dataTransfer.effectAllowed = 'move';
  };

  const onDragOver = (event: React.DragEvent) => {
    event.preventDefault();
    event.dataTransfer.dropEffect = 'move';
  };

  const addToolNodeAtPosition = useCallback(
    (toolId: string, position: { x: number; y: number }) => {
      const toolSpec = tools.find((t) => t.id === toolId);
      const newId = `node-${Date.now().toString().slice(-6)}`;
      const newNode: Node = {
        id: newId,
        type: 'harnessNode',
        position,
        data: {
          label: toolSpec?.name || 'Harness Step',
          tool: toolId,
          category: toolSpec?.category || 'benchmark',
          params: { ...(toolSpec?.default_params || {}) },
          status: 'idle',
          onDelete: handleDeleteNode,
        },
      };

      setNodes((nds) => [...nds, newNode]);
      setSelectedNodeId(newId);
    },
    [tools, handleDeleteNode]
  );

  const onDrop = useCallback(
    (event: React.DragEvent) => {
      event.preventDefault();
      const toolId = event.dataTransfer.getData('application/harness-tool');
      if (!toolId) return;

      const bounds = reactFlowWrapper.current?.getBoundingClientRect();
      const position = {
        x: bounds ? event.clientX - bounds.left - 100 : 150,
        y: bounds ? event.clientY - bounds.top - 40 : 150,
      };

      addToolNodeAtPosition(toolId, position);
    },
    [addToolNodeAtPosition]
  );

  // Save workflow mutation
  const saveWorkflowMutation = useMutation({
    mutationFn: async () => {
      const payload: Partial<CustomHarnessWorkflow> = {
        id: selectedWorkflowId.startsWith('hw-preset-') ? undefined : selectedWorkflowId,
        name: workflowName.trim() || t('Quy trình Harness Tùy chỉnh', 'Custom Harness Workflow'),
        description: workflowDesc.trim(),
        topic_id: topicId || '',
        nodes: nodes.map((n) => ({
          id: n.id,
          type: n.type,
          position: n.position,
          data: {
            label: String(n.data.label || ''),
            tool: String(n.data.tool || ''),
            category: String(n.data.category || ''),
            params: (n.data.params as Record<string, unknown>) || {},
          },
        })),
        edges: edges.map((e) => ({
          id: e.id,
          source: e.source,
          target: e.target,
        })),
      };

      return api.post<CustomHarnessWorkflow>('/api/harness/workflows', payload);
    },
    onSuccess: (saved) => {
      queryClient.invalidateQueries({ queryKey: ['harness-workflows'] });
      setSelectedWorkflowId(saved.id);
      alert(t('Đã lưu quy trình harness thành công!', 'Harness workflow saved successfully!'));
    },
    onError: (err: Error) => {
      alert(t(`Lỗi lưu quy trình: ${err.message}`, `Failed to save workflow: ${err.message}`));
    },
  });

  // Execute workflow mutation
  const executeMutation = useMutation({
    mutationFn: async () => {
      // Set all nodes to running visually
      setNodes((nds) =>
        nds.map((n) => ({
          ...n,
          data: { ...n.data, status: 'running' },
        }))
      );

      const workflowPayload = {
        id: selectedWorkflowId,
        name: workflowName,
        nodes: nodes.map((n) => ({
          id: n.id,
          data: n.data,
        })),
        edges: edges.map((e) => ({
          id: e.id,
          source: e.source,
          target: e.target,
        })),
      };

      const res = await api.post<HarnessExecutionReport>('/api/harness/execute', {
        workflow: workflowPayload,
        topic_id: topicId || '',
      });
      return res;
    },
    onSuccess: (report: HarnessExecutionReport) => {
      setLatestReport(report);
      setShowReportModal(true);

      // Update node statuses with execution outputs
      setNodes((nds) =>
        nds.map((n) => {
          const res = report.node_results[n.id];
          if (!res) return n;
          return {
            ...n,
            data: {
              ...n.data,
              status: res.passed ? 'completed' : 'failed',
              result: {
                passed: res.passed,
                duration_s: res.duration_s,
                metrics: res.metrics,
                summary: res.summary,
              },
            },
          };
        })
      );
    },
    onError: (err: Error) => {
      setNodes((nds) =>
        nds.map((n) => ({
          ...n,
          data: { ...n.data, status: 'idle' },
        }))
      );
      alert(t(`Lỗi thực thi harness: ${err.message}`, `Failed to execute harness: ${err.message}`));
    },
  });

  // Selected node for config
  const selectedNode = nodes.find((n) => n.id === selectedNodeId) || null;
  const selectedNodeTool = tools.find((t) => t.id === selectedNode?.data.tool);

  // Update selected node parameter
  const updateSelectedNodeParam = (key: string, value: unknown) => {
    if (!selectedNodeId) return;
    setNodes((nds) =>
      nds.map((n) => {
        if (n.id !== selectedNodeId) return n;
        const currentParams = (n.data.params as Record<string, unknown>) || {};
        return {
          ...n,
          data: {
            ...n.data,
            params: {
              ...currentParams,
              [key]: value,
            },
          },
        };
      })
    );
  };

  const updateSelectedNodeLabel = (label: string) => {
    if (!selectedNodeId) return;
    setNodes((nds) =>
      nds.map((n) => (n.id === selectedNodeId ? { ...n, data: { ...n.data, label } } : n))
    );
  };

  const handleExportJson = () => {
    const dataStr =
      'data:text/json;charset=utf-8,' +
      encodeURIComponent(
        JSON.stringify(
          {
            name: workflowName,
            description: workflowDesc,
            nodes,
            edges,
          },
          null,
          2
        )
      );
    const dlAnchor = document.createElement('a');
    dlAnchor.setAttribute('href', dataStr);
    dlAnchor.setAttribute('download', `${workflowName || 'harness-workflow'}.json`);
    dlAnchor.click();
  };

  return (
    <div
      style={{
        display: 'flex',
        flexDirection: 'column',
        height: '100%',
        width: '100%',
        background: 'var(--bg)',
        color: 'var(--ink)',
        overflow: 'hidden',
      }}
    >
      {/* Top Header: Mode Pill Selector + Full Space Navigation Controls */}
      <div
        id="harness-space-header"
        style={{
          padding: '8px 14px',
          borderBottom: '1px solid var(--line)',
          background: 'var(--panel)',
          display: 'flex',
          justifyContent: 'space-between',
          alignItems: 'center',
          flexWrap: 'wrap',
          gap: 10,
        }}
      >
        <div style={{ display: 'flex', alignItems: 'center', gap: 10, flexWrap: 'wrap' }}>
          {fullSpaceActive && (
            <div style={{ display: 'flex', alignItems: 'center', gap: 5 }}>
              <button
                type="button"
                className="btn sm ghost"
                onClick={() => setMainView('chat')}
                title={t('Quay lại Trò chuyện Nghiên cứu', 'Back to Research Chat')}
                style={{ borderRadius: 6, gap: 5, padding: '4px 8px' }}
              >
                <ArrowLeft size={14} />
                <span style={{ fontSize: 12 }}>{t('Trò chuyện', 'Chat')}</span>
              </button>
              <button
                type="button"
                className="btn sm ghost"
                onClick={() => open3DOffice(true)}
                title={t('Mở Phòng Lab 3D', 'Open 3D Lab')}
                style={{ borderRadius: 6, gap: 5, padding: '4px 8px' }}
              >
                <Bot size={14} />
                <span style={{ fontSize: 12 }}>{t('Lab 3D', '3D Lab')}</span>
              </button>
            </div>
          )}

          <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
            <Layers size={18} color="var(--accent)" />
            <span style={{ fontWeight: 700, fontSize: 14 }}>
              {t('Harness Studio & Thiết kế Quy trình', 'Harness Studio & Workflow Builder')}
            </span>
            {fullSpaceActive && (
              <span
                style={{
                  display: 'inline-flex',
                  alignItems: 'center',
                  gap: 4,
                  background: 'rgba(16, 185, 129, 0.1)',
                  border: '1px solid rgba(16, 185, 129, 0.3)',
                  borderRadius: 999,
                  padding: '2px 8px',
                  fontSize: 11,
                  fontWeight: 600,
                  color: 'var(--accent)',
                }}
              >
                <Sliders size={11} />
                <span>{t('Không gian Full Canvas', 'Full Canvas Space')}</span>
              </span>
            )}
          </div>

          {/* Mode Switcher */}
          <div
            style={{
              display: 'inline-flex',
              background: 'var(--bg-2)',
              borderRadius: 6,
              padding: 2,
              border: '1px solid var(--line)',
              marginLeft: 4,
            }}
          >
            <button
              type="button"
              className={`btn xs ${studioMode === 'automated' ? 'accent' : 'ghost'}`}
              onClick={() => {
                setStudioMode('automated');
                if (onSwitchToAutomated) onSwitchToAutomated();
              }}
              style={{ borderRadius: 4, display: 'flex', alignItems: 'center', gap: 4, padding: '3px 8px' }}
            >
              <Bot size={12} />
              <span>{t('Quy trình Tự động', 'Automated Agents')}</span>
            </button>
            <button
              type="button"
              className={`btn xs ${studioMode === 'manual' ? 'accent' : 'ghost'}`}
              onClick={() => setStudioMode('manual')}
              style={{ borderRadius: 4, display: 'flex', alignItems: 'center', gap: 4, padding: '3px 8px' }}
            >
              <Sparkles size={12} />
              <span>{t('Thủ công Kéo thả', 'Visual Drag & Drop')}</span>
            </button>
          </div>
        </div>

        {/* Workflow Action Bar */}
        <div style={{ display: 'flex', alignItems: 'center', gap: 6, flexWrap: 'wrap' }}>
          {!fullSpaceActive && (
            <button
              type="button"
              className="btn sm accent"
              onClick={() => openHarnessStudio()}
              title={t('Mở rộng ra thành một space riêng có full không gian như 3D space', 'Pop out into a dedicated full canvas space like 3D space')}
              style={{ borderRadius: 6, display: 'flex', alignItems: 'center', gap: 5 }}
            >
              <Maximize2 size={13} />
              <span>{t('Topup Space Riêng', 'Topup Full Space')}</span>
            </button>
          )}

          {/* Preset / Custom Selector */}
          <select
            className="input sm"
            style={{ minWidth: 190, fontSize: 12 }}
            value={selectedWorkflowId}
            onChange={(e) => {
              const wf = workflows.find((w) => w.id === e.target.value);
              if (wf) loadWorkflowIntoCanvas(wf);
            }}
          >
            {workflows.map((w) => (
              <option key={w.id} value={w.id}>
                {w.name} {w.is_preset ? `(${t('Mẫu chuẩn', 'Preset')})` : ''}
              </option>
            ))}
          </select>

          <button
            type="button"
            className="btn sm accent"
            onClick={() => executeMutation.mutate()}
            disabled={executeMutation.isPending || nodes.length === 0}
            title={t('Thực thi quy trình harness', 'Execute harness pipeline')}
          >
            <Play size={13} style={{ marginRight: 4 }} />
            {executeMutation.isPending
              ? t('Đang chạy…', 'Executing…')
              : t('Chạy Harness', 'Run Harness')}
          </button>

          <button
            type="button"
            className="btn sm ghost"
            onClick={() => saveWorkflowMutation.mutate()}
            disabled={saveWorkflowMutation.isPending}
            title={t('Lưu quy trình harness này', 'Save this harness workflow')}
          >
            <Save size={13} style={{ marginRight: 4 }} />
            {t('Lưu', 'Save')}
          </button>

          <button
            type="button"
            className="btn sm ghost"
            onClick={() => {
              setSelectedWorkflowId(`hw-${Date.now().toString().slice(-8)}`);
              setWorkflowName(t('Quy trình Mới', 'New Workflow'));
              setWorkflowDesc('');
              setNodes([]);
              setEdges([]);
              setSelectedNodeId(null);
              setLatestReport(null);
            }}
            title={t('Tạo canvas mới', 'Create fresh canvas')}
          >
            <Plus size={13} style={{ marginRight: 4 }} />
            {t('Mới', 'New')}
          </button>

          <button
            type="button"
            className="btn sm ghost"
            onClick={handleExportJson}
            title={t('Xuất sơ đồ JSON', 'Export JSON')}
          >
            <FileDown size={13} />
          </button>

          {fullSpaceActive && (
            <>
              <button
                type="button"
                className={`btn sm ${paletteOpen ? 'accent' : 'ghost'}`}
                onClick={() => setPaletteOpen(!paletteOpen)}
                title={paletteOpen ? t('Ẩn bảng công cụ', 'Hide tools palette') : t('Hiện bảng công cụ', 'Show tools palette')}
                style={{ borderRadius: 6, gap: 4 }}
              >
                <Layers size={13} />
                <span>{paletteOpen ? t('Ẩn Công cụ', 'Hide Tools') : t('Công cụ', 'Tools')}</span>
              </button>

              {selectedNode && (
                <button
                  type="button"
                  className={`btn sm ${inspectorOpen ? 'accent' : 'ghost'}`}
                  onClick={() => setInspectorOpen(!inspectorOpen)}
                  title={inspectorOpen ? t('Ẩn bảng cấu hình', 'Hide config') : t('Hiện bảng cấu hình', 'Show config')}
                  style={{ borderRadius: 6, gap: 4 }}
                >
                  <Sliders size={13} />
                  <span>{inspectorOpen ? t('Ẩn Cấu hình', 'Hide Config') : t('Cấu hình', 'Config')}</span>
                </button>
              )}

              <button
                type="button"
                className="icon sm"
                onClick={() => setMainView('chat')}
                title={t('Đóng Space, về Trò chuyện', 'Close Space, back to Chat')}
                style={{ marginLeft: 2 }}
              >
                <X size={15} />
              </button>
            </>
          )}
        </div>
      </div>

      {/* Main Studio Body: Left Palette + Center Canvas + Right Config Inspector */}
      <div style={{ flex: 1, display: 'flex', overflow: 'hidden', position: 'relative' }}>
        {/* 1. Left Sidebar: Tool Palette */}
        {paletteOpen ? (
          <aside
            style={{
              width: 250,
            background: 'var(--panel)',
            borderRight: '1px solid var(--line)',
            display: 'flex',
            flexDirection: 'column',
            overflowY: 'auto',
            padding: 12,
            gap: 10,
            flexShrink: 0,
          }}
        >
          <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between' }}>
            <span style={{ fontSize: 12, fontWeight: 700, textTransform: 'uppercase', letterSpacing: 0.5, color: 'var(--muted)' }}>
              {t('Công cụ Harness Mở', 'Harness Tools')}
            </span>
            <span style={{ fontSize: 11, color: 'var(--muted)' }}>{tools.length}</span>
          </div>

          <p className="muted" style={{ margin: 0, fontSize: 11.5, lineHeight: 1.4 }}>
            {t(
              'Kéo thả thẻ công cụ vào canvas hoặc bấm nút cộng để thêm bước kiểm thử vào quy trình.',
              'Drag and drop tool cards onto canvas or click plus to add a test stage.'
            )}
          </p>

          <div style={{ display: 'flex', flexDirection: 'column', gap: 8, marginTop: 4 }}>
            {tools.map((tool) => (
              <div
                key={tool.id}
                draggable
                onDragStart={(e) => onDragStart(e, tool.id)}
                style={{
                  background: 'var(--bg-2)',
                  border: '1px solid var(--line)',
                  borderRadius: 8,
                  padding: '9px 10px',
                  cursor: 'grab',
                  display: 'flex',
                  flexDirection: 'column',
                  gap: 4,
                  transition: 'border 0.15s ease',
                }}
                onMouseEnter={(e) => (e.currentTarget.style.borderColor = 'var(--accent)')}
                onMouseLeave={(e) => (e.currentTarget.style.borderColor = 'var(--line)')}
              >
                <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
                  <b style={{ fontSize: 12, color: 'var(--ink)' }}>{tool.name}</b>
                  <button
                    type="button"
                    className="icon xs"
                    onClick={() => addToolNodeAtPosition(tool.id, { x: 120 + nodes.length * 40, y: 80 + nodes.length * 40 })}
                    title={t('Thêm vào canvas', 'Add to canvas')}
                    style={{ padding: 2 }}
                  >
                    <Plus size={13} color="var(--accent)" />
                  </button>
                </div>
                <div className="muted" style={{ fontSize: 11, lineHeight: 1.3 }}>
                  {tool.description}
                </div>
                <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginTop: 4 }}>
                  <span className="chip sm" style={{ fontSize: 10, padding: '1px 6px' }}>
                    {tool.category}
                  </span>
                  <a
                    href={tool.docs_url}
                    target="_blank"
                    rel="noopener noreferrer"
                    title={t('Tài liệu mã nguồn mở', 'Open-source documentation')}
                    style={{ fontSize: 11, color: 'var(--muted)', display: 'flex', alignItems: 'center', gap: 2 }}
                    onClick={(e) => e.stopPropagation()}
                  >
                    <ExternalLink size={10} />
                  </a>
                </div>
              </div>
            ))}
          </div>
        </aside>
        ) : (
          <div
            style={{
              width: 36,
              background: 'var(--panel)',
              borderRight: '1px solid var(--line)',
              display: 'flex',
              flexDirection: 'column',
              alignItems: 'center',
              padding: '10px 4px',
              gap: 8,
              flexShrink: 0,
            }}
          >
            <button
              type="button"
              className="icon sm"
              onClick={() => setPaletteOpen(true)}
              title={t('Mở bảng công cụ Harness', 'Open Harness tool palette')}
            >
              <Layers size={16} color="var(--accent)" />
            </button>
          </div>
        )}

        {/* 2. Center: ReactFlow Canvas */}
        <div
          ref={reactFlowWrapper}
          style={{ flex: 1, height: '100%', position: 'relative', background: 'var(--bg)' }}
          onDrop={onDrop}
          onDragOver={onDragOver}
        >
          <ReactFlow
            nodes={nodes}
            edges={edges}
            nodeTypes={nodeTypes}
            onNodesChange={onNodesChange}
            onEdgesChange={onEdgesChange}
            onConnect={onConnect}
            onNodeClick={onNodeClick}
            fitView
          >
            <Background color="var(--line-2)" gap={16} />
            <Controls />
          </ReactFlow>

          {nodes.length === 0 && (
            <div
              style={{
                position: 'absolute',
                top: '50%',
                left: '50%',
                transform: 'translate(-50%, -50%)',
                textAlign: 'center',
                pointerEvents: 'none',
                maxWidth: 320,
              }}
            >
              <Sliders size={36} color="var(--muted)" style={{ marginBottom: 8 }} />
              <div style={{ fontWeight: 600, fontSize: 14 }}>{t('Canvas Quy trình Trống', 'Empty Workflow Canvas')}</div>
              <p className="muted" style={{ fontSize: 12, marginTop: 4 }}>
                {t(
                  'Kéo các công cụ harness từ thanh bên trái thả vào đây để xây dựng quy trình kiểm thử tùy chỉnh.',
                  'Drag harness tools from the left palette and drop here to build your custom test pipeline.'
                )}
              </p>
            </div>
          )}
        </div>

        {/* 3. Right Sidebar: Node & Parameter Inspector */}
        {selectedNode && inspectorOpen ? (
          <aside
            style={{
              width: 270,
              background: 'var(--panel)',
              borderLeft: '1px solid var(--line)',
              display: 'flex',
              flexDirection: 'column',
              overflowY: 'auto',
              padding: 14,
              gap: 12,
              flexShrink: 0,
            }}
          >
            <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
              <span style={{ fontSize: 12, fontWeight: 700, color: 'var(--muted)', textTransform: 'uppercase' }}>
                {t('Cấu hình Bước kiểm thử', 'Stage Configuration')}
              </span>
              <button
                type="button"
                className="btn xs ghost"
                onClick={() => setSelectedNodeId(null)}
              >
                ✕
              </button>
            </div>

            <label className="field" style={{ margin: 0 }}>
              <span>{t('Tên hiển thị:', 'Label:')}</span>
              <input
                className="input sm"
                value={String(selectedNode.data.label || '')}
                onChange={(e) => updateSelectedNodeLabel(e.target.value)}
              />
            </label>

            <div style={{ background: 'var(--bg-2)', padding: 10, borderRadius: 6, fontSize: 12 }}>
              <div style={{ fontWeight: 600, color: 'var(--accent)' }}>
                {selectedNodeTool?.name || String(selectedNode.data.tool || '')}
              </div>
              <div className="muted" style={{ fontSize: 11.5, marginTop: 4 }}>
                {selectedNodeTool?.description || ''}
              </div>
            </div>

            {/* Parameter Inputs */}
            <div style={{ display: 'flex', flexDirection: 'column', gap: 8 }}>
              <span style={{ fontSize: 11.5, fontWeight: 600 }}>{t('Tham số kiểm thử:', 'Test Parameters:')}</span>
              {Object.entries((selectedNode.data.params as Record<string, unknown>) || {}).map(
                ([k, v]) => (
                  <label key={k} className="field" style={{ margin: 0 }}>
                    <span style={{ fontSize: 11, fontFamily: 'var(--mono)' }}>{k}</span>
                    <input
                      className="input sm"
                      style={{ fontSize: 12 }}
                      value={String(v)}
                      onChange={(e) => updateSelectedNodeParam(k, e.target.value)}
                    />
                  </label>
                )
              )}
            </div>

            {/* Result Breakdown if Executed */}
            {(() => {
              const nodeRes = selectedNode.data.result as
                | { passed?: boolean; summary?: string; metrics?: Record<string, unknown> }
                | undefined;
              if (!nodeRes) return null;
              return (
                <div
                  style={{
                    background: nodeRes.passed ? 'rgba(16, 185, 129, 0.08)' : 'rgba(239, 68, 68, 0.08)',
                    border: `1px solid ${nodeRes.passed ? 'var(--ok)' : 'var(--err)'}`,
                    borderRadius: 6,
                    padding: 10,
                    fontSize: 12,
                  }}
                >
                  <div style={{ fontWeight: 600, color: nodeRes.passed ? 'var(--ok)' : 'var(--err)' }}>
                    {nodeRes.passed
                      ? t('Đạt tiêu chuẩn kiểm thử', 'Test Passed')
                      : t('Không đạt tiêu chuẩn', 'Test Failed')}
                  </div>
                  <div style={{ fontSize: 11.5, marginTop: 4, lineHeight: 1.4 }}>
                    {nodeRes.summary || ''}
                  </div>
                </div>
              );
            })()}

            <button
              type="button"
              className="btn sm ghost"
              onClick={() => handleDeleteNode(selectedNode.id)}
              style={{ color: 'var(--err)', marginTop: 8 }}
            >
              {t('Xóa node này', 'Delete this node')}
            </button>
          </aside>
        ) : selectedNode && !inspectorOpen ? (
          <div
            style={{
              width: 36,
              background: 'var(--panel)',
              borderLeft: '1px solid var(--line)',
              display: 'flex',
              flexDirection: 'column',
              alignItems: 'center',
              padding: '10px 4px',
              gap: 8,
              flexShrink: 0,
            }}
          >
            <button
              type="button"
              className="icon sm"
              onClick={() => setInspectorOpen(true)}
              title={t('Mở cấu hình bước kiểm thử', 'Open stage configuration')}
            >
              <Sliders size={16} color="var(--accent)" />
            </button>
          </div>
        ) : null}
      </div>

      {/* Execution Report Modal */}
      {showReportModal && latestReport && (
        <div
          style={{
            position: 'absolute',
            bottom: 0,
            left: 0,
            right: 0,
            maxHeight: '45%',
            background: 'var(--panel)',
            borderTop: '2px solid var(--line)',
            boxShadow: '0 -4px 16px rgba(0,0,0,0.15)',
            display: 'flex',
            flexDirection: 'column',
            zIndex: 30,
            padding: 16,
            overflowY: 'auto',
          }}
        >
          <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 12 }}>
            <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
              {latestReport.passed ? (
                <CheckCircle2 size={18} color="var(--ok, #10b981)" />
              ) : (
                <XCircle size={18} color="var(--err, #ef4444)" />
              )}
              <h4 style={{ margin: 0, fontSize: 14 }}>
                {t('Báo cáo Thực thi Harness:', 'Harness Execution Report:')} {latestReport.workflow_name}
              </h4>
              <span className={`chip ${latestReport.passed ? 'ok' : 'err'}`} style={{ fontSize: 11 }}>
                {latestReport.passed ? t('Hoàn thành xuất sắc', 'Passed') : t('Cần rà soát lại', 'Action Needed')}
              </span>
            </div>
            <div style={{ display: 'flex', alignItems: 'center', gap: 10 }}>
              <span className="muted" style={{ fontSize: 12 }}>
                {t('Tổng thời gian:', 'Duration:')} <b>{latestReport.total_duration_s}s</b>
              </span>
              <button
                type="button"
                className="btn xs ghost"
                onClick={() => setShowReportModal(false)}
              >
                ✕ {t('Đóng', 'Close')}
              </button>
            </div>
          </div>

          {/* Node Results Table */}
          <table style={{ width: '100%', fontSize: 12, borderCollapse: 'collapse' }}>
            <thead>
              <tr style={{ borderBottom: '1px solid var(--line)', color: 'var(--muted)', textAlign: 'left' }}>
                <th style={{ padding: '6px 8px' }}>{t('Bước kiểm thử', 'Stage')}</th>
                <th style={{ padding: '6px 8px' }}>{t('Công cụ Harness', 'Harness Tool')}</th>
                <th style={{ padding: '6px 8px' }}>{t('Trạng thái', 'Status')}</th>
                <th style={{ padding: '6px 8px' }}>{t('Thời gian', 'Time')}</th>
                <th style={{ padding: '6px 8px' }}>{t('Chi tiết kết quả & Điểm số', 'Detailed Results & Metrics')}</th>
              </tr>
            </thead>
            <tbody>
              {Object.values(latestReport.node_results).map((nr) => (
                <tr key={nr.node_id} style={{ borderBottom: '1px solid var(--line-2)' }}>
                  <td style={{ padding: '6px 8px', fontWeight: 600 }}>{nr.label}</td>
                  <td style={{ padding: '6px 8px', color: 'var(--accent)' }}>{nr.tool_name}</td>
                  <td style={{ padding: '6px 8px' }}>
                    <span className={`chip ${nr.passed ? 'ok' : 'err'}`} style={{ fontSize: 10.5 }}>
                      {nr.passed ? t('Đạt', 'Pass') : t('Lỗi', 'Fail')}
                    </span>
                  </td>
                  <td style={{ padding: '6px 8px', color: 'var(--muted)' }}>{nr.duration_s}s</td>
                  <td style={{ padding: '6px 8px', fontSize: 11.5, lineHeight: 1.4 }}>{nr.summary}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
    </div>
  );
};
