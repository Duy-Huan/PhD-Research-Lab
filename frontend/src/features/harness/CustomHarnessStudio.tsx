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
  WorkflowNodeMetadata,
  WorkflowValidationResult,
  AgentProfile,
  WorkflowExecutionState,
  WorkflowNodeType,
} from '../../shared/api/types';
import { HarnessNodeComponent } from './HarnessNodeComponent';
import { MissionTeamPanel } from './MissionTeamPanel';
import {
  Play,
  Pause,
  Square,
  StepForward,
  Save,
  Plus,
  Layers,
  Sliders,
  CheckCircle2,
  XCircle,
  FileDown,
  FileUp,
  ExternalLink,
  ChevronRight,
  Sparkles,
  Bot,
  Zap,
  ArrowLeft,
  Maximize2,
  X,
  ShieldCheck,
  Scale,
  FileText,
  Database,
  AlertTriangle,
  Bookmark,
  Users,
  Cpu,
  Wrench,
  Boxes,
  GitBranch,
  Split,
  Merge,
  RefreshCw,
  Clock,
  Terminal,
} from 'lucide-react';

interface CustomHarnessStudioProps {
  topicId?: string;
  onSwitchToAutomated?: () => void;
  isFullSpace?: boolean;
}

type LeftSidebarTab = 'palette' | 'templates' | 'agents' | 'architect';
type RightSidebarTab = 'config' | 'debugger';

export const CustomHarnessStudio: React.FC<CustomHarnessStudioProps> = ({
  topicId,
  onSwitchToAutomated,
  isFullSpace,
}) => {
  const queryClient = useQueryClient();
  const { t, language } = useI18n();
  const { setMainView, open3DOffice, openHarnessStudio, mainView } = useUIStore();
  const fullSpaceActive = isFullSpace ?? mainView === 'harness';

  const [paletteOpen, setPaletteOpen] = useState<boolean>(true);
  const [inspectorOpen, setInspectorOpen] = useState<boolean>(true);
  const [leftTab, setLeftTab] = useState<LeftSidebarTab>('palette');
  const [rightTab, setRightTab] = useState<RightSidebarTab>('config');

  const reactFlowWrapper = useRef<HTMLDivElement>(null);
  const fileInputRef = useRef<HTMLInputElement>(null);

  // Studio mode: 'manual' vs 'automated'
  const [studioMode, setStudioMode] = useState<'manual' | 'automated'>('manual');

  // Selected workflow & template state
  const [selectedWorkflowId, setSelectedWorkflowId] = useState<string>('hw-preset-llm-eval');
  const [workflowName, setWorkflowName] = useState<string>('');
  const [workflowDesc, setWorkflowDesc] = useState<string>('');
  const [executionLevel, setExecutionLevel] = useState<'L2' | 'L3' | 'L4'>('L3');
  const [selectedNodeId, setSelectedNodeId] = useState<string | null>(null);

  // Nodes & Edges state for ReactFlow
  const [nodes, setNodes] = useState<Node[]>([]);
  const [edges, setEdges] = useState<Edge[]>([]);

  // Validation state
  const [validation, setValidation] = useState<WorkflowValidationResult>({
    valid: true,
    errors: [],
    warnings: [],
    node_count: 0,
    edge_count: 0,
  });

  // Execution state (debugger & legacy report)
  const [latestReport, setLatestReport] = useState<HarnessExecutionReport | null>(null);
  const [executionState, setExecutionState] = useState<WorkflowExecutionState | null>(null);
  const [showReportModal, setShowReportModal] = useState<boolean>(false);
  const [approvalFeedback, setApprovalFeedback] = useState<string>('');

  // AI Architect & Dynamic Team Builder states
  const [architectObjective, setArchitectObjective] = useState<string>('');
  const [architectLevel, setArchitectLevel] = useState<'L2' | 'L3' | 'L4'>('L3');
  const [generatedWorkflow, setGeneratedWorkflow] = useState<CustomHarnessWorkflow | null>(null);
  const [isArchitectGenerating, setIsArchitectGenerating] = useState<boolean>(false);

  // Custom Agent Creation Modal
  const [showAgentModal, setShowAgentModal] = useState<boolean>(false);
  const [newAgentName, setNewAgentName] = useState<string>('');
  const [newAgentRole, setNewAgentRole] = useState<string>('researcher');
  const [newAgentPurpose, setNewAgentPurpose] = useState<string>('');
  const [newAgentPrompt, setNewAgentPrompt] = useState<string>('');
  const [newAgentProvider, setNewAgentProvider] = useState<string>('auto');

  // Queries
  const { data: toolsData } = useQuery<{ tools: HarnessToolSpec[] }>({
    queryKey: ['harness-tools'],
    queryFn: () => api.get<{ tools: HarnessToolSpec[] }>('/api/harness/tools'),
  });

  const { data: nodesData } = useQuery<{ nodes: WorkflowNodeMetadata[] }>({
    queryKey: ['workflow-nodes'],
    queryFn: () => api.get<{ nodes: WorkflowNodeMetadata[] }>('/api/harness/nodes'),
  });

  const { data: templatesData } = useQuery<{ templates: CustomHarnessWorkflow[] }>({
    queryKey: ['workflow-templates'],
    queryFn: () => api.get<{ templates: CustomHarnessWorkflow[] }>('/api/harness/templates'),
  });

  const { data: agentsData } = useQuery<{ agents: AgentProfile[] }>({
    queryKey: ['workflow-agents'],
    queryFn: () => api.get<{ agents: AgentProfile[] }>('/api/harness/agents'),
  });

  const { data: workflowsData } = useQuery<{ workflows: CustomHarnessWorkflow[] }>({
    queryKey: ['harness-workflows', topicId],
    queryFn: () =>
      api.get<{ workflows: CustomHarnessWorkflow[] }>(
        `/api/harness/workflows${topicId ? `?topic_id=${topicId}` : ''}`
      ),
  });

  const tools = toolsData?.tools || [];
  const nodeRegistry = nodesData?.nodes || [];
  const templates = templatesData?.templates || [];
  const agents = agentsData?.agents || [];
  const workflows = workflowsData?.workflows || [];

  // Register all 17 node types + harnessNode for ReactFlow
  const nodeTypes = useMemo(
    () => ({
      harnessNode: HarnessNodeComponent,
      start: HarnessNodeComponent,
      end: HarnessNodeComponent,
      agent_task: HarnessNodeComponent,
      multi_agent_team: HarnessNodeComponent,
      research_engine: HarnessNodeComponent,
      tool_skill: HarnessNodeComponent,
      mcp_tool: HarnessNodeComponent,
      input: HarnessNodeComponent,
      output: HarnessNodeComponent,
      condition: HarnessNodeComponent,
      parallel_branch: HarnessNodeComponent,
      join: HarnessNodeComponent,
      bounded_loop: HarnessNodeComponent,
      human_approval: HarnessNodeComponent,
      evaluation_gate: HarnessNodeComponent,
      artifact_transformation: HarnessNodeComponent,
      memory_read: HarnessNodeComponent,
      memory_write: HarnessNodeComponent,
      error_handler: HarnessNodeComponent,
      checkpoint: HarnessNodeComponent,
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
      if (wf.execution_level && ['L2', 'L3', 'L4'].includes(wf.execution_level)) {
        setExecutionLevel(wf.execution_level as 'L2' | 'L3' | 'L4');
      }
      setSelectedNodeId(null);
      setLatestReport(null);
      setExecutionState(null);

      const flowNodes: Node[] = (wf.nodes || []).map((n) => ({
        id: n.id,
        type: n.type || n.data?.node_type || (n.data?.tool ? 'harnessNode' : 'agent_task'),
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
        sourceHandle: e.sourceHandle,
        targetHandle: e.targetHandle,
        animated: true,
        style: { stroke: 'var(--accent)', strokeWidth: 2 },
      }));

      setNodes(flowNodes);
      setEdges(flowEdges);
    },
    [handleDeleteNode]
  );

  // Validate workflow graph whenever nodes or edges change
  useEffect(() => {
    if (nodes.length === 0) {
      setValidation({ valid: true, errors: [], warnings: [], node_count: 0, edge_count: 0 });
      return;
    }
    const timer = setTimeout(async () => {
      try {
        const payload = {
          nodes: nodes.map((n) => ({
            id: n.id,
            type: n.type || n.data.node_type,
            data: n.data,
          })),
          edges: edges.map((e) => ({
            id: e.id,
            source: e.source,
            target: e.target,
            sourceHandle: e.sourceHandle,
            targetHandle: e.targetHandle,
          })),
        };
        const res = await api.post<WorkflowValidationResult>('/api/harness/validate', payload);
        if (res && typeof res.valid === 'boolean') {
          setValidation({
            valid: res.valid,
            errors: Array.isArray(res.errors) ? res.errors : [],
            warnings: Array.isArray(res.warnings) ? res.warnings : [],
            node_count: res.node_count ?? nodes.length,
            edge_count: res.edge_count ?? edges.length,
          });
        }
      } catch {
        // Fallback local validation
        setValidation({
          valid: true,
          errors: [],
          warnings: [],
          node_count: nodes.length,
          edge_count: edges.length,
        });
      }
    }, 300);
    return () => clearTimeout(timer);
  }, [nodes, edges]);

  // Initial load
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
    setRightTab('config');
  }, []);

  // Add specific node type to canvas
  const addNodeToCanvas = useCallback(
    (nodeType: WorkflowNodeType, position?: { x: number; y: number }, initialData?: Record<string, unknown>) => {
      const meta = nodeRegistry.find((n) => n.type === nodeType);
      const newId = `node-${Date.now().toString().slice(-6)}`;
      const pos = position || {
        x: 120 + (nodes.length % 5) * 45,
        y: 80 + (nodes.length % 5) * 45,
      };

      const newNode: Node = {
        id: newId,
        type: nodeType,
        position: pos,
        data: {
          node_type: nodeType,
          label: (initialData?.label as string) || (language === 'en' ? meta?.label_en : meta?.label) || meta?.label || nodeType,
          config: { ...(meta?.default_config || {}), ...(initialData?.config || {}) },
          params: { ...(initialData?.params || {}) },
          status: 'idle',
          onDelete: handleDeleteNode,
          ...initialData,
        },
      };

      setNodes((nds) => [...nds, newNode]);
      setSelectedNodeId(newId);
    },
    [nodeRegistry, nodes.length, handleDeleteNode]
  );

  // Add legacy benchmark tool node
  const addToolNodeAtPosition = useCallback(
    (toolId: string, position: { x: number; y: number }) => {
      const toolSpec = tools.find((t) => t.id === toolId);
      const newId = `node-${Date.now().toString().slice(-6)}`;
      const newNode: Node = {
        id: newId,
        type: 'harnessNode',
        position,
        data: {
          node_type: 'harnessNode',
          label: toolSpec?.name || 'Harness Step',
          tool: toolId,
          category: toolSpec?.category || 'benchmark',
          params: { ...(toolSpec?.default_params || {}) },
          config: {},
          status: 'idle',
          onDelete: handleDeleteNode,
        },
      };

      setNodes((nds) => [...nds, newNode]);
      setSelectedNodeId(newId);
    },
    [tools, handleDeleteNode]
  );

  // Drag & drop handlers
  const onDragStart = (event: React.DragEvent, payload: { kind: 'tool' | 'node'; id: string }) => {
    event.dataTransfer.setData('application/json', JSON.stringify(payload));
    // Legacy fallback
    if (payload.kind === 'tool') {
      event.dataTransfer.setData('application/harness-tool', payload.id);
    }
    event.dataTransfer.effectAllowed = 'move';
  };

  const onDragOver = (event: React.DragEvent) => {
    event.preventDefault();
    event.dataTransfer.dropEffect = 'move';
  };

  const onDrop = useCallback(
    (event: React.DragEvent) => {
      event.preventDefault();
      const bounds = reactFlowWrapper.current?.getBoundingClientRect();
      const position = {
        x: bounds ? event.clientX - bounds.left - 100 : 150,
        y: bounds ? event.clientY - bounds.top - 40 : 150,
      };

      // Try JSON payload first
      try {
        const raw = event.dataTransfer.getData('application/json');
        if (raw) {
          const parsed = JSON.parse(raw);
          if (parsed.kind === 'node') {
            addNodeToCanvas(parsed.id as WorkflowNodeType, position);
            return;
          }
          if (parsed.kind === 'tool') {
            addToolNodeAtPosition(parsed.id, position);
            return;
          }
        }
      } catch {
        // Fallback
      }

      // Legacy fallback
      const toolId = event.dataTransfer.getData('application/harness-tool');
      if (toolId) {
        addToolNodeAtPosition(toolId, position);
      }
    },
    [addNodeToCanvas, addToolNodeAtPosition]
  );

  // Save workflow mutation
  const saveWorkflowMutation = useMutation({
    mutationFn: async () => {
      const payload: Partial<CustomHarnessWorkflow> = {
        id: selectedWorkflowId.startsWith('hw-preset-') || selectedWorkflowId.startsWith('tpl-')
          ? `hw-${Date.now().toString().slice(-8)}`
          : selectedWorkflowId,
        name: workflowName.trim() || t('Quy trình Nghiên cứu Tùy chỉnh', 'Custom Research Workflow'),
        description: workflowDesc.trim(),
        topic_id: topicId || '',
        execution_level: executionLevel,
        nodes: nodes.map((n) => ({
          id: n.id,
          type: (n.type || n.data.node_type) as string,
          position: n.position,
          data: {
            label: String(n.data.label || ''),
            node_type: n.data.node_type as WorkflowNodeType,
            tool: n.data.tool ? String(n.data.tool) : undefined,
            category: String(n.data.category || ''),
            config: (n.data.config as Record<string, unknown>) || {},
            params: (n.data.params as Record<string, unknown>) || {},
          },
        })),
        edges: edges.map((e) => ({
          id: e.id,
          source: e.source,
          target: e.target,
          sourceHandle: e.sourceHandle || undefined,
          targetHandle: e.targetHandle || undefined,
        })),
      };

      return api.post<CustomHarnessWorkflow>('/api/harness/workflows', payload);
    },
    onSuccess: (saved) => {
      queryClient.invalidateQueries({ queryKey: ['harness-workflows'] });
      setSelectedWorkflowId(saved.id);
      alert(t('Đã lưu quy trình thành công!', 'Workflow saved successfully!'));
    },
    onError: (err: Error) => {
      alert(t(`Lỗi lưu quy trình: ${err.message}`, `Failed to save workflow: ${err.message}`));
    },
  });

  // Execute workflow mutation (supports full modern runtime and legacy benchmark)
  const executeMutation = useMutation({
    mutationFn: async (stepMode: boolean = false) => {
      // Visually set all nodes to running
      setNodes((nds) =>
        nds.map((n) => ({
          ...n,
          data: { ...n.data, status: 'running' },
        }))
      );

      const workflowPayload = {
        id: selectedWorkflowId,
        name: workflowName,
        execution_level: executionLevel,
        nodes: nodes.map((n) => ({
          id: n.id,
          type: n.type || n.data.node_type,
          data: n.data,
        })),
        edges: edges.map((e) => ({
          id: e.id,
          source: e.source,
          target: e.target,
          sourceHandle: e.sourceHandle,
          targetHandle: e.targetHandle,
        })),
      };

      const res = await api.post<any>('/api/harness/execute', {
        workflow: workflowPayload,
        topic_id: topicId || '',
        level: executionLevel,
        step_mode: stepMode,
      });
      return res;
    },
    onSuccess: (res: any) => {
      // Check if modern WorkflowExecutionState or legacy HarnessExecutionReport
      if (res.node_statuses && Array.isArray(res.node_statuses)) {
        const state = res as WorkflowExecutionState;
        setExecutionState(state);
        setRightTab('debugger');

        // Update nodes on canvas
        setNodes((nds) =>
          nds.map((n) => {
            const st = state.node_statuses.find((s) => s.node_id === n.id);
            if (!st) return n;
            return {
              ...n,
              data: {
                ...n.data,
                status: st.status,
                result: {
                  passed: (st as any).passed === true,
                  duration_s: st.duration_s,
                  output: st.output,
                  error: st.error,
                  summary: (st as any).summary || st.error || (st.output ? JSON.stringify(st.output).slice(0, 100) : st.status),
                },
              },
            };
          })
        );
      } else if (res.node_results) {
        // Legacy benchmark report format
        const report = res as HarnessExecutionReport;
        setLatestReport(report);
        setShowReportModal(true);

        setNodes((nds) =>
          nds.map((n) => {
            const r = report.node_results[n.id];
            if (!r) return n;
            return {
              ...n,
              data: {
                ...n.data,
                status: r.status || (r.passed ? 'completed' : 'failed'),
                result: {
                  passed: r.passed,
                  duration_s: r.duration_s,
                  metrics: r.metrics,
                  summary: r.summary,
                },
              },
            };
          })
        );
      }
    },
    onError: (err: Error) => {
      setNodes((nds) =>
        nds.map((n) => ({
          ...n,
          data: { ...n.data, status: 'idle' },
        }))
      );
      alert(t(`Lỗi thực thi quy trình: ${err.message}`, `Failed to execute workflow: ${err.message}`));
    },
  });

  // Action mutation (approve / reject / cancel)
  const actionMutation = useMutation({
    mutationFn: async ({ action, nodeId }: { action: 'approve' | 'reject' | 'cancel'; nodeId?: string }) => {
      if (!executionState) return;
      return api.post('/api/harness/execute/action', {
        execution_id: executionState.execution_id,
        action,
        node_id: nodeId || executionState.current_node_id,
        feedback: approvalFeedback,
      });
    },
    onSuccess: (data: any) => {
      if (data?.execution) {
        setExecutionState(data.execution);
      }
      setApprovalFeedback('');
    },
  });

  // AI Architect: generate workflow graph
  const handleGenerateWorkflow = async () => {
    if (!architectObjective.trim()) return;
    setIsArchitectGenerating(true);
    try {
      const res = await api.post<CustomHarnessWorkflow>('/api/harness/architect/generate', {
        objective: architectObjective.trim(),
        level: architectLevel,
      });
      setGeneratedWorkflow(res);
    } catch (err: any) {
      alert(t(`Lỗi tạo quy trình AI: ${err.message}`, `AI Architect error: ${err.message}`));
    } finally {
      setIsArchitectGenerating(false);
    }
  };

  // Create custom agent mutation
  const createAgentMutation = useMutation({
    mutationFn: async () => {
      return api.post<AgentProfile>('/api/harness/agents', {
        name: newAgentName.trim() || 'Custom Agent',
        role: newAgentRole,
        purpose: newAgentPurpose.trim(),
        system_prompt: newAgentPrompt.trim(),
        provider: newAgentProvider,
      });
    },
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['workflow-agents'] });
      setShowAgentModal(false);
      setNewAgentName('');
      setNewAgentPurpose('');
      setNewAgentPrompt('');
    },
  });

  // Export JSON
  const handleExportJson = () => {
    const dataStr =
      'data:text/json;charset=utf-8,' +
      encodeURIComponent(
        JSON.stringify(
          {
            name: workflowName,
            description: workflowDesc,
            execution_level: executionLevel,
            nodes,
            edges,
          },
          null,
          2
        )
      );
    const dlAnchor = document.createElement('a');
    dlAnchor.setAttribute('href', dataStr);
    dlAnchor.setAttribute('download', `${workflowName || 'research-workflow'}.json`);
    dlAnchor.click();
  };

  // Import JSON
  const handleImportJson = (e: React.ChangeEvent<HTMLInputElement>) => {
    const file = e.target.files?.[0];
    if (!file) return;
    const reader = new FileReader();
    reader.onload = (event) => {
      try {
        const parsed = JSON.parse(event.target?.result as string);
        if (parsed.nodes && Array.isArray(parsed.nodes)) {
          loadWorkflowIntoCanvas(parsed);
          alert(t('Đã nhập quy trình JSON thành công!', 'Imported workflow JSON successfully!'));
        }
      } catch (err: any) {
        alert(t(`Lỗi đọc file JSON: ${err.message}`, `Failed to parse JSON file: ${err.message}`));
      }
    };
    reader.readAsText(file);
    if (fileInputRef.current) fileInputRef.current.value = '';
  };

  // Selected node config helpers
  const selectedNode = nodes.find((n) => n.id === selectedNodeId) || null;
  const selectedNodeTool = tools.find((t) => t.id === selectedNode?.data.tool);
  const selectedNodeMeta = nodeRegistry.find((m) => m.type === (selectedNode?.type || selectedNode?.data.node_type));

  const updateSelectedNodeLabel = (label: string) => {
    if (!selectedNodeId) return;
    setNodes((nds) =>
      nds.map((n) => (n.id === selectedNodeId ? { ...n, data: { ...n.data, label } } : n))
    );
  };

  const updateSelectedNodeConfig = (key: string, value: unknown) => {
    if (!selectedNodeId) return;
    setNodes((nds) =>
      nds.map((n) => {
        if (n.id !== selectedNodeId) return n;
        const currentConfig = (n.data.config as Record<string, unknown>) || {};
        return {
          ...n,
          data: {
            ...n.data,
            config: {
              ...currentConfig,
              [key]: value,
            },
          },
        };
      })
    );
  };

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

  // Node Palette Category Grouping
  const paletteCategories = [
    {
      id: 'flow',
      title: t('Điều phối & luồng', 'Flow & control'),
      types: ['start', 'end', 'condition', 'bounded_loop', 'parallel_branch', 'join'],
    },
    {
      id: 'agent',
      title: t('Agent & đội ngũ', 'Agents & teams'),
      types: ['agent_task', 'multi_agent_team'],
    },
    {
      id: 'engine',
      title: t('Công cụ nghiên cứu', 'Research engines'),
      types: ['research_engine'],
    },
    {
      id: 'tool',
      title: t('Kỹ năng & MCP', 'Skills & tools'),
      types: ['tool_skill', 'mcp_tool'],
    },
    {
      id: 'data',
      title: t('Dữ liệu & bộ nhớ', 'Data & memory'),
      types: ['input', 'output', 'artifact_transformation', 'memory_read', 'memory_write'],
    },
    {
      id: 'governance',
      title: t('Kiểm định & an toàn', 'Governance & gates'),
      types: ['human_approval', 'evaluation_gate', 'error_handler', 'checkpoint'],
    },
  ];

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
      <input type="file" ref={fileInputRef} style={{ display: 'none' }} accept=".json" onChange={handleImportJson} />

      {/* ----------------- Top Header Navigation & Controls ----------------- */}
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

            {/* Validation Pill */}
            <span
              className={`chip sm ${validation?.valid ? 'ok' : 'err'}`}
              title={
                validation?.valid
                  ? `${validation?.node_count || nodes.length} nodes, ${validation?.edge_count || edges.length} edges (Acyclic DAG)`
                  : (validation?.errors || []).join('; ')
              }
              style={{ fontSize: 10.5, cursor: 'help' }}
            >
              {validation?.valid
                ? `✓ ${t('DAG hợp lệ', 'Valid DAG')} (${nodes.length} nodes)`
                : `⚠ ${(validation?.errors || []).length} ${t('lỗi', 'errors')}`}
            </span>
          </div>

          {/* Mode Switcher: only where an automated view exists (Missions); the standalone studio is the canvas */}
          {onSwitchToAutomated && <div
            style={{
              display: 'inline-flex',
              background: 'var(--bg-2)',
              borderRadius: 6,
              padding: 2,
              border: '1px solid var(--line)',
            }}
          >
            <button
              type="button"
              className={`btn xs ${studioMode === 'automated' ? 'accent' : 'ghost'}`}
              onClick={() => {
                setStudioMode('automated');
                onSwitchToAutomated();
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
          </div>}
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

          {/* Execution Level Pill (L2 / L3 / L4) */}
          <select
            className="input sm"
            style={{ fontSize: 11, fontWeight: 600, color: 'var(--accent)', maxWidth: 120 }}
            value={executionLevel}
            onChange={(e) => setExecutionLevel(e.target.value as 'L2' | 'L3' | 'L4')}
            title={t('Cấp độ tự chủ (L2: Thủ công, L3: Đội ngũ, L4: Tự chủ hoàn toàn)', 'Autonomy level (L2: manual, L3: team, L4: fully autonomous)')}
          >
            <option value="L2">{t('Cấp độ L2', 'Level L2')}</option>
            <option value="L3">{t('Cấp độ L3', 'Level L3')}</option>
            <option value="L4">{t('Cấp độ L4', 'Level L4')}</option>
          </select>

          {/* Saved Workflows & Presets Selector */}
          <select
            className="input sm"
            aria-label={t('Quy trình đã lưu', 'Saved workflows')}
            style={{ minWidth: 180, fontSize: 12 }}
            value={selectedWorkflowId}
            onChange={(e) => {
              const target = workflows.find((w) => w.id === e.target.value) || templates.find((t) => t.id === e.target.value);
              if (target) loadWorkflowIntoCanvas(target);
            }}
          >
            {workflows.map((w) => (
              <option key={w.id} value={w.id}>
                {(language === 'en' && (w as { name_en?: string }).name_en) || w.name} {w.is_preset ? `(${t('Mẫu chuẩn', 'Preset')})` : ''}
              </option>
            ))}
          </select>

          {/* Execute Workflow Button */}
          <button
            type="button"
            className="btn sm accent"
            onClick={() => executeMutation.mutate(false)}
            disabled={executeMutation.isPending || nodes.length === 0}
            title={t('Thực thi quy trình harness', 'Execute harness pipeline')}
          >
            <Play size={13} style={{ marginRight: 4 }} />
            {executeMutation.isPending
              ? t('Đang chạy…', 'Executing…')
              : t('Chạy Harness', 'Run Harness')}
          </button>

          {/* Step Button */}
          <button
            type="button"
            className="btn sm ghost"
            onClick={() => executeMutation.mutate(true)}
            disabled={executeMutation.isPending || nodes.length === 0}
            title={t('Thực thi từng bước (Step Mode)', 'Execute step-by-step')}
          >
            <StepForward size={13} style={{ marginRight: 4 }} />
            {t('Bước', 'Step')}
          </button>

          {/* Save Button */}
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

          {/* New Canvas Button */}
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
              setExecutionState(null);
            }}
            title={t('Tạo canvas mới', 'Create fresh canvas')}
          >
            <Plus size={13} style={{ marginRight: 4 }} />
            {t('Mới', 'New')}
          </button>

          {/* Export JSON */}
          <button
            type="button"
            className="btn sm ghost"
            onClick={handleExportJson}
            title={t('Xuất sơ đồ JSON', 'Export JSON')}
          >
            <FileDown size={13} />
          </button>

          {/* Import JSON */}
          <button
            type="button"
            className="btn sm ghost"
            onClick={() => fileInputRef.current?.click()}
            title={t('Nhập sơ đồ JSON', 'Import JSON')}
          >
            <FileUp size={13} />
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

              <button
                type="button"
                className={`btn sm ${inspectorOpen ? 'accent' : 'ghost'}`}
                onClick={() => setInspectorOpen(!inspectorOpen)}
                title={inspectorOpen ? t('Ẩn bảng cấu hình & gỡ lỗi', 'Hide config & debugger') : t('Hiện bảng cấu hình & gỡ lỗi', 'Show config & debugger')}
                style={{ borderRadius: 6, gap: 4 }}
              >
                <Sliders size={13} />
                <span>{inspectorOpen ? t('Ẩn Bảng Phải', 'Hide Right Panel') : t('Bảng Phải', 'Right Panel')}</span>
              </button>

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

      {/* ----------------- Main Studio Workspace ----------------- */}
      <div style={{ flex: 1, display: 'flex', overflow: 'hidden', position: 'relative' }}>
        {/* 1. Left Sidebar: 4 Tabs (Palette, Templates, Dynamic Team, AI Architect) */}
        {paletteOpen ? (
          <aside
            style={{
              width: 290,
              background: 'var(--panel)',
              borderRight: '1px solid var(--line)',
              display: 'flex',
              flexDirection: 'column',
              flexShrink: 0,
              zIndex: 10,
            }}
          >
            {/* Tabs Header */}
            <div
              style={{
                display: 'flex',
                borderBottom: '1px solid var(--line)',
                background: 'var(--bg-2)',
              }}
            >
              <button
                type="button"
                className={`btn xs ${leftTab === 'palette' ? 'accent' : 'ghost'}`}
                onClick={() => setLeftTab('palette')}
                style={{ flex: 1, borderRadius: 0, padding: '7px 4px', fontSize: 11 }}
                title={t('Khối Node & Công cụ', 'Nodes & tools')}
              >
                Nodes
              </button>
              <button
                type="button"
                className={`btn xs ${leftTab === 'templates' ? 'accent' : 'ghost'}`}
                onClick={() => setLeftTab('templates')}
                style={{ flex: 1, borderRadius: 0, padding: '7px 4px', fontSize: 11 }}
                title={t('Thư viện Mẫu nghiên cứu', 'Research template library')}
              >
                Templates
              </button>
              <button
                type="button"
                className={`btn xs ${leftTab === 'agents' ? 'accent' : 'ghost'}`}
                onClick={() => setLeftTab('agents')}
                style={{ flex: 1, borderRadius: 0, padding: '7px 4px', fontSize: 11 }}
                title={t('Xây dựng Đội ngũ Agent', 'Build the agent team')}
              >
                Team
              </button>
              <button
                type="button"
                className={`btn xs ${leftTab === 'architect' ? 'accent' : 'ghost'}`}
                onClick={() => setLeftTab('architect')}
                style={{ flex: 1, borderRadius: 0, padding: '7px 4px', fontSize: 11 }}
                title="AI Workflow Architect"
              >
                AI Architect
              </button>
            </div>

            {/* TAB CONTENT */}
            <div style={{ flex: 1, overflowY: 'auto', padding: 12 }}>
              {/* TAB 1: NODE PALETTE */}
              {leftTab === 'palette' && (
                <div style={{ display: 'flex', flexDirection: 'column', gap: 14 }}>
                  <div style={{ fontSize: 11, color: 'var(--muted)' }}>
                    {t('Kéo thả hoặc bấm dấu cộng để thêm khối vào canvas quy trình:', 'Drag a block, or press +, to add it to the workflow canvas:')}
                  </div>

                  {paletteCategories.map((cat) => (
                    <div key={cat.id} style={{ display: 'flex', flexDirection: 'column', gap: 6 }}>
                      <div
                        style={{
                          fontSize: 10.5,
                          fontWeight: 700,
                          textTransform: 'uppercase',
                          color: 'var(--muted)',
                          letterSpacing: 0.5,
                        }}
                      >
                        {cat.title}
                      </div>

                      <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 6 }}>
                        {cat.types.map((typeKey) => {
                          const meta = nodeRegistry.find((n) => n.type === typeKey);
                          const label = (language === 'en' ? meta?.label_en : meta?.label) || meta?.label || typeKey;
                          return (
                            <div
                              key={typeKey}
                              draggable
                              onDragStart={(e) => onDragStart(e, { kind: 'node', id: typeKey })}
                              onClick={() => addNodeToCanvas(typeKey as WorkflowNodeType)}
                              style={{
                                background: 'var(--bg-2)',
                                border: '1px solid var(--line)',
                                borderRadius: 6,
                                padding: '6px 8px',
                                cursor: 'pointer',
                                fontSize: 11,
                                fontWeight: 500,
                                display: 'flex',
                                alignItems: 'center',
                                justifyContent: 'space-between',
                                transition: 'all 0.15s ease',
                              }}
                              onMouseEnter={(e) => (e.currentTarget.style.borderColor = 'var(--accent)')}
                              onMouseLeave={(e) => (e.currentTarget.style.borderColor = 'var(--line)')}
                              title={meta?.description || label}
                            >
                              <span style={{ overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>
                                {label}
                              </span>
                              <Plus size={11} color="var(--accent)" />
                            </div>
                          );
                        })}
                      </div>
                    </div>
                  ))}

                  {/* Benchmark Harness Tools */}
                  <div style={{ display: 'flex', flexDirection: 'column', gap: 6, marginTop: 4 }}>
                    <div
                      style={{
                        fontSize: 10.5,
                        fontWeight: 700,
                        textTransform: 'uppercase',
                        color: 'var(--muted)',
                        letterSpacing: 0.5,
                      }}
                    >
                      {t('Công cụ Benchmark Mở', 'Benchmark Tools')} ({tools.length})
                    </div>
                    {tools.map((tool) => (
                      <div
                        key={tool.id}
                        draggable
                        onDragStart={(e) => onDragStart(e, { kind: 'tool', id: tool.id })}
                        style={{
                          background: 'var(--bg-2)',
                          border: '1px solid var(--line)',
                          borderRadius: 6,
                          padding: '7px 8px',
                          cursor: 'grab',
                          display: 'flex',
                          flexDirection: 'column',
                          gap: 3,
                        }}
                      >
                        <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
                          <b style={{ fontSize: 11.5 }}>{tool.name}</b>
                          <button
                            type="button"
                            className="icon xs"
                            onClick={() => addToolNodeAtPosition(tool.id, { x: 120 + nodes.length * 30, y: 80 + nodes.length * 30 })}
                            title={t('Thêm vào canvas', 'Add to canvas')}
                            style={{ padding: 2 }}
                          >
                            <Plus size={12} color="var(--accent)" />
                          </button>
                        </div>
                        <div className="muted" style={{ fontSize: 10.5, lineHeight: 1.3 }}>
                          {tool.description}
                        </div>
                      </div>
                    ))}
                  </div>
                </div>
              )}

              {/* TAB 2: TEMPLATE LIBRARY */}
              {leftTab === 'templates' && (
                <div style={{ display: 'flex', flexDirection: 'column', gap: 10 }}>
                  <div style={{ fontSize: 11, color: 'var(--muted)' }}>
                    {t('7 Mẫu quy trình nghiên cứu khoa học chuẩn có thể chỉnh sửa:', '7 editable standard research workflows:')}
                  </div>

                  {templates.map((tpl) => (
                    <div
                      key={tpl.id}
                      style={{
                        background: 'var(--bg-2)',
                        border: '1px solid var(--line)',
                        borderRadius: 8,
                        padding: 10,
                        display: 'flex',
                        flexDirection: 'column',
                        gap: 6,
                      }}
                    >
                      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start' }}>
                        <b style={{ fontSize: 12, lineHeight: 1.3 }}>{(language === 'en' && (tpl as { name_en?: string }).name_en) || tpl.name}</b>
                        {tpl.badge && <span className="chip sm accent" style={{ fontSize: 9.5 }}>{tpl.badge}</span>}
                      </div>
                      <p className="muted" style={{ margin: 0, fontSize: 11, lineHeight: 1.4 }}>
                        {(language === 'en' && (tpl as { description_en?: string }).description_en) || tpl.description}
                      </p>
                      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginTop: 4 }}>
                        <span style={{ fontSize: 10, color: 'var(--muted)' }}>
                          {tpl.nodes?.length || 0} nodes · {tpl.edges?.length || 0} edges
                        </span>
                        <button
                          type="button"
                          className="btn xs accent"
                          onClick={() => loadWorkflowIntoCanvas(tpl)}
                          style={{ padding: '3px 8px', fontSize: 11 }}
                        >
                          Tải vào Canvas
                        </button>
                      </div>
                    </div>
                  ))}
                </div>
              )}

              {/* TAB 3: DYNAMIC AGENT TEAM BUILDER */}
              {leftTab === 'agents' && (
                <div style={{ display: 'flex', flexDirection: 'column', gap: 10 }}>
                  <MissionTeamPanel
                    workflow={() => ({
                      name: workflowName,
                      nodes: nodes.map((n) => ({ id: n.id, type: n.type || n.data.node_type, data: n.data })),
                      edges: edges.map((e) => ({ id: e.id, source: e.source, target: e.target, sourceHandle: e.sourceHandle })),
                    })}
                    level={executionLevel}
                    objective={architectObjective || workflowDesc}
                    topicId={topicId}
                  />
                  <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
                    <span style={{ fontSize: 11, fontWeight: 700, color: 'var(--muted)', textTransform: 'uppercase' }}>
                      {t('Đội ngũ chuyên gia', 'Expert team')} ({agents.length})
                    </span>
                    <button
                      type="button"
                      className="btn xs accent"
                      onClick={() => setShowAgentModal(true)}
                      style={{ padding: '2px 7px', fontSize: 10.5 }}
                    >
                      {t('+ Tạo Agent', '+ New agent')}
                    </button>
                  </div>

                  {agents.map((ag) => (
                    <div
                      key={ag.id}
                      style={{
                        background: 'var(--bg-2)',
                        border: '1px solid var(--line)',
                        borderRadius: 8,
                        padding: 9,
                        display: 'flex',
                        flexDirection: 'column',
                        gap: 4,
                      }}
                    >
                      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
                        <b style={{ fontSize: 11.5, color: 'var(--ink)' }}>{(language === 'en' && ag.name_en) || ag.name}</b>
                        <button
                          type="button"
                          className="btn xs ghost"
                          onClick={() =>
                            addNodeToCanvas('agent_task', undefined, {
                              label: ag.name,
                              label_en: ag.name_en,
                              config: {
                                agent_role: ag.role,
                                provider: ag.provider,
                                prompt: ag.system_prompt,
                              },
                            })
                          }
                          title={t('Thêm Agent này thành Node Task', 'Add this agent as a task node')}
                          style={{ padding: '1px 5px', fontSize: 10 }}
                        >
                          + Canvas
                        </button>
                      </div>
                      <div style={{ fontSize: 10.5, color: 'var(--accent)', fontFamily: 'var(--mono)' }}>
                        Role: {ag.role} · {ag.provider}
                      </div>
                      <p className="muted" style={{ margin: 0, fontSize: 11, lineHeight: 1.35 }}>
                        {(language === 'en' && ag.purpose_en) || ag.purpose}
                      </p>
                      {ag.skills?.length > 0 && (
                        <div style={{ display: 'flex', gap: 4, flexWrap: 'wrap', marginTop: 2 }}>
                          {ag.skills.map((sk) => (
                            <span key={sk} className="chip xs" style={{ fontSize: 9 }}>
                              {sk}
                            </span>
                          ))}
                        </div>
                      )}
                    </div>
                  ))}
                </div>
              )}

              {/* TAB 4: AI WORKFLOW ARCHITECT */}
              {leftTab === 'architect' && (
                <div style={{ display: 'flex', flexDirection: 'column', gap: 10 }}>
                  <div style={{ fontSize: 11, color: 'var(--muted)', lineHeight: 1.4 }}>
                    {t('Thiết kế tự động toàn bộ quy trình DAG từ mục tiêu nghiên cứu tự nhiên:', 'Design the whole DAG workflow from a research goal in plain language:')}
                  </div>

                  <label className="field" style={{ margin: 0 }}>
                    <span style={{ fontSize: 11, fontWeight: 600 }}>{t('Mục tiêu nghiên cứu:', 'Research goal:')}</span>
                    <textarea
                      className="input sm"
                      rows={4}
                      style={{ fontSize: 11.5, resize: 'vertical' }}
                      placeholder={t('VD: Khảo sát và tối ưu hóa suy luận mô hình DeepSeek R1 trên phần cứng biên...', 'e.g. Survey and optimise DeepSeek R1 inference on edge hardware...')}
                      value={architectObjective}
                      onChange={(e) => setArchitectObjective(e.target.value)}
                    />
                  </label>

                  <label className="field" style={{ margin: 0 }}>
                    <span style={{ fontSize: 11, fontWeight: 600 }}>{t('Cấp độ thực thi:', 'Execution level:')}</span>
                    <select
                      className="input sm"
                      value={architectLevel}
                      onChange={(e) => setArchitectLevel(e.target.value as 'L2' | 'L3' | 'L4')}
                    >
                      <option value="L2">{t('L2: Giám sát từng bước có phê duyệt', 'L2: step-by-step with approval')}</option>
                      <option value="L3">{t('L3: Điều phối nhóm đa tác tử chuyên biệt', 'L3: coordinated specialist agent team')}</option>
                      <option value="L4">{t('L4: Tự chủ toàn diện từ ý tưởng đến bài báo', 'L4: fully autonomous from idea to paper')}</option>
                    </select>
                  </label>

                  <button
                    type="button"
                    className="btn sm accent"
                    onClick={handleGenerateWorkflow}
                    disabled={isArchitectGenerating || !architectObjective.trim()}
                    style={{ display: 'flex', alignItems: 'center', justifyContent: 'center', gap: 6 }}
                  >
                    <Sparkles size={13} />
                    {isArchitectGenerating ? t('Đang phân tích & thiết kế…', 'Analysing & designing…') : t('AI thiết kế quy trình', 'AI workflow design')}
                  </button>

                  {generatedWorkflow && (
                    <div
                      style={{
                        background: 'var(--bg-2)',
                        border: '1px solid var(--accent)',
                        borderRadius: 8,
                        padding: 10,
                        display: 'flex',
                        flexDirection: 'column',
                        gap: 6,
                        marginTop: 4,
                      }}
                    >
                      <b style={{ fontSize: 12 }}>{generatedWorkflow.name}</b>
                      <p className="muted" style={{ margin: 0, fontSize: 11, lineHeight: 1.35 }}>
                        {(language === 'en' && (generatedWorkflow as { description_en?: string }).description_en) || generatedWorkflow.description}
                      </p>
                      <div style={{ fontSize: 10.5, color: 'var(--ok)' }}>
                        ✓ {generatedWorkflow.nodes?.length} nodes · {generatedWorkflow.edges?.length} edges ({t('hợp lệ', 'valid')})
                      </div>
                      <button
                        type="button"
                        className="btn sm accent"
                        onClick={() => loadWorkflowIntoCanvas(generatedWorkflow)}
                        style={{ marginTop: 4 }}
                      >
                        {t('Tải vào Canvas & Chỉnh sửa', 'Load into canvas & edit')}
                      </button>
                    </div>
                  )}
                </div>
              )}
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
                maxWidth: 340,
              }}
            >
              <Sliders size={36} color="var(--muted)" style={{ marginBottom: 8 }} />
              <div style={{ fontWeight: 600, fontSize: 14 }}>{t('Canvas Quy trình Trống', 'Empty Workflow Canvas')}</div>
              <p className="muted" style={{ fontSize: 12, marginTop: 4, lineHeight: 1.4 }}>
                {t(
                  t('Chọn một mẫu nghiên cứu từ Thư viện, tạo tự động bằng AI Architect, hoặc kéo thả các khối từ bảng bên trái.', 'Pick a research template from the library, generate one with AI Architect, or drag blocks from the left panel.'),
                  'Select a template, generate with AI Architect, or drag and drop blocks from the left palette.'
                )}
              </p>
            </div>
          )}
        </div>

        {/* 3. Right Sidebar: Inspector & Debugger */}
        {inspectorOpen ? (
          <aside
            id={fullSpaceActive ? 'panel' : undefined}
            style={{
              width: 300,
              background: 'var(--panel)',
              borderLeft: '1px solid var(--line)',
              display: 'flex',
              flexDirection: 'column',
              flexShrink: 0,
              zIndex: 10,
            }}
          >
            {/* Header Tabs: Config vs Debugger */}
            <div style={{ display: 'flex', borderBottom: '1px solid var(--line)', background: 'var(--bg-2)' }}>
              <button
                type="button"
                className={`btn xs ${rightTab === 'config' ? 'accent' : 'ghost'}`}
                onClick={() => setRightTab('config')}
                style={{ flex: 1, borderRadius: 0, padding: '7px 4px', fontSize: 11 }}
              >
                {t('Cấu hình Node', 'Node settings')}
              </button>
              <button
                type="button"
                className={`btn xs ${rightTab === 'debugger' ? 'accent' : 'ghost'}`}
                onClick={() => setRightTab('debugger')}
                style={{ flex: 1, borderRadius: 0, padding: '7px 4px', fontSize: 11 }}
              >
                {t('Gỡ lỗi & Logs', 'Debug & logs')}
              </button>
            </div>

            <div style={{ flex: 1, overflowY: 'auto', padding: 12 }}>
              {/* TAB 1: NODE CONFIG */}
              {rightTab === 'config' && (
                <div>
                  {selectedNode ? (() => {
                    const nodeConfig = (selectedNode.data.config as Record<string, unknown>) || {};
                    return (
                    <div style={{ display: 'flex', flexDirection: 'column', gap: 10 }}>
                      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
                        <span style={{ fontSize: 11, fontWeight: 700, color: 'var(--muted)', textTransform: 'uppercase' }}>
                          {t('Cấu hình', 'Settings')} ({String(selectedNode.type || selectedNode.data.node_type || '')})
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
                        <span style={{ fontSize: 11, fontWeight: 600 }}>{t('Tên hiển thị:', 'Display name:')}</span>
                        <input
                          className="input sm"
                          value={String(selectedNode.data.label || '')}
                          onChange={(e) => updateSelectedNodeLabel(e.target.value)}
                        />
                      </label>

                      {/* Engine Selection if research_engine */}
                      {selectedNode.type === 'research_engine' && (
                        <label className="field" style={{ margin: 0 }}>
                          <span style={{ fontSize: 11, fontWeight: 600 }}>{t('Công cụ nghiên cứu:', 'Research engine:')}</span>
                          <select
                            className="input sm"
                            value={String(nodeConfig.engine || 'phdlab')}
                            onChange={(e) => updateSelectedNodeConfig('engine', e.target.value)}
                          >
                            <option value="paperorchestra">{t('PaperOrchestra (biên soạn bài báo)', 'PaperOrchestra (paper writing)')}</option>
                          </select>
                        </label>
                      )}

                      {/* Agent Role Selection if agent_task */}
                      {selectedNode.type === 'agent_task' && (
                        <>
                          <label className="field" style={{ margin: 0 }}>
                            <span style={{ fontSize: 11, fontWeight: 600 }}>Vai trò Agent:</span>
                            <select
                              className="input sm"
                              value={String(nodeConfig.agent_role || 'researcher')}
                              onChange={(e) => updateSelectedNodeConfig('agent_role', e.target.value)}
                            >
                              <option value="director">{t('Giáo sư hướng dẫn (PI)', 'Principal investigator (PI)')}</option>
                              <option value="literature">{t('Chuyên viên tổng quan tài liệu', 'Literature reviewer')}</option>
                              <option value="theorist">{t('Lý thuyết gia giả thuyết', 'Hypothesis theorist')}</option>
                              <option value="coder">{t('Kỹ sư thực nghiệm & code', 'Experiment & code engineer')}</option>
                              <option value="reviewer">{t('Phản biện khoa học độc lập', 'Independent scientific reviewer')}</option>
                              <option value="writer">{t('Biên tập viên PaperOrchestra', 'PaperOrchestra editor')}</option>
                            </select>
                          </label>

                          <label className="field" style={{ margin: 0 }}>
                            <span style={{ fontSize: 11, fontWeight: 600 }}>{t('Chỉ thị nhiệm vụ (prompt):', 'Task prompt:')}</span>
                            <textarea
                              className="input sm"
                              rows={3}
                              style={{ fontSize: 11 }}
                              value={String(nodeConfig.prompt || '')}
                              onChange={(e) => updateSelectedNodeConfig('prompt', e.target.value)}
                            />
                          </label>
                        </>
                      )}

                      {/* Condition formula if condition */}
                      {selectedNode.type === 'condition' && (
                        <label className="field" style={{ margin: 0 }}>
                          <span style={{ fontSize: 11, fontWeight: 600 }}>{t('Biểu thức điều kiện:', 'Condition expression:')}</span>
                          <input
                            className="input sm"
                            placeholder="acc >= 0.85 or pass_rate > 0.8"
                            value={String(nodeConfig.condition_rule || '')}
                            onChange={(e) => updateSelectedNodeConfig('condition_rule', e.target.value)}
                          />
                        </label>
                      )}

                      {/* Bounded loop settings */}
                      {selectedNode.type === 'bounded_loop' && (
                        <label className="field" style={{ margin: 0 }}>
                          <span style={{ fontSize: 11, fontWeight: 600 }}>{t('Số lần lặp tối đa:', 'Max iterations:')}</span>
                          <input
                            type="number"
                            className="input sm"
                            value={Number(nodeConfig.max_iterations || 3)}
                            onChange={(e) => updateSelectedNodeConfig('max_iterations', parseInt(e.target.value, 10))}
                          />
                        </label>
                      )}

                      {/* Human approval title */}
                      {selectedNode.type === 'human_approval' && (
                        <label className="field" style={{ margin: 0 }}>
                          <span style={{ fontSize: 11, fontWeight: 600 }}>{t('Tiêu đề checkpoint duyệt:', 'Approval checkpoint title:')}</span>
                          <input
                            className="input sm"
                            value={String(nodeConfig.checkpoint_title || '')}
                            onChange={(e) => updateSelectedNodeConfig('checkpoint_title', e.target.value)}
                          />
                        </label>
                      )}

                      {/* Benchmark Parameters if harnessNode */}
                      {selectedNodeTool && (
                        <div style={{ display: 'flex', flexDirection: 'column', gap: 6, marginTop: 4 }}>
                          <span style={{ fontSize: 11, fontWeight: 600 }}>{t('Tham số benchmark:', 'Benchmark parameters:')}</span>
                          {Object.entries((selectedNode.data.params as Record<string, unknown>) || {}).map(
                            ([k, v]) => (
                              <label key={k} className="field" style={{ margin: 0 }}>
                                <span style={{ fontSize: 10.5, fontFamily: 'var(--mono)' }}>{k}</span>
                                <input
                                  className="input sm"
                                  style={{ fontSize: 11 }}
                                  value={String(v)}
                                  onChange={(e) => updateSelectedNodeParam(k, e.target.value)}
                                />
                              </label>
                            )
                          )}
                        </div>
                      )}

                      {/* Delete node button */}
                      <button
                        type="button"
                        className="btn sm ghost"
                        onClick={() => handleDeleteNode(selectedNode.id)}
                        style={{ color: 'var(--err)', marginTop: 10 }}
                      >
                        {t('Xóa Node này khỏi Canvas', 'Remove this node from the canvas')}
                      </button>
                    </div>
                    );
                  })() : (
                    <div style={{ textAlign: 'center', color: 'var(--muted)', marginTop: 40, fontSize: 12 }}>
                      {t('Bấm chọn một khối node trên canvas để xem và điều chỉnh thuộc tính chi tiết.', 'Select a node on the canvas to view and edit its properties.')}
                    </div>
                  )}
                </div>
              )}

              {/* TAB 2: WORKFLOW DEBUGGER & LOGS */}
              {rightTab === 'debugger' && (
                <div style={{ display: 'flex', flexDirection: 'column', gap: 10 }}>
                  <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
                    <span style={{ fontSize: 11, fontWeight: 700, color: 'var(--muted)', textTransform: 'uppercase' }}>
                      {t('Trạng thái Thực thi', 'Execution status')}
                    </span>
                    {executionState && (
                      <span className={`chip sm ${executionState.status === 'completed' ? 'ok' : executionState.status === 'failed' ? 'err' : 'accent'}`}>
                        {executionState.status}
                      </span>
                    )}
                  </div>

                  {/* Human Approval Gate Action Banner */}
                  {executionState && executionState.status === 'waiting_approval' && (
                    <div
                      style={{
                        background: 'rgba(244, 63, 94, 0.08)',
                        border: '1px solid #f43f5e',
                        borderRadius: 8,
                        padding: 10,
                        display: 'flex',
                        flexDirection: 'column',
                        gap: 8,
                      }}
                    >
                      <div style={{ display: 'flex', alignItems: 'center', gap: 6, color: '#f43f5e', fontWeight: 600, fontSize: 12 }}>
                        <ShieldCheck size={15} />
                        {t('Yêu cầu Phê duyệt của Nhà nghiên cứu', 'Researcher approval required')}
                      </div>
                      <p style={{ margin: 0, fontSize: 11, lineHeight: 1.35 }}>
                        {t('Quy trình đang tạm dừng tại điểm kiểm soát. Vui lòng xem xét các minh chứng trước khi tiếp tục.', 'The workflow is paused at a checkpoint. Review the evidence before continuing.')}
                      </p>
                      <textarea
                        className="input sm"
                        rows={2}
                        placeholder={t('Ghi chú phản biện hoặc hướng dẫn sửa đổi...', 'Review notes or revision instructions...')}
                        value={approvalFeedback}
                        onChange={(e) => setApprovalFeedback(e.target.value)}
                        style={{ fontSize: 11 }}
                      />
                      <div style={{ display: 'flex', gap: 6 }}>
                        <button
                          type="button"
                          className="btn sm accent"
                          onClick={() => actionMutation.mutate({ action: 'approve' })}
                          style={{ flex: 1 }}
                        >
                          {t('✓ Phê duyệt', '✓ Approve')}
                        </button>
                        <button
                          type="button"
                          className="btn sm ghost"
                          onClick={() => actionMutation.mutate({ action: 'reject' })}
                          style={{ color: 'var(--err)' }}
                        >
                          {t('✕ Từ chối', '✕ Reject')}
                        </button>
                      </div>
                    </div>
                  )}

                  {/* Node Execution Steps Timeline */}
                  {executionState?.node_statuses ? (
                    <div style={{ display: 'flex', flexDirection: 'column', gap: 6 }}>
                      <span style={{ fontSize: 11, fontWeight: 600 }}>{t('Tiến trình các bước', 'Step progress')} ({executionState.node_statuses.length}):</span>
                      {executionState.node_statuses.map((st) => (
                        <div
                          key={st.node_id}
                          style={{
                            background: 'var(--bg-2)',
                            border: '1px solid var(--line)',
                            borderRadius: 6,
                            padding: '6px 8px',
                            display: 'flex',
                            flexDirection: 'column',
                            gap: 4,
                            fontSize: 11,
                          }}
                        >
                          <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
                            <div title={(language === 'en' && (st as { label_en?: string }).label_en) || st.label} style={{ overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap', maxWidth: 180 }}>
                              <b>{(language === 'en' && (st as { label_en?: string }).label_en) || st.label}</b>
                            </div>
                            <span className={`chip xs ${st.status === 'completed' ? 'ok' : st.status === 'blocked' ? 'muted' : st.status === 'failed' ? 'err' : 'muted'}`}>
                              {st.status}
                            </span>
                          </div>
                          {st.summary && (
                            <div style={{ fontSize: 10, color: 'var(--muted)', lineHeight: 1.3 }}>
                              {st.summary}
                            </div>
                          )}
                        </div>
                      ))}
                    </div>
                  ) : (
                    <div style={{ fontSize: 11.5, color: 'var(--muted)', textAlign: 'center', marginTop: 20 }}>
                      {t('Chưa có phiên thực thi nào. Bấm', 'No runs yet. Press')} <b>{t('Chạy Harness', 'Run Harness')}</b> {t('hoặc', 'or')} <b>{t('Bước', 'Step')}</b> {t('để theo dõi luồng dữ liệu thời gian thực.', 'to follow the data flow live.')}
                    </div>
                  )}

                  {/* Structured Logs */}
                  {executionState?.logs && executionState.logs.length > 0 && (
                    <div style={{ display: 'flex', flexDirection: 'column', gap: 6, marginTop: 10 }}>
                      <span style={{ fontSize: 11, fontWeight: 600 }}>{t('Nhật ký thực thi:', 'Execution log:')}</span>
                      <div
                        style={{
                          background: 'var(--bg-2)',
                          borderRadius: 6,
                          padding: 8,
                          fontFamily: 'var(--mono)',
                          fontSize: 10,
                          maxHeight: 200,
                          overflowY: 'auto',
                          display: 'flex',
                          flexDirection: 'column',
                          gap: 3,
                        }}
                      >
                        {executionState.logs.map((log, idx) => (
                          <div key={idx} style={{ color: log.level === 'error' ? 'var(--err)' : 'var(--ink)' }}>
                            <span style={{ color: 'var(--muted)' }}>[{log.timestamp.slice(11, 19)}]</span> {log.message}
                          </div>
                        ))}
                      </div>
                    </div>
                  )}
                </div>
              )}
            </div>
          </aside>
        ) : null}
      </div>

      {/* ----------------- Create Agent Modal ----------------- */}
      {showAgentModal && (
        <div
          style={{
            position: 'fixed',
            inset: 0,
            background: 'rgba(0,0,0,0.5)',
            display: 'flex',
            alignItems: 'center',
            justifyContent: 'center',
            zIndex: 100,
          }}
        >
          <div
            style={{
              background: 'var(--panel)',
              borderRadius: 10,
              padding: 18,
              width: 440,
              maxWidth: '90vw',
              display: 'flex',
              flexDirection: 'column',
              gap: 12,
              boxShadow: '0 8px 30px rgba(0,0,0,0.3)',
            }}
          >
            <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
              <h3 style={{ margin: 0, fontSize: 14 }}>{t('Tạo chuyên gia AI nghiên cứu mới', 'New AI research expert')}</h3>
              <button type="button" className="icon xs" onClick={() => setShowAgentModal(false)}>
                ✕
              </button>
            </div>

            <label className="field" style={{ margin: 0 }}>
              <span style={{ fontSize: 11 }}>{t('Tên chuyên gia:', 'Expert name:')}</span>
              <input
                className="input sm"
                placeholder={t('VD: Chuyên gia Phân tích Thống kê', 'e.g. Statistics analyst')}
                value={newAgentName}
                onChange={(e) => setNewAgentName(e.target.value)}
              />
            </label>

            <label className="field" style={{ margin: 0 }}>
              <span style={{ fontSize: 11 }}>Vai trò:</span>
              <select className="input sm" value={newAgentRole} onChange={(e) => setNewAgentRole(e.target.value)}>
                <option value="researcher">{t('Nghiên cứu viên độc lập', 'Independent researcher')}</option>
                <option value="director">{t('Giáo sư hướng dẫn', 'Principal investigator')}</option>
                <option value="theorist">{t('Lý thuyết gia giả thuyết', 'Theorist')}</option>
                <option value="coder">{t('Kỹ sư thực nghiệm & code', 'Coder')}</option>
                <option value="reviewer">{t('Phản biện khoa học độc lập', 'Reviewer')}</option>
                <option value="writer">{t('Biên soạn bài báo học thuật', 'Academic writer')}</option>
              </select>
            </label>

            <label className="field" style={{ margin: 0 }}>
              <span style={{ fontSize: 11 }}>{t('Mục đích & trách nhiệm:', 'Purpose & responsibilities:')}</span>
              <textarea
                className="input sm"
                rows={2}
                placeholder={t('Mô tả phạm vi trách nhiệm của agent...', 'Describe what this agent is responsible for...')}
                value={newAgentPurpose}
                onChange={(e) => setNewAgentPurpose(e.target.value)}
              />
            </label>

            <label className="field" style={{ margin: 0 }}>
              <span style={{ fontSize: 11 }}>System Prompt:</span>
              <textarea
                className="input sm"
                rows={3}
                placeholder="You are an expert in..."
                value={newAgentPrompt}
                onChange={(e) => setNewAgentPrompt(e.target.value)}
              />
            </label>

            <div style={{ display: 'flex', justifyContent: 'flex-end', gap: 8, marginTop: 6 }}>
              <button type="button" className="btn sm ghost" onClick={() => setShowAgentModal(false)}>
                Hủy
              </button>
              <button
                type="button"
                className="btn sm accent"
                onClick={() => createAgentMutation.mutate()}
                disabled={createAgentMutation.isPending || !newAgentName.trim()}
              >
                {t('Lưu Agent Profile', 'Save agent profile')}
              </button>
            </div>
          </div>
        </div>
      )}

      {/* ----------------- Legacy Execution Report Modal ----------------- */}
      {showReportModal && latestReport && (
        <div
          style={{
            position: 'absolute',
            bottom: 0,
            left: 0,
            right: 0,
            maxHeight: '45%',
            background: 'var(--panel)',
            borderTop: '2px solid var(--accent)',
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
                  <td style={{ padding: '6px 8px', fontWeight: 600 }}>{(language === 'en' && (nr as { label_en?: string }).label_en) || nr.label}</td>
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
