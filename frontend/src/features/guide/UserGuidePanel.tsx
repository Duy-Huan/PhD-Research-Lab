import React, { useState } from 'react';
import { useUIStore, useI18n } from '../../shared/state/uiStore';
import {
  BookOpen,
  HelpCircle,
  Rocket,
  Bot,
  Terminal,
  FileText,
  Sparkles,
  CheckCircle2,
  Cpu,
  Layers,
  Search,
  Compass,
  Keyboard,
  ShieldCheck,
  ChevronRight,
  ExternalLink,
  HardDrive,
  MessageSquare,
  Play,
  Settings,
  Languages,
  UserCheck,
  Code,
  FolderOpen,
  Workflow,
  Award,
  Zap,
  Sliders,
  Maximize2,
  Database,
  BarChart3,
  GitBranch,
  FlaskConical,
  Palette,
} from 'lucide-react';

export const UserGuidePanel: React.FC = () => {
  const { t, language, setLanguage } = useI18n();
  const { openDrawer, openSettings, open3DOffice, setMainView } = useUIStore();
  const [activeTab, setActiveTab] = useState<'quickstart' | 'workflows' | 'agents' | 'commands' | 'library' | 'shortcuts'>('quickstart');
  const [filterText, setFilterText] = useState('');

  const tabs = [
    { id: 'quickstart', label: t('🚀 Bắt đầu nhanh (5 bước)', '🚀 Quickstart (5 Steps)'), icon: <Rocket size={15} /> },
    { id: 'workflows', label: t('🔄 Danh mục Quy trình', '🔄 Research Workflows'), icon: <Workflow size={15} /> },
    { id: 'agents', label: t('🤖 Hội đồng AI & Phòng Lab 3D', '🤖 AI Agents & 3D Lab'), icon: <Bot size={15} /> },
    { id: 'commands', label: t('💬 Trò chuyện & Lệnh tắt gạch chéo', '💬 Chat & Slash Commands (/)'), icon: <Terminal size={15} /> },
    { id: 'library', label: t('📚 Thư viện PDF & Xếp hạng', '📚 PDF Library & Ranking'), icon: <BookOpen size={15} /> },
    { id: 'shortcuts', label: t('⌨️ Phím tắt & Câu hỏi thường gặp', '⌨️ Shortcuts & FAQ'), icon: <Keyboard size={15} /> },
  ] as const;

  const toggleLanguage = () => {
    setLanguage(language === 'vi' ? 'en' : 'vi');
  };

  const workflowsList = [
    {
      id: 'lit-hypothesis',
      number: 1,
      icon: <BookOpen size={20} color="var(--accent)" />,
      categoryVi: 'Khám phá & Giả thuyết',
      categoryEn: 'Discovery & Hypotheses',
      titleVi: 'Quy trình Khảo cứu Tài liệu & Đề xuất Giả thuyết Khoa học',
      titleEn: 'Literature Exploration & Scientific Hypothesis Formulation Workflow',
      descVi: 'Tự động hóa tìm kiếm đa nguồn học thuật, phân tích đồ thị trích dẫn, bóc tách khoảng trống nghiên cứu và tạo giả thuyết khoa học có thể kiểm chứng.',
      descEn: 'Automated multi-source academic retrieval, citation graph analysis, research gap synthesis, and verifiable hypothesis generation.',
      stepsVi: [
        'Khảo sát nguồn học thuật: Kết nối Google Scholar, ArXiv, CrossRef, Semantic Scholar bằng lệnh gạch chéo lit.',
        'Trích xuất siêu dữ liệu và tóm tắt: Tự động phân loại tài liệu theo nhóm chủ đề và lưu trữ vào thư viện bài báo.',
        'Phân tích đồ thị trích dẫn: Nhận diện các công trình nền tảng, bài báo bước ngoặt và xu hướng nghiên cứu mới nhất.',
        'Tổng hợp khoảng trống tri thức: Dùng lệnh gạch chéo hypothesis để phân tích những vấn đề chưa được giải quyết trong y văn.',
        'Đề xuất giả thuyết định lượng: Tác nhân Lead Researcher và Critic cùng xây dựng giả thuyết kèm tiêu chí kiểm định thực nghiệm và đánh giá độ mới.',
      ],
      stepsEn: [
        'Academic survey: Retrieve papers across Google Scholar, ArXiv, CrossRef, Semantic Scholar via /lit command.',
        'Metadata & abstract ingestion: Automatically categorize literature into subject clusters and sync to paper library.',
        'Citation graph analysis: Trace seminal publications, milestone papers, and emerging research fronts.',
        'Research gap synthesis: Run /hypothesis command to analyze unresolved bottlenecks across prior publications.',
        'Verifiable hypothesis generation: Lead Researcher and Critic formulate quantified hypotheses with empirical test criteria and novelty metrics.',
      ],
      actionLabelVi: 'Mở Thư viện Bài báo',
      actionLabelEn: 'Open Paper Library',
      actionIcon: <BookOpen size={13} style={{ marginRight: 5 }} />,
      onAction: () => openDrawer('library'),
      secondaryActionLabelVi: 'Khảo sát qua Khung Chat',
      secondaryActionLabelEn: 'Survey via Chat',
      secondaryActionIcon: <MessageSquare size={13} style={{ marginRight: 5 }} />,
      onSecondaryAction: () => setMainView('chat'),
    },
    {
      id: 'autonomous-missions',
      number: 2,
      icon: <Bot size={20} color="#3b82f6" />,
      categoryVi: 'Điều phối & Tự trị',
      categoryEn: 'Autonomous Orchestration',
      titleVi: 'Quy trình Nhiệm vụ Tự trị & Hội đồng AI Điều phối',
      titleEn: 'Autonomous Research Missions & Multi-Agent Council Workflow',
      descVi: 'Thực thi nhiệm vụ nghiên cứu tự hành theo hiến chương, hội đồng 6 tác nhân chuyên môn hóa phân rã đồ thị nhiệm vụ DAG có giám sát.',
      descEn: 'Charter-driven autonomous research execution orchestrated by a specialized 6-agent advisory board with supervised DAG decomposition.',
      stepsVi: [
        'Soạn thảo Hiến chương Nghiên cứu: Xác định rõ ràng mục tiêu, phạm vi nghiên cứu, giả định và chuẩn đầu ra.',
        'Phân rã đồ thị DAG: Tác nhân Giáo sư Hướng dẫn phân tách nhiệm vụ thành mạng lưới công việc có thứ tự phụ thuộc chặt chẽ.',
        'Phân công tác nhân chuyên trách: Giao việc cho Nghiên cứu viên Trưởng, Chuyên gia Phản biện, Chuyên gia Phương pháp và Kỹ sư Phần mềm.',
        'Cổng phê duyệt của người dùng: Các quyết định trọng yếu, sửa đổi cấu trúc lớn đều cần người dùng bấm xác nhận trước khi tiếp tục.',
        'Tổng kết và lưu trữ nhiệm vụ: Tổng hợp kết quả, tự động cập nhật nhật ký tiến độ và sinh báo cáo tổng kết hoàn chỉnh.',
      ],
      stepsEn: [
        'Mission charter drafting: Clearly define research objectives, problem scope, scientific assumptions, and expected deliverables.',
        'DAG task decomposition: Supervisor orchestrates the dependency tree into parallel and sequential subtasks.',
        'Role assignment: Delegate specialized tasks across Lead Researcher, Critic, Methodologist, and Software Engineer.',
        'Human-in-the-loop review gates: Critical decisions and structural modifications require explicit user sign-off before proceeding.',
        'Mission synthesis & archival: Aggregate empirical results, auto-update progress logs, and generate final comprehensive summaries.',
      ],
      actionLabelVi: 'Mở Quản lý Nhiệm vụ',
      actionLabelEn: 'Open Missions Drawer',
      actionIcon: <Rocket size={13} style={{ marginRight: 5 }} />,
      onAction: () => openDrawer('missions'),
      secondaryActionLabelVi: 'Xem Hội đồng Tác nhân',
      secondaryActionLabelEn: 'View Agent Council',
      secondaryActionIcon: <Bot size={13} style={{ marginRight: 5 }} />,
      onSecondaryAction: () => openDrawer('agent-status'),
    },
    {
      id: 'workstreams-cas',
      number: 3,
      icon: <GitBranch size={20} color="#8b5cf6" />,
      categoryVi: 'Xử lý Song song & Đồng bộ',
      categoryEn: 'Concurrency & Synchronization',
      titleVi: 'Quy trình Phân luồng Workstreams Song song & Trọng tài Đồng quy CAS',
      titleEn: 'Parallel Workstreams & Conflict-Free CAS Concurrency Workflow',
      descVi: 'Vận hành đa luồng nghiên cứu song song không xung đột dữ liệu, ứng dụng cơ chế so sánh và hoán đổi CAS đảm bảo toàn vẹn trạng thái.',
      descEn: 'Concurrent multi-track research execution with zero state collision, leveraging Compare-And-Swap optimistic locks for data integrity.',
      stepsVi: [
        'Khởi tạo nhánh luồng công việc: Tạo các workstream độc lập cho từng hướng giải pháp hoặc nhóm thí nghiệm song song.',
        'Khóa tài nguyên phân tán: Hệ thống tự động thiết lập quyền truy cập độc quyền cho từng tệp hoặc bản ghi nghiên cứu.',
        'Trọng tài Compare-And-Swap: Kiểm tra phiên bản trạng thái trước khi ghi nhận thay đổi, ngăn chặn tình trạng ghi đè vô ý.',
        'Phân giải xung đột tự động: Khi xảy ra dị biệt phiên bản, hệ thống kích hoạt cơ chế hòa trộn hoặc hoàn tác có kiểm soát.',
        'Đồng bộ vào nhánh chính: Hợp nhất kết quả từ các nhánh công việc đã được kiểm định an toàn vào không gian dự án chung.',
      ],
      stepsEn: [
        'Workstream branch creation: Launch independent workstreams for distinct hypothesis angles or concurrent experiment batches.',
        'Distributed resource locking: System establishes fine-grained lease locks for files, records, and execution states.',
        'Compare-And-Swap arbitration: Validates state version tokens before commits, eliminating silent overwrites.',
        'Automated conflict resolution: Discrepancies trigger structured three-way merges or controlled state rollbacks.',
        'Mainline synchronization: Integrate verified workstream artifacts back into the shared research repository.',
      ],
      actionLabelVi: 'Mở Giám sát Luồng công việc',
      actionLabelEn: 'Open Workstream Monitor',
      actionIcon: <GitBranch size={13} style={{ marginRight: 5 }} />,
      onAction: () => openDrawer('workstreams'),
    },
    {
      id: 'controlled-protocols',
      number: 4,
      icon: <FlaskConical size={20} color="#10b981" />,
      categoryVi: 'Thực nghiệm & Tái lập',
      categoryEn: 'Controlled Protocols',
      titleVi: 'Quy trình Thí nghiệm Có kiểm soát & Tái lập Định thức',
      titleEn: 'Controlled Protocols & Reproducible Experimentation Workflow',
      descVi: 'Quản lý giao thức thực nghiệm chặt chẽ, tối ưu phân bổ tài nguyên tính toán và xác thực tính tái lập bằng băm mã SHA-256.',
      descEn: 'Rigorous protocol orchestration, dynamic compute offloading, and deterministic verification backed by SHA-256 hashing.',
      stepsVi: [
        'Định nghĩa giao thức chuẩn: Thiết lập tham số thí nghiệm, điều kiện môi trường, bộ hạt giống ngẫu nhiên và tiêu chí dừng.',
        'Phân bổ tài nguyên thông minh: Trình bảo vệ ResourceGuard tự động điều phối bộ nhớ GPU, tạm dừng mô hình cục bộ khi cần VRAM chạy mã.',
        'Ghi nhận nhật ký liên tục: Theo dõi số liệu huấn luyện và đánh giá theo thời gian thực, tích hợp công cụ theo dõi native.',
        'Băm mã định danh SHA-256: Mã hóa tệp cấu hình, mã nguồn thực thi và tập dữ liệu đầu ra để chứng thực tính nguyên bản.',
        'Đóng gói bộ thí nghiệm tái lập: Tự động xuất snapshot môi trường, đảm bảo đồng nghiệp có thể tái tạo kết quả chính xác 100%.',
      ],
      stepsEn: [
        'Structured protocol specification: Define experiment parameters, compute environment, seed sets, and convergence criteria.',
        'ResourceGuard GPU arbitration: Intelligently suspends idle local models from VRAM whenever compute jobs request GPU allocations.',
        'Telemetry & experiment tracking: Stream training and evaluation metrics in real time with integrated native logging.',
        'SHA-256 cryptographic provenance: Hashes configs, executable source code, and result datasets to certify reproducibility.',
        'Reproducible bundle export: Generates full container snapshots and dependencies ensuring 100% reproducible results.',
      ],
      actionLabelVi: 'Mở Giao thức Thí nghiệm',
      actionLabelEn: 'Open Protocols Drawer',
      actionIcon: <FlaskConical size={13} style={{ marginRight: 5 }} />,
      onAction: () => openDrawer('protocols'),
      secondaryActionLabelVi: 'Cài đặt Tài nguyên Phần cứng',
      secondaryActionLabelEn: 'Hardware Settings',
      secondaryActionIcon: <Settings size={13} style={{ marginRight: 5 }} />,
      onSecondaryAction: () => openSettings(),
    },
    {
      id: 'opencode-sandbox',
      number: 5,
      icon: <Code size={20} color="#f59e0b" />,
      categoryVi: 'Lập trình & Bản vá Tự động',
      categoryEn: 'Native Code Sandbox',
      titleVi: 'Quy trình Nhân Thực nghiệm Native Code & Tự động Sửa mã',
      titleEn: 'Native Experiment Sandbox & Automated Self-Debugging Workflow',
      descVi: 'Môi trường lập trình hộp cát cô lập, tác nhân AI tự động tạo bản vá, chạy kiểm thử và sửa lỗi lặp cho đến khi vượt qua 100% test.',
      descEn: 'Sandboxed code execution environment where agents craft diff patches, run regression suites, and iteratively fix bugs until all tests pass.',
      stepsVi: [
        'Thiết lập hộp cát cô lập: Tạo môi trường thực thi ảo độc lập để chạy mã nguồn thực nghiệm an toàn tuyệt đối.',
        'Phân tích lỗi và đề xuất bản vá: Đọc hiểu thông báo lỗi ngoại lệ, tạo bản sửa đổi định dạng diff chuẩn xác từng dòng lệnh.',
        'Thực thi bộ kiểm thử tự động: Chạy toàn bộ test suite đơn vị và kiểm thử chức năng để đánh giá tính đúng đắn.',
        'Vòng lặp tự sửa lỗi: Lặp lại quy trình chỉnh sửa mã nếu còn ca kiểm thử thất bại cho đến khi đạt tỷ lệ vượt qua tuyệt đối.',
        'Kiểm định hồi quy hiệu năng: Đo lường tốc độ tính toán, mức chiếm dụng bộ nhớ RAM và GPU để đảm bảo mã nguồn tối ưu.',
      ],
      stepsEn: [
        'Sandboxed isolation: Spins up an isolated execution sandbox to safely run experimental scripts and compute algorithms.',
        'Error diagnosis & diff patching: Parses exception tracebacks and generates unified diff patches pinpointing necessary fixes.',
        'Automated test execution: Runs complete unit test suites and functional test cases to verify correctness.',
        'Iterative self-debugging loop: Automatically re-patches and re-executes tests upon failure until 100% test pass is achieved.',
        'Regression & efficiency benchmarking: Profiles compute throughput, RAM footprint, and VRAM utilization to ensure optimal code.',
      ],
      actionLabelVi: 'Mở Không gian Native Code',
      actionLabelEn: 'Open Native Code Workspace',
      actionIcon: <Code size={13} style={{ marginRight: 5 }} />,
      onAction: () => openDrawer('code'),
    },
    {
      id: 'scientific-figures',
      number: 6,
      icon: <Palette size={20} color="#ec4899" />,
      categoryVi: 'Đồ họa & Trực quan hóa',
      categoryEn: 'Figure Studio',
      titleVi: 'Quy trình Xưởng Đồ họa Khoa học & Trực quan hóa Dữ liệu',
      titleEn: 'Scientific Visualization & Multi-Format Figure Studio Workflow',
      descVi: 'Thiết kế biểu đồ chuẩn xuất bản bài báo khoa học, từ đồ thị 2D, bảng so sánh đa panel, sơ đồ Graphviz đến dạng sóng WaveDrom và bề mặt 3D.',
      descEn: 'Design publication-grade scientific figures, spanning 2D plots, multi-panel comparative plates, Graphviz schematics, WaveDrom waveforms, and 3D surfaces.',
      stepsVi: [
        'Khởi tạo kịch bản trực quan: Nạp dữ liệu thực nghiệm từ tệp CSV, JSON hoặc cơ sở dữ liệu kết quả nghiên cứu.',
        'Lựa chọn định dạng đồ họa: Hỗ trợ biểu đồ 2D xuất bản bằng Matplotlib và Seaborn, bảng ghép nhiều hình ảnh, sơ đồ kiến trúc Graphviz, giản đồ thời gian WaveDrom hoặc biểu đồ mặt 3D.',
        'Tinh chỉnh bố cục và phông chữ: Tùy biến kiểu chữ khoa học, bảng màu phân biệt rõ ràng, nhãn trục tọa độ và ghi chú chú giải.',
        'Kiểm tra độ tương phản và tỷ lệ: Tự động kiểm tra độ phân giải cao và tính tương thích trên cả nền sáng lẫn nền tối.',
        'Xuất tệp đồ họa vector: Tải về định dạng PDF, SVG, EPS hoặc PNG với độ phân giải cao sẵn sàng chèn trực tiếp vào bản thảo LaTeX.',
      ],
      stepsEn: [
        'Visualization script ingestion: Loads experimental data from CSV, JSON, or SQL benchmark tables.',
        'Multi-format rendering: Generates 2D scientific plots (Matplotlib/Seaborn), multi-panel image plates, Graphviz architecture diagrams, WaveDrom signal timing, or 3D surfaces.',
        'Layout & typography refinement: Customizes academic fonts, accessible color palettes, axis tick labels, and legends.',
        'Contrast & dpi validation: Automatically audits print contrast compliance and high-DPI scaling across light and dark modes.',
        'Vector export: Exports high-resolution PDF, SVG, EPS, or PNG assets ready for direct inclusion in LaTeX manuscripts.',
      ],
      actionLabelVi: 'Mở Xưởng Đồ họa',
      actionLabelEn: 'Open Figure Studio',
      actionIcon: <Palette size={13} style={{ marginRight: 5 }} />,
      onAction: () => openDrawer('figures'),
    },
    {
      id: 'claims-evidence-review',
      number: 7,
      icon: <ShieldCheck size={20} color="#06b6d4" />,
      categoryVi: 'Quản trị Luận điểm & Bình duyệt',
      categoryEn: 'Claims & Peer Review',
      titleVi: 'Quy trình Quản trị Luận điểm & Sổ cái Bằng chứng Khoa học',
      titleEn: 'Claims Governance & Cryptographic Evidence Ledger Workflow',
      descVi: 'Liên kết mật mã giữa tuyên bố khoa học với bằng chứng thực nghiệm, tổ chức hội đồng bình duyệt 3 vòng độc lập phản biện khắt khe.',
      descEn: 'Cryptographically binds scientific assertions to empirical proof, orchestrating rigorous 3-stage peer review councils.',
      stepsVi: [
        'Đăng ký luận điểm khoa học: Ghi nhận từng tuyên bố cốt lõi của nghiên cứu vào sổ cái dữ liệu.',
        'Liên kết bằng chứng thực nghiệm: Gắn kết từng luận điểm với các bảng số liệu, đường dẫn đồ thị và đoạn mã chạy thực tế.',
        'Đánh giá độ vững chắc: Tác nhân Phản biện đối chiếu các kịch bản phản chứng và tính hợp lệ của số liệu thống kê.',
        'Khởi động 3 vòng bình duyệt độc lập: Các chuyên gia bình duyệt R1, R2, R3 chấm điểm khắt khe dựa trên tiêu chí của các hội nghị hàng đầu.',
        'Xuất bản ma trận xác thực: Tổng hợp bảng đối chiếu luận điểm kèm chữ ký xác thực bằng chứng sẵn sàng phục vụ phản biện bài báo.',
      ],
      stepsEn: [
        'Claim registration: Registers core scientific theses, empirical contributions, and theoretical conjectures in the ledger.',
        'Cryptographic evidence anchoring: Binds assertions directly to raw log runs, benchmark tables, and source code commits.',
        'Falsification analysis: Critic agent probes edge cases, counter-examples, and statistical significance margins.',
        '3-tier peer review board: Reviewers R1, R2, and R3 evaluate the submission against IEEE, ACM, and Nature standards.',
        'Verification matrix publication: Emits tamper-evident claim-evidence proof sheets ready for journal rebuttals.',
      ],
      actionLabelVi: 'Mở Sổ cái Luận điểm',
      actionLabelEn: 'Open Claims Ledger',
      actionIcon: <ShieldCheck size={13} style={{ marginRight: 5 }} />,
      onAction: () => openDrawer('claims'),
      secondaryActionLabelVi: 'Mở Bàn tròn Bình duyệt',
      secondaryActionLabelEn: 'Open Peer Review',
      secondaryActionIcon: <UserCheck size={13} style={{ marginRight: 5 }} />,
      onSecondaryAction: () => openDrawer('review'),
    },
    {
      id: 'paper-latex-dual',
      number: 8,
      icon: <FileText size={20} color="#6366f1" />,
      categoryVi: 'Bản thảo & Biên dịch Tài liệu',
      categoryEn: 'Manuscript & LaTeX',
      titleVi: 'Quy trình Soạn thảo Bản thảo & Biên dịch LaTeX Hai Chế độ',
      titleEn: 'Manuscript Drafting & Dual-Engine LaTeX Compilation Workflow',
      descVi: 'Tự động phác thảo bài báo theo chuẩn học thuật quốc tế, biên dịch kép linh hoạt bằng công cụ máy chủ cục bộ hoặc dịch vụ trực tuyến.',
      descEn: 'Drafts publication-ready papers with templates, powered by dual-engine local TeX Live/Tectonic and online cloud compilation.',
      stepsVi: [
        'Khởi tạo khung bài báo: Lựa chọn mẫu định dạng chuẩn như IEEE, ACM, NeurIPS hoặc Springer.',
        'Soạn thảo từng chương mục: Tác nhân phối hợp viết tóm tắt, phần mở đầu, phương pháp đề xuất, thực nghiệm đánh giá và tài liệu liên quan.',
        'Đồng bộ trích dẫn BibTeX: Tự động liên kết các mã khóa trích dẫn từ thư viện bài báo vào các tệp tham khảo.',
        'Lựa chọn chế độ biên dịch: Chuyển đổi linh hoạt giữa Biên dịch Cục bộ qua TeX Live hoặc Tectonic trên máy tính và Biên dịch Trực tuyến qua đám mây.',
        'Xem trước trực tiếp và xuất gói ZIP: Đọc bản in PDF song song với khung soạn thảo mã nguồn, xuất trọn gói kho lưu trữ nén nộp bài.',
      ],
      stepsEn: [
        'Template initialization: Choose from premier conference templates including IEEE, ACM, NeurIPS, and Springer.',
        'Collaborative section drafting: Agents author Abstract, Introduction, Proposed Method, Evaluation, and Related Work.',
        'BibTeX citation synchronization: Automatically links citation keys from the paper library directly into references.bib.',
        'Dual-engine compilation: Seamlessly switch between Local Engine (local TeX Live / Tectonic) and Online Cloud Engine.',
        'Live PDF preview & ZIP export: View rendered PDF alongside source TeX code, with one-click export of complete camera-ready ZIP archives.',
      ],
      actionLabelVi: 'Mở Bản thảo Bài báo',
      actionLabelEn: 'Open Paper Manuscript',
      actionIcon: <FileText size={13} style={{ marginRight: 5 }} />,
      onAction: () => openDrawer('paper'),
    },
    {
      id: 'custom-harness-studio',
      number: 9,
      icon: <Workflow size={20} color="#ea580c" />,
      categoryVi: 'Đánh giá Điểm chuẩn & Kéo thả',
      categoryEn: 'Custom Harness Studio',
      titleVi: 'Quy trình Đánh giá Harness Kéo thả Tùy chỉnh & Công cụ Mã nguồn Mở',
      titleEn: 'Visual Custom Harness Studio & Open-Source Tools Workflow',
      descVi: 'Xây dựng quy trình đánh giá mô hình bằng giao diện kéo thả trực quan, tích hợp sâu các công cụ chuẩn học thuật mã nguồn mở hàng đầu thế giới.',
      descEn: 'Visual drag-and-drop workflow canvas for benchmarking, deeply integrating premier open-source evaluation tools.',
      stepsVi: [
        'Kéo thả các nút tác vụ trên bảng vẽ: Đặt các khối nguồn mô hình, bộ nạp dữ liệu kiểm thử, công cụ đánh giá và khối xuất kết quả.',
        'Lựa chọn công cụ mã nguồn mở chuyên sâu: Hỗ trợ đầy đủ LM-Evaluation-Harness, Inspect AI, Promptfoo, Ragas, SWE-Bench, Pytest Runner và PhDLab Research Harness.',
        'Nối dây luồng dữ liệu tương tác: Kết nối đầu ra của mô hình vào cổng đầu vào của bộ đánh giá một cách trực quan.',
        'Thực thi luồng đánh giá tự động: Theo dõi trạng thái hoàn thành của từng khối tác vụ với hiệu ứng phản hồi thời gian thực.',
        'Phân tích ma trận kết quả: So sánh điểm số chất lượng, độ chính xác suy luận, thời gian đáp ứng và xuất biểu đồ tổng hợp.',
      ],
      stepsEn: [
        'Drag-and-drop node placement: Place model inputs, dataset loaders, evaluators, and report nodes onto the visual flow canvas.',
        'Top open-source tool integration: Supports LM-Evaluation-Harness, Inspect AI, Promptfoo, Ragas, SWE-Bench, Pytest Runner, and PhDLab Research Harness.',
        'Interactive wire routing: Connect model generation outputs directly into evaluation metric inputs intuitively.',
        'Automated pipeline execution: Track real-time execution states with glowing connection lines and node progress telemetry.',
        'Benchmark matrix analytics: Compare accuracy, reasoning throughput, latency, and export comparative evaluation plots.',
      ],
      actionLabelVi: 'Mở Harness Studio Kéo thả',
      actionLabelEn: 'Open Harness Studio',
      actionIcon: <Workflow size={13} style={{ marginRight: 5 }} />,
      onAction: () => openDrawer('harness'),
    },
    {
      id: 'pure-phd-lab-native',
      number: 10,
      icon: <HardDrive size={20} color="#14b8a6" />,
      categoryVi: 'Bản địa & Bảo mật Cục bộ',
      categoryEn: 'Local-First & Air-Gapped',
      titleVi: 'Quy trình Thuần Bản địa PhD Lab Độc lập Hoàn toàn',
      titleEn: 'Pure PhD Lab Native & Zero-External-Cloud Workflow',
      descVi: 'Vận hành toàn bộ chu trình nghiên cứu hoàn toàn trên thiết bị cá nhân, không gửi dữ liệu ra ngoài, bảo vệ tuyệt đối bí mật đề tài.',
      descEn: 'Operate the complete scientific research lifecycle fully on local hardware, ensuring absolute data privacy and IP protection.',
      stepsVi: [
        'Kết nối mô hình ngôn ngữ cục bộ: Sử dụng LM Studio hoặc Ollama với các trọng số nguồn mở như Phi-4, DeepSeek hay Qwen.',
        'Lưu trữ cơ sở dữ liệu nội bộ: Toàn bộ bảng dữ liệu quan hệ, vectơ nhúng và nhật ký phiên trò chuyện nằm trong tệp SQLite trên ổ đĩa.',
        'Biên dịch tài liệu ngoại tuyến: Sử dụng công cụ Tectonic hoặc TeX Live được cài đặt sẵn trên máy tính, không cần kết nối mạng.',
        'Cách ly hoàn toàn môi trường mạng: Đảm bảo dữ liệu nghiên cứu, ý tưởng phát minh và mã nguồn độc quyền không bao giờ rời khỏi thiết bị.',
        'Toàn quyền sở hữu dữ liệu: Dễ dàng sao lưu, di chuyển trọn vẹn thư mục dự án sang bất kỳ máy tính nào khác mà không lo mất mát.',
      ],
      stepsEn: [
        'Local model inference: Run offline weights (Phi-4, DeepSeek, Qwen) through LM Studio or Ollama with zero cloud API keys.',
        'Internal data residency: All relational tables, embeddings, and chat sessions reside strictly inside local SQLite storage.',
        'Air-gapped document compilation: Compile camera-ready PDFs using local Tectonic or TeX Live engines completely offline.',
        'Zero data leakage: Proprietary algorithms, novel formulas, and unpublished drafts never transmit over the external internet.',
        '100% data sovereignty: Easily archive, copy, or transfer the complete research project directory between local machines without friction.',
      ],
      actionLabelVi: 'Cài đặt Mô hình Cục bộ',
      actionLabelEn: 'Local Model Settings',
      actionIcon: <Settings size={13} style={{ marginRight: 5 }} />,
      onAction: () => openSettings(),
      secondaryActionLabelVi: 'Mở Quản lý Không gian Dự án',
      secondaryActionLabelEn: 'Open Workspaces',
      secondaryActionIcon: <FolderOpen size={13} style={{ marginRight: 5 }} />,
      onSecondaryAction: () => openDrawer('projects'),
    },
  ];

  const query = filterText.trim().toLowerCase();
  const filteredWorkflows = workflowsList.filter((wf) => {
    if (!query) return true;
    const isVi = language === 'vi';
    if (isVi) {
      return (
        wf.titleVi.toLowerCase().includes(query) ||
        wf.categoryVi.toLowerCase().includes(query) ||
        wf.descVi.toLowerCase().includes(query) ||
        wf.stepsVi.some((s) => s.toLowerCase().includes(query))
      );
    }
    return (
      wf.titleEn.toLowerCase().includes(query) ||
      wf.categoryEn.toLowerCase().includes(query) ||
      wf.descEn.toLowerCase().includes(query) ||
      wf.stepsEn.some((s) => s.toLowerCase().includes(query))
    );
  });

  return (
    <div
      style={{
        display: 'flex',
        flexDirection: 'column',
        height: '100%',
        background: 'var(--bg)',
        color: 'var(--fg)',
        overflowY: 'auto',
      }}
    >
      {/* Hero Banner */}
      <div
        style={{
          background: 'linear-gradient(135deg, rgba(185, 75, 28, 0.14) 0%, rgba(14, 165, 233, 0.1) 100%)',
          borderBottom: '1px solid var(--line)',
          padding: '24px 28px',
          display: 'flex',
          flexDirection: 'column',
          gap: 14,
        }}
      >
        <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', flexWrap: 'wrap', gap: 12 }}>
          <div style={{ display: 'flex', alignItems: 'center', gap: 12 }}>
            <div
              style={{
                width: 40,
                height: 40,
                borderRadius: 10,
                background: 'var(--accent)',
                display: 'flex',
                alignItems: 'center',
                justifyContent: 'center',
                color: '#ffffff',
                boxShadow: '0 4px 14px rgba(185, 75, 28, 0.35)',
              }}
            >
              <Compass size={22} />
            </div>
            <div>
              <div
                style={{
                  fontSize: 11,
                  fontWeight: 700,
                  textTransform: 'uppercase',
                  letterSpacing: 0.8,
                  color: 'var(--accent)',
                }}
              >
                {t('PHD RESEARCH LAB · HƯỚNG DẪN & NHẬP MÔN', 'PHD RESEARCH LAB · ONBOARDING & MANUAL')}
              </div>
              <h2 style={{ margin: 0, fontSize: 19, fontWeight: 800 }}>
                {t('Sổ tay & Hướng dẫn Sử dụng Chi tiết cho Người Mới', 'User Guide & Beginner Onboarding Manual')}
              </h2>
            </div>
          </div>

          {/* Quick Language Toggle inside Guide */}
          <button
            type="button"
            className="btn sm ghost"
            onClick={toggleLanguage}
            title={t('Chuyển đổi ngôn ngữ hiển thị của sổ tay', 'Toggle guide display language')}
            style={{
              borderRadius: 999,
              padding: '5px 12px',
              border: '1px solid var(--line-2)',
              background: 'var(--panel)',
              fontWeight: 600,
              fontSize: 12,
              display: 'inline-flex',
              alignItems: 'center',
              gap: 6,
            }}
          >
            <Languages size={14} color="var(--accent)" />
            <span>{language === 'vi' ? 'Tiếng Việt (VI)' : 'English (EN)'}</span>
            <span style={{ fontSize: 10, opacity: 0.6 }}>• {t('Bấm để đổi', 'Click to switch')}</span>
          </button>
        </div>

        <p style={{ margin: 0, fontSize: 13, lineHeight: 1.65, color: 'var(--fg)', maxWidth: 880 }}>
          {t(
            'Chào mừng bạn đến với PhD Research Lab — Hệ điều hành nghiên cứu khoa học tích hợp AI Đa tác nhân. Sổ tay này cung cấp hướng dẫn tường tận từng bước: từ khởi tạo thư mục dự án cục bộ, kết nối mô hình AI (Mô hình Cục bộ Ngoại tuyến / API Đám mây), khai thác thư viện PDF & Google Scholar, tùy biến hồ sơ Agent 3D, đến viết bài báo LaTeX và chạy thí nghiệm tự động hóa.',
            'Welcome to PhD Research Lab — the comprehensive Multi-Agent Research Operating System. This guide provides comprehensive, step-by-step instructions: from setting up local project workspaces, configuring AI models (Local Offline Phi-4 / Cloud APIs), extracting PDFs & Google Scholar citations, personalizing 3D agent profiles, to drafting publication-ready LaTeX papers and automating experimental workflows.'
          )}
        </p>

        {/* Quick Action Navigation Pills */}
        <div style={{ display: 'flex', alignItems: 'center', gap: 8, flexWrap: 'wrap', marginTop: 4 }}>
          <button
            type="button"
            className="btn sm accent"
            onClick={() => openDrawer('projects')}
            style={{ borderRadius: 999, fontWeight: 600, padding: '5px 12px' }}
          >
            <HardDrive size={13} style={{ marginRight: 5 }} />
            <span>{t('Không gian Dự án', 'Workspaces')}</span>
          </button>
          <button
            type="button"
            className="btn sm ghost"
            onClick={() => openSettings()}
            style={{ borderRadius: 999, padding: '5px 12px' }}
          >
            <Settings size={13} style={{ marginRight: 5 }} />
            <span>{t('Cài đặt Mô hình AI & Models', 'Model Settings')}</span>
          </button>
          <button
            type="button"
            className="btn sm ghost"
            onClick={() => open3DOffice()}
            style={{ borderRadius: 999, padding: '5px 12px' }}
          >
            <Bot size={13} style={{ marginRight: 5 }} />
            <span>{t('Khám phá Lab 3D', 'Explore 3D Lab')}</span>
          </button>
          <button
            type="button"
            className="btn sm ghost"
            onClick={() => setMainView('chat')}
            style={{ borderRadius: 999, padding: '5px 12px' }}
          >
            <MessageSquare size={13} style={{ marginRight: 5 }} />
            <span>{t('Vào Khu vực Trò chuyện', 'Go to Chat')}</span>
          </button>
        </div>
      </div>

      {/* Tabs Bar & Quick Search */}
      <div
        style={{
          display: 'flex',
          alignItems: 'center',
          justifyContent: 'space-between',
          padding: '10px 24px',
          background: 'var(--panel)',
          borderBottom: '1px solid var(--line)',
          gap: 12,
          flexWrap: 'wrap',
          position: 'sticky',
          top: 0,
          zIndex: 10,
        }}
      >
        <div style={{ display: 'flex', alignItems: 'center', gap: 6, flexWrap: 'wrap' }}>
          {tabs.map((tab) => (
            <button
              key={tab.id}
              type="button"
              className={`btn sm ${activeTab === tab.id ? 'accent' : 'ghost'}`}
              onClick={() => setActiveTab(tab.id)}
              style={{
                borderRadius: 8,
                fontWeight: activeTab === tab.id ? 700 : 500,
                display: 'inline-flex',
                alignItems: 'center',
                gap: 6,
              }}
            >
              {tab.icon}
              <span>{tab.label}</span>
            </button>
          ))}
        </div>

        {/* Search box within guide */}
        <div style={{ position: 'relative', width: 240 }}>
          <Search size={13} style={{ position: 'absolute', left: 9, top: '50%', transform: 'translateY(-50%)', color: 'var(--muted)' }} />
          <input
            className="input sm"
            value={filterText}
            onChange={(e) => setFilterText(e.target.value)}
            placeholder={t('Tìm nhanh trong sổ tay…', 'Search guide topics…')}
            style={{ paddingLeft: 28, borderRadius: 8, width: '100%', fontSize: 12 }}
          />
        </div>
      </div>

      {/* Main Content Area */}
      <div style={{ padding: '24px 28px', maxWidth: 1000, margin: '0 auto', width: '100%' }}>
        {/* TAB 1: QUICKSTART */}
        {activeTab === 'quickstart' && (
          <div style={{ display: 'flex', flexDirection: 'column', gap: 24 }}>
            <div>
              <h3 style={{ margin: 0, fontSize: 18, fontWeight: 700, display: 'flex', alignItems: 'center', gap: 8 }}>
                <Rocket size={20} color="var(--accent)" />
                <span>{t('Quy trình 5 bước Nghiên cứu Khởi đầu cho Người Mới', '5-Step Research Quickstart Workflow')}</span>
              </h3>
              <p style={{ margin: '6px 0 0', fontSize: 13, color: 'var(--muted)', lineHeight: 1.6 }}>
                {t(
                  'Dành cho nghiên cứu sinh và nhà khoa học bắt đầu làm quen với hệ thống. Hãy thực hiện tuần tự theo 5 bước dưới đây để thiết lập môi trường nghiên cứu hoàn hảo.',
                  'Designed for researchers and scholars onboarding into the system. Follow these 5 consecutive steps to set up your comprehensive research environment.'
                )}
              </p>
            </div>

            {/* Step 1 */}
            <div className="panelbox" style={{ padding: 20, borderRadius: 12, border: '1px solid var(--line)', background: 'var(--panel)' }}>
              <div style={{ display: 'flex', alignItems: 'center', gap: 10, marginBottom: 10 }}>
                <span style={{ width: 26, height: 26, borderRadius: '50%', background: 'var(--accent)', color: '#fff', display: 'flex', alignItems: 'center', justifyContent: 'center', fontSize: 13, fontWeight: 800 }}>
                  1
                </span>
                <b style={{ fontSize: 15.5 }}>
                  {t('Khởi tạo Dự án & Thiết lập Thư mục Lưu trữ Cục bộ', 'Create Research Project & Storage Directories')}
                </b>
              </div>
              <p style={{ margin: '0 0 12px', fontSize: 13, lineHeight: 1.65, color: 'var(--fg)' }}>
                {t(
                  'Hệ thống PhD Research Lab vận hành theo nguyên lý Local-First: toàn bộ tài liệu nghiên cứu, CSDL quan hệ SQLite, vector memory và lịch sử chat đều được lưu trữ hoàn toàn trên máy tính của bạn, không lo bị phụ thuộc vào cloud hoặc rò rỉ dữ liệu.',
                  'PhD Research Lab follows a strict Local-First architecture: all academic literature, relational SQLite records, vector memories, and experiment history reside directly on your local computer.'
                )}
              </p>

              <div style={{ background: 'var(--bg-2)', padding: 12, borderRadius: 8, border: '1px solid var(--line-2)', marginBottom: 12, fontSize: 12.5, lineHeight: 1.6 }}>
                <b>{t('Cấu trúc thư mục chuẩn của một Dự án:', 'Standard Research Project Hierarchy:')}</b>
                <ul style={{ margin: '6px 0 0', paddingLeft: 20, color: 'var(--fg)' }}>
                  <li><code>data_dir</code>: {t('Thư mục gốc lưu trữ dữ liệu thực nghiệm, cơ sở dữ liệu lab.db và vector index.', 'Root directory for experiment data, SQLite database lab.db, and vector embeddings.')}</li>
                  <li><code>references_dir</code>: {t('Kho chứa các tệp PDF bài báo khoa học, sách chuyên khảo đã tải về.', 'Directory for downloaded academic research PDF papers and monographs.')}</li>
                  <li><code>runs/</code>: {t('Lưu trữ kết quả các phiên chạy tính toán, code mô phỏng, log kiểm định và artifacts.', 'Stores computational execution runs, simulation scripts, test logs, and artifacts.')}</li>
                  <li><code>notes/</code>: {t('Ghi chú học thuật, biên bản trao đổi và đề cương phác thảo.', 'Academic notes, research meeting minutes, and working outlines.')}</li>
                </ul>
              </div>

              <div style={{ fontSize: 12.5, lineHeight: 1.6, color: 'var(--fg)', marginBottom: 12 }}>
                <b>{t('💡 Cách thực hiện:', '💡 Step-by-Step Action:')}</b>
                <ol style={{ margin: '4px 0 0', paddingLeft: 20 }}>
                  <li>{t('Mở bảng "Không gian Dự án" ở thanh bên trái.', 'Open "Workspaces" in the left sidebar drawer.')}</li>
                  <li>{t('Chọn "Dự án Mới" hoặc "Mở Dự án".', 'Click "New Project" or "Open Existing Project".')}</li>
                  <li>{t('Bấm nút "Duyệt máy" để chọn trực tiếp thư mục từ các ổ đĩa máy tính trực quan mà không cần gõ đường dẫn bằng tay.', 'Use the "Browse" button to directly pick local drive directories without manual path typing.')}</li>
                </ol>
              </div>

              <div style={{ display: 'flex', gap: 8 }}>
                <button className="btn sm accent" onClick={() => openDrawer('projects')}>
                  <FolderOpen size={13} style={{ marginRight: 5 }} />
                  {t('Mở Quản lý Dự án', 'Open Workspaces Drawer')}
                </button>
              </div>
            </div>

            {/* Step 2 */}
            <div className="panelbox" style={{ padding: 20, borderRadius: 12, border: '1px solid var(--line)', background: 'var(--panel)' }}>
              <div style={{ display: 'flex', alignItems: 'center', gap: 10, marginBottom: 10 }}>
                <span style={{ width: 26, height: 26, borderRadius: '50%', background: 'var(--accent)', color: '#fff', display: 'flex', alignItems: 'center', justifyContent: 'center', fontSize: 13, fontWeight: 800 }}>
                  2
                </span>
                <b style={{ fontSize: 15.5 }}>
                  {t('Cấu hình Nhà cung cấp AI & Kết nối Mô hình (Mô hình Cục bộ Ngoại tuyến / API Đám mây)', 'Configure AI Models & LLM Providers')}
                </b>
              </div>
              <p style={{ margin: '0 0 12px', fontSize: 13, lineHeight: 1.65, color: 'var(--fg)' }}>
                {t(
                  'PhD Research Lab hỗ trợ linh hoạt cả mô hình AI cục bộ ngoại tuyến lẫn các mô hình đám mây thương mại hàng đầu. Bạn có thể cấu hình độc lập ngôn ngữ giao diện và ngôn ngữ suy luận của AI.',
                  'PhD Research Lab seamlessly orchestrates both local offline LLMs and leading commercial cloud providers. Interface language and AI reasoning language are independently configurable.'
                )}
              </p>

              <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(280px, 1fr))', gap: 12, marginBottom: 12 }}>
                <div style={{ padding: 12, borderRadius: 8, background: 'var(--bg-2)', border: '1px solid var(--line-2)' }}>
                  <b style={{ color: 'var(--accent)', fontSize: 13 }}>{t('💻 Mô hình Cục bộ Ngoại tuyến', '💻 Local Offline Models (LM Studio / Ollama)')}</b>
                  <p style={{ margin: '4px 0 0', fontSize: 12, lineHeight: 1.5, color: 'var(--fg)' }}>
                    {t(
                      'Khởi động LM Studio và nạp mô hình (ví dụ: phi-4, deepseek-r1, qwen2.5-coder). Bật Local Inference Server tại http://127.0.0.1:1234/v1. Không cần API key, miễn phí hoàn toàn và bảo mật 100%.',
                      'Launch LM Studio with local weights (e.g. phi-4, deepseek-r1). Start the local server at http://127.0.0.1:1234/v1. Zero cost, no API keys, and 100% offline data sovereignty.'
                    )}
                  </p>
                </div>
                <div style={{ padding: 12, borderRadius: 8, background: 'var(--bg-2)', border: '1px solid var(--line-2)' }}>
                  <b style={{ color: '#0ea5e9', fontSize: 13 }}>{t('☁️ Mô hình Thương mại (Claude, GPT-4o, Gemini)', '☁️ Commercial Cloud Models')}</b>
                  <p style={{ margin: '4px 0 0', fontSize: 12, lineHeight: 1.5, color: 'var(--fg)' }}>
                    {t(
                      'Điền khóa API cho Anthropic Claude, OpenAI GPT, Google Gemini. Nếu máy tính của bạn chưa đăng nhập tài khoản trả phí hoặc CLI AI, hệ thống sẽ mở ứng dụng hoặc chuyển tiếp để đăng nhập.',
                      'Configure API keys for Anthropic Claude 3.5 Sonnet, OpenAI GPT-4o, Google Gemini. If your machine is not logged in to AI CLI/subscription, the app forwards you to complete login.'
                    )}
                  </p>
                </div>
              </div>

              <div style={{ fontSize: 12.5, lineHeight: 1.6, color: 'var(--fg)', marginBottom: 12 }}>
                <b>{t('🌐 Tách biệt Ngôn ngữ Giao diện & Ngôn ngữ AI:', '🌐 Independent UI & AI Language Separation:')}</b>
                <div style={{ marginTop: 4 }}>
                  {t(
                    '• Ngôn ngữ giao diện: Hiển thị menu, nút bấm, nhãn công cụ bằng Tiếng Việt hoặc Tiếng Anh.\n• Ngôn ngữ phản hồi của AI: Chọn "Tự động" (theo ngôn ngữ câu hỏi), "Tiếng Việt", hoặc "English". Cài đặt này được lưu độc lập trong mục Cài đặt → Giao diện & Ngôn ngữ.',
                    '• UI Language: Controls menus, buttons, and system labels (VI or EN).\n• AI Response Language: Configures model outputs (Auto-detect from prompt, Vietnamese, or English). Configured in Settings → Language.'
                  )}
                </div>
              </div>

              <div style={{ display: 'flex', gap: 8 }}>
                <button className="btn sm ghost" onClick={() => openSettings()}>
                  <Settings size={13} style={{ marginRight: 5 }} />
                  {t('Mở Cài đặt Mô hình', 'Open Model Settings')}
                </button>
              </div>
            </div>

            {/* Step 3 */}
            <div className="panelbox" style={{ padding: 20, borderRadius: 12, border: '1px solid var(--line)', background: 'var(--panel)' }}>
              <div style={{ display: 'flex', alignItems: 'center', gap: 10, marginBottom: 10 }}>
                <span style={{ width: 26, height: 26, borderRadius: '50%', background: 'var(--accent)', color: '#fff', display: 'flex', alignItems: 'center', justifyContent: 'center', fontSize: 13, fontWeight: 800 }}>
                  3
                </span>
                <b style={{ fontSize: 15.5 }}>
                  {t('Nạp Tài liệu vào Thư viện Khoa học & Tìm kiếm Google Scholar / arXiv', 'Import Papers into Scientific PDF Library')}
                </b>
              </div>
              <p style={{ margin: '0 0 12px', fontSize: 13, lineHeight: 1.65, color: 'var(--fg)' }}>
                {t(
                  'Thư viện Khoa học là trung tâm tri thức của phòng lab, hỗ trợ đọc và lập chỉ mục ngữ nghĩa cho hàng nghìn bài báo PDF, phục vụ việc tìm kiếm tài liệu và đối chiếu bằng chứng.',
                  'The Academic Library indexes thousands of research PDFs, enabling instant semantic search, multi-venue discovery, and automated evidence grounding.'
                )}
              </p>

              <div style={{ background: 'var(--bg-2)', padding: 12, borderRadius: 8, border: '1px solid var(--line-2)', marginBottom: 12, fontSize: 12.5, lineHeight: 1.6 }}>
                <b>{t('Các tính năng chủ đạo trong Thư viện:', 'Key Library Features:')}</b>
                <ul style={{ margin: '6px 0 0', paddingLeft: 20, color: 'var(--fg)' }}>
                  <li><b>{t('Tìm kiếm đa nguồn trực tiếp:', 'Direct Multi-Source Search:')}</b> {t('Tìm bài báo trên Google Scholar, Semantic Scholar, arXiv hoặc tìm nhanh bằng mã số định danh DOI.', 'Search across Google Scholar, Semantic Scholar, arXiv, or query by DOI.')}</li>
                  <li><b>{t('Trích nguồn tham khảo:', 'Citation Extraction:')}</b> {t('Lấy thông tin trích dẫn chi tiết từ Google Scholar, xuất chuẩn BibTeX, APA, IEEE, Harvard cho bài báo LaTeX chỉ với 1 cú click.', 'Extract citations with Google Scholar integration, export BibTeX, APA, IEEE for LaTeX in 1 click.')}</li>
                  <li><b>{t('Phân hạng tạp chí & hội nghị:', 'Venue Tier Classification:')}</b> {t('Tự động nhận diện phân hạng uy tín: Core A*, Q1, Q2, Tier 1 (Nature, NeurIPS, ICML, CVPR, IEEE TPAMI).', 'Automatically tags venue tiers: Core A*, Q1, Q2, Tier 1 (Nature, NeurIPS, ICML, CVPR).')}</li>
                  <li><b>{t('Bộ xem trước PDF tích hợp:', 'In-Browser PDF Viewer:')}</b> {t('Xem trực tiếp tệp PDF ngay trong ứng dụng, có chế độ phóng to toàn màn hình và xem theo từng trang.', 'Read PDF papers directly with built-in viewer, full-screen toggle, and page navigation.')}</li>
                </ul>
              </div>

              <div style={{ display: 'flex', gap: 8 }}>
                <button className="btn sm ghost" onClick={() => openDrawer('library')}>
                  <BookOpen size={13} style={{ marginRight: 5 }} />
                  {t('Mở Thư viện Bài báo', 'Open Academic Library Drawer')}
                </button>
              </div>
            </div>

            {/* Step 4 */}
            <div className="panelbox" style={{ padding: 20, borderRadius: 12, border: '1px solid var(--line)', background: 'var(--panel)' }}>
              <div style={{ display: 'flex', alignItems: 'center', gap: 10, marginBottom: 10 }}>
                <span style={{ width: 26, height: 26, borderRadius: '50%', background: 'var(--accent)', color: '#fff', display: 'flex', alignItems: 'center', justifyContent: 'center', fontSize: 13, fontWeight: 800 }}>
                  4
                </span>
                <b style={{ fontSize: 15.5 }}>
                  {t('Xác lập Đề cương Nghiên cứu 5 Cấp độ', 'Establish 5-Level Research Outline')}
                </b>
              </div>
              <p style={{ margin: '0 0 12px', fontSize: 13, lineHeight: 1.65, color: 'var(--fg)' }}>
                {t(
                  'Đề cương nghiên cứu là kim chỉ nam định hướng học thuật cho toàn bộ hội đồng tác nhân AI, ngăn chặn tuyệt đối tình trạng lạc đề, phân mảnh hoặc ảo giác tri thức trong quá trình nghiên cứu tự trị.',
                  'The 5-Level Research Outline anchors all AI agents to a rigorous academic roadmap, preventing topic drift, hallucination, and fragmented inquiry.'
                )}
              </p>

              <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(180px, 1fr))', gap: 10, marginBottom: 12 }}>
                <div style={{ padding: 10, borderRadius: 8, background: 'var(--bg-2)', border: '1px solid var(--line-2)' }}>
                  <b style={{ color: 'var(--accent)', fontSize: 12 }}>1. Keywords (Từ khóa)</b>
                  <div style={{ fontSize: 11.5, color: 'var(--muted)', marginTop: 2 }}>{t('Khung từ khóa khoa học trọng tâm', 'Core academic domain keywords')}</div>
                </div>
                <div style={{ padding: 10, borderRadius: 8, background: 'var(--bg-2)', border: '1px solid var(--line-2)' }}>
                  <b style={{ color: '#0ea5e9', fontSize: 12 }}>2. Topic (Chủ đề)</b>
                  <div style={{ fontSize: 11.5, color: 'var(--muted)', marginTop: 2 }}>{t('Xác định bài toán nghiên cứu hẹp', 'Specific research problem definition')}</div>
                </div>
                <div style={{ padding: 10, borderRadius: 8, background: 'var(--bg-2)', border: '1px solid var(--line-2)' }}>
                  <b style={{ color: '#f59e0b', fontSize: 12 }}>3. Direction (Hướng đột phá)</b>
                  <div style={{ fontSize: 11.5, color: 'var(--muted)', marginTop: 2 }}>{t('Điểm mới so với văn hiến cũ', 'Novelty relative to prior art')}</div>
                </div>
                <div style={{ padding: 10, borderRadius: 8, background: 'var(--bg-2)', border: '1px solid var(--line-2)' }}>
                  <b style={{ color: '#10b981', fontSize: 12 }}>4. Method (Phương pháp)</b>
                  <div style={{ fontSize: 11.5, color: 'var(--muted)', marginTop: 2 }}>{t('Kiến trúc kỹ thuật & thuật toán', 'Algorithms & technical methods')}</div>
                </div>
                <div style={{ padding: 10, borderRadius: 8, background: 'var(--bg-2)', border: '1px solid var(--line-2)' }}>
                  <b style={{ color: '#8b5cf6', fontSize: 12 }}>5. Proposal (Đề xuất)</b>
                  <div style={{ fontSize: 11.5, color: 'var(--muted)', marginTop: 2 }}>{t('Bản đề xuất đầy đủ & metrics', 'Full research plan & metrics')}</div>
                </div>
              </div>

              <div style={{ display: 'flex', gap: 8 }}>
                <button className="btn sm ghost" onClick={() => openDrawer('outline')}>
                  <Compass size={13} style={{ marginRight: 5 }} />
                  {t('Mở Đề cương 5 Cấp độ', 'Open 5-Level Outline Drawer')}
                </button>
              </div>
            </div>

            {/* Step 5 */}
            <div className="panelbox" style={{ padding: 20, borderRadius: 12, border: '1px solid var(--line)', background: 'var(--panel)' }}>
              <div style={{ display: 'flex', alignItems: 'center', gap: 10, marginBottom: 10 }}>
                <span style={{ width: 26, height: 26, borderRadius: '50%', background: 'var(--accent)', color: '#fff', display: 'flex', alignItems: 'center', justifyContent: 'center', fontSize: 13, fontWeight: 800 }}>
                  5
                </span>
                <b style={{ fontSize: 15.5 }}>
                  {t('Vận hành Tự động hóa Tối đa & Hội đồng Phản biện Đa tác nhân', 'Interact with Multi-Agents & Enable Maximum Automation')}
                </b>
              </div>
              <p style={{ margin: '0 0 12px', fontSize: 13, lineHeight: 1.65, color: 'var(--fg)' }}>
                {t(
                  'Hệ thống điều phối các tác nhân AI làm việc song song không giới hạn: từ tổng hợp tài liệu, phát hiện khoảng trống tri thức, chạy mã Python thực nghiệm trong Native Code, đến chấm điểm phản biện R1–R3 và biên soạn bản thảo LaTeX.',
                  'The system coordinates multi-agent parallel execution: from deep literature synthesis, gap analysis, automated Native Code Python simulation, to calibrated R1–R3 peer reviews and LaTeX manuscript authoring.'
                )}
              </p>

              <div style={{ background: 'var(--bg-2)', padding: 12, borderRadius: 8, border: '1px solid var(--line-2)', marginBottom: 12, fontSize: 12.5, lineHeight: 1.6 }}>
                <b>{t('Chu trình Nghiên cứu Tự trị:', 'Autonomous Research Loop:')}</b>
                <div style={{ marginTop: 4, fontFamily: 'var(--mono)', fontSize: 11.5, color: 'var(--accent)' }}>
                  {t(
                    '1. Khám phá tài liệu /lit ➔ 2. Xây dựng giả thuyết /hypothesis ➔ 3. Thiết kế thí nghiệm /experiment ➔ 4. Chạy mã thực nghiệm /code ➔ 5. Kiểm định bằng chứng /claims ➔ 6. Hội đồng phản biện /review ➔ 7. Soạn thảo LaTeX /latex',
                    '1. Literature Survey (/lit) ➔ 2. Hypothesize (/hypothesis) ➔ 3. Protocol Design (/experiment) ➔ 4. Execute Code (Native Code) ➔ 5. Verify Claims (/claims) ➔ 6. Peer Review (/review) ➔ 7. Draft LaTeX (/latex)'
                  )}
                </div>
              </div>

              <div style={{ display: 'flex', gap: 8 }}>
                <button className="btn sm accent" onClick={() => setMainView('chat')}>
                  <MessageSquare size={13} style={{ marginRight: 5 }} />
                  {t('Bắt đầu Trò chuyện', 'Start Chatting')}
                </button>
                <button className="btn sm ghost" onClick={() => open3DOffice()}>
                  <Bot size={13} style={{ marginRight: 5 }} />
                  {t('Vào Phòng Lab 3D', 'Enter 3D Lab')}
                </button>
              </div>
            </div>
          </div>
        )}

        {/* TAB 2: ALL RESEARCH WORKFLOWS */}
        {activeTab === 'workflows' && (
          <div style={{ display: 'flex', flexDirection: 'column', gap: 24 }}>
            <div>
              <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', flexWrap: 'wrap', gap: 12 }}>
                <h3 style={{ margin: 0, fontSize: 18, fontWeight: 700, display: 'flex', alignItems: 'center', gap: 8 }}>
                  <Workflow size={20} color="var(--accent)" />
                  <span>{t('Danh mục Toàn bộ Quy trình Nghiên cứu Khoa học', 'Comprehensive Scientific Research Workflows Catalog')}</span>
                </h3>
                <span
                  style={{
                    fontSize: 12,
                    fontWeight: 700,
                    padding: '3px 10px',
                    borderRadius: 999,
                    background: 'rgba(185, 75, 28, 0.12)',
                    color: 'var(--accent)',
                    border: '1px solid rgba(185, 75, 28, 0.25)',
                  }}
                >
                  {t('10 Quy trình Chuyên sâu', '10 Specialized Workflows')}
                </span>
              </div>
              <p style={{ margin: '6px 0 0', fontSize: 13, color: 'var(--muted)', lineHeight: 1.6 }}>
                {t(
                  'Nền tảng PhD Research Lab tích hợp sẵn 10 quy trình nghiên cứu chuyên sâu, bao quát toàn diện từ giai đoạn tìm kiếm ý tưởng ban đầu, phân rã nhiệm vụ tự hành, thực nghiệm có kiểm soát, đánh giá điểm chuẩn kéo thả tùy chỉnh, đến hoàn thiện bài báo LaTeX xuất bản quốc tế.',
                  'PhD Research Lab integrates 10 specialized research workflows, spanning from initial ideation, autonomous task decomposition, controlled experiments, visual drag-and-drop benchmarking harness, to publication-ready LaTeX paper compilation.'
                )}
              </p>
            </div>

            {/* Quick Metrics Bar */}
            <div
              style={{
                display: 'grid',
                gridTemplateColumns: 'repeat(auto-fit, minmax(200px, 1fr))',
                gap: 12,
                padding: '14px 18px',
                borderRadius: 10,
                background: 'var(--bg-2)',
                border: '1px solid var(--line-2)',
              }}
            >
              <div style={{ display: 'flex', alignItems: 'center', gap: 10 }}>
                <CheckCircle2 size={18} color="#10b981" />
                <div>
                  <div style={{ fontSize: 11, color: 'var(--muted)', fontWeight: 600 }}>{t('Khảo sát & Đề xuất', 'Exploration & Ideation')}</div>
                  <div style={{ fontSize: 13, fontWeight: 700 }}>{t('Đa nguồn Học thuật', 'Multi-Source Synthesis')}</div>
                </div>
              </div>
              <div style={{ display: 'flex', alignItems: 'center', gap: 10 }}>
                <ShieldCheck size={18} color="#06b6d4" />
                <div>
                  <div style={{ fontSize: 11, color: 'var(--muted)', fontWeight: 600 }}>{t('Bảo mật & Toàn vẹn', 'Security & Sovereignty')}</div>
                  <div style={{ fontSize: 13, fontWeight: 700 }}>{t('Bảo mật Cục bộ Tuyệt đối', '100% Local-First Data')}</div>
                </div>
              </div>
              <div style={{ display: 'flex', alignItems: 'center', gap: 10 }}>
                <Sliders size={18} color="#f59e0b" />
                <div>
                  <div style={{ fontSize: 11, color: 'var(--muted)', fontWeight: 600 }}>{t('Harness Điểm chuẩn', 'Harness Benchmarking')}</div>
                  <div style={{ fontSize: 13, fontWeight: 700 }}>{t('7 Công cụ Mã nguồn Mở', '7 Open Tools Integrated')}</div>
                </div>
              </div>
              <div style={{ display: 'flex', alignItems: 'center', gap: 10 }}>
                <FileText size={18} color="#8b5cf6" />
                <div>
                  <div style={{ fontSize: 11, color: 'var(--muted)', fontWeight: 600 }}>{t('Biên dịch Bản thảo', 'Manuscript Engine')}</div>
                  <div style={{ fontSize: 13, fontWeight: 700 }}>{t('Biên dịch Cục bộ & Online', 'Local & Online Compilation')}</div>
                </div>
              </div>
            </div>

            {/* List of Workflows */}
            {filteredWorkflows.length === 0 ? (
              <div style={{ padding: 32, textAlign: 'center', color: 'var(--muted)', fontSize: 13, background: 'var(--panel)', borderRadius: 10, border: '1px solid var(--line)' }}>
                {t('Không tìm thấy quy trình nghiên cứu nào phù hợp với từ khóa tìm kiếm.', 'No research workflows found matching your search query.')}
              </div>
            ) : (
              <div style={{ display: 'flex', flexDirection: 'column', gap: 18 }}>
                {filteredWorkflows.map((wf) => {
                  const title = language === 'vi' ? wf.titleVi : wf.titleEn;
                  const category = language === 'vi' ? wf.categoryVi : wf.categoryEn;
                  const desc = language === 'vi' ? wf.descVi : wf.descEn;
                  const steps = language === 'vi' ? wf.stepsVi : wf.stepsEn;
                  const actionLabel = language === 'vi' ? wf.actionLabelVi : wf.actionLabelEn;
                  const secActionLabel = language === 'vi' ? wf.secondaryActionLabelVi : wf.secondaryActionLabelEn;

                  return (
                    <div
                      key={wf.id}
                      className="panelbox"
                      style={{
                        padding: 20,
                        borderRadius: 12,
                        border: '1px solid var(--line)',
                        background: 'var(--panel)',
                        display: 'flex',
                        flexDirection: 'column',
                        gap: 14,
                        transition: 'box-shadow 0.2s ease',
                      }}
                    >
                      {/* Workflow Card Header */}
                      <div style={{ display: 'flex', alignItems: 'flex-start', justifyContent: 'space-between', gap: 12, flexWrap: 'wrap' }}>
                        <div style={{ display: 'flex', alignItems: 'center', gap: 10 }}>
                          <span
                            style={{
                              width: 32,
                              height: 32,
                              borderRadius: 8,
                              background: 'var(--bg-2)',
                              border: '1px solid var(--line)',
                              display: 'flex',
                              alignItems: 'center',
                              justifyContent: 'center',
                            }}
                          >
                            {wf.icon}
                          </span>
                          <div>
                            <div style={{ display: 'flex', alignItems: 'center', gap: 8, flexWrap: 'wrap' }}>
                              <span
                                style={{
                                  fontSize: 10.5,
                                  fontWeight: 700,
                                  textTransform: 'uppercase',
                                  letterSpacing: 0.5,
                                  padding: '2px 8px',
                                  borderRadius: 4,
                                  background: 'var(--bg-2)',
                                  border: '1px solid var(--line-2)',
                                  color: 'var(--accent)',
                                }}
                              >
                                {category}
                              </span>
                              <span style={{ fontSize: 11, color: 'var(--muted)', fontWeight: 600 }}>
                                #{wf.number}
                              </span>
                            </div>
                            <b style={{ fontSize: 15.5, display: 'block', marginTop: 3 }}>{title}</b>
                          </div>
                        </div>
                      </div>

                      {/* Workflow Description */}
                      <p style={{ margin: 0, fontSize: 13, lineHeight: 1.65, color: 'var(--fg)' }}>
                        {desc}
                      </p>

                      {/* Step by Step Breakdown */}
                      <div
                        style={{
                          background: 'var(--bg-2)',
                          padding: 14,
                          borderRadius: 8,
                          border: '1px solid var(--line-2)',
                          fontSize: 12.5,
                          lineHeight: 1.65,
                        }}
                      >
                        <b style={{ display: 'block', marginBottom: 6, color: 'var(--fg)' }}>
                          {t('Tuần tự các bước thực thi:', 'Step-by-Step Execution Sequence:')}
                        </b>
                        <ol style={{ margin: 0, paddingLeft: 20, display: 'flex', flexDirection: 'column', gap: 5, color: 'var(--fg)' }}>
                          {steps.map((st, idx) => (
                            <li key={idx}>
                              <span>{st}</span>
                            </li>
                          ))}
                        </ol>
                      </div>

                      {/* Action Buttons */}
                      <div style={{ display: 'flex', alignItems: 'center', gap: 8, flexWrap: 'wrap', paddingTop: 2 }}>
                        <button
                          type="button"
                          className="btn sm accent"
                          onClick={wf.onAction}
                          style={{ borderRadius: 8, fontWeight: 600, padding: '5px 12px' }}
                        >
                          {wf.actionIcon}
                          <span>{actionLabel}</span>
                        </button>
                        {secActionLabel && wf.onSecondaryAction && (
                          <button
                            type="button"
                            className="btn sm ghost"
                            onClick={wf.onSecondaryAction}
                            style={{ borderRadius: 8, padding: '5px 12px' }}
                          >
                            {wf.secondaryActionIcon}
                            <span>{secActionLabel}</span>
                          </button>
                        )}
                      </div>
                    </div>
                  );
                })}
              </div>
            )}
          </div>
        )}

        {/* TAB 3: AGENTS & 3D LAB */}
        {activeTab === 'agents' && (
          <div style={{ display: 'flex', flexDirection: 'column', gap: 24 }}>
            <div>
              <h3 style={{ margin: 0, fontSize: 18, fontWeight: 700, display: 'flex', alignItems: 'center', gap: 8 }}>
                <Bot size={20} color="var(--accent)" />
                <span>{t('Hội đồng Nghiên cứu Đa tác nhân & Phòng Lab Đại học 3D', 'AI Research Advisory Board & 3D University Lab')}</span>
              </h3>
              <p style={{ margin: '6px 0 0', fontSize: 13, color: 'var(--muted)', lineHeight: 1.6 }}>
                {t(
                  'PhD Research Lab mô phỏng trung thực không gian làm việc của một viện nghiên cứu chuẩn quốc tế với 6 tác nhân AI chuyên trách, không gian 3D tương tác sống động, và tính năng cá nhân hóa tên tuổi, hồ sơ cho từng Agent.',
                  'Simulates an international research institute environment with 6 specialized agents, interactive 3D virtual lab spaces, and complete agent profile customization.'
                )}
              </p>
            </div>

            {/* Feature Highlight: Personal Profiles & Custom Agent Names */}
            <div className="panelbox" style={{ padding: 18, borderRadius: 12, border: '1px solid var(--accent)', background: 'rgba(185, 75, 28, 0.04)' }}>
              <div style={{ display: 'flex', alignItems: 'center', gap: 10, marginBottom: 8 }}>
                <UserCheck size={18} color="var(--accent)" />
                <b style={{ fontSize: 15, color: 'var(--accent)' }}>
                  {t('Tính năng Mới: Tùy biến Thông tin Cá nhân & Đổi Tên Riêng Từng Agent', 'Custom Agent Profiles & Personalized Names')}
                </b>
              </div>
              <p style={{ margin: '0 0 10px', fontSize: 13, lineHeight: 1.65, color: 'var(--fg)' }}>
                {t(
                  'Bạn có thể cá nhân hóa toàn bộ hội đồng AI theo sở thích cá nhân hoặc theo tên các nhà khoa học, giáo sư ngoài đời thực:',
                  'You can customize every agent to match your personal preference or real-world academic mentors:'
                )}
              </p>
              <ul style={{ margin: 0, paddingLeft: 20, fontSize: 12.5, lineHeight: 1.65, color: 'var(--fg)' }}>
                <li><b>{t('Đổi tên hiển thị:', 'Custom Display Name:')}</b> {t('Đặt tên riêng cho từng nhân vật (ví dụ: GS. Nguyễn Văn An, TS. Lan, Alex, etc.).', 'Give each agent a unique name (e.g. Prof. Smith, Dr. Lan, Alex, etc.).')}</li>
                <li><b>{t('Danh xưng học thuật:', 'Academic Title:')}</b> {t('Thay đổi chức danh (Giáo sư Hướng dẫn, Nghiên cứu sinh Trưởng, Phản biện viên Độc lập).', 'Customize title (Principal Investigator, Lead Postdoc, Rigorous Reviewer).')}</li>
                <li><b>{t('Màu sắc & Lời chào (Theme & Greeting):', 'Theme Color & Greeting:')}</b> {t('Chọn màu đại diện và lời chào đón riêng khi bạn click vào nhân vật.', 'Choose personalized avatar accent color and unique greeting message.')}</li>
                <li><b>{t('Cách thực hiện:', 'How to open:')}</b> {t('Nhấp vào nút "Thông tin cá nhân" (icon thẻ hồ sơ) ngay trên avatar nhân vật trong phòng Lab 3D hoặc trong danh sách Hội đồng tác nhân.', 'Click the "Personal Profile" badge button directly on the agent avatar in 3D Lab or Agent Status list.')}</li>
              </ul>
            </div>

            {/* 6 Specialized Agents Grid */}
            <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(290px, 1fr))', gap: 14 }}>
              {/* Supervisor */}
              <div className="panelbox" style={{ padding: 16, borderRadius: 10, border: '1px solid var(--line)', background: 'var(--panel)' }}>
                <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginBottom: 6 }}>
                  <b style={{ fontSize: 14, color: '#b94b1c' }}>{t('1. Giáo sư Hướng dẫn', '1. Research Supervisor (PI)')}</b>
                  <span style={{ fontSize: 10.5, padding: '2px 6px', borderRadius: 4, background: 'rgba(185, 75, 28, 0.1)', color: '#b94b1c', fontWeight: 700 }}>Lead PI</span>
                </div>
                <p style={{ margin: 0, fontSize: 12.5, lineHeight: 1.55, color: 'var(--fg)' }}>
                  {t(
                    'Định hướng học thuật chiến lược, phản biện tính mới, phê duyệt giao thức thí nghiệm, kiểm soát an toàn dữ liệu và tổng duyệt đề xuất trước khi xuất bản.',
                    'Directs strategic vision, evaluates novelty, approves experimental protocols, enforces safety bounds, and conducts final proposal sign-offs.'
                  )}
                </p>
              </div>

              {/* Researcher */}
              <div className="panelbox" style={{ padding: 16, borderRadius: 10, border: '1px solid var(--line)', background: 'var(--panel)' }}>
                <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginBottom: 6 }}>
                  <b style={{ fontSize: 14, color: '#0ea5e9' }}>{t('2. Nghiên cứu sinh Trưởng nhóm', '2. Lead Researcher (Postdoc)')}</b>
                  <span style={{ fontSize: 10.5, padding: '2px 6px', borderRadius: 4, background: 'rgba(14, 165, 233, 0.1)', color: '#0ea5e9', fontWeight: 700 }}>Research</span>
                </div>
                <p style={{ margin: 0, fontSize: 12.5, lineHeight: 1.55, color: 'var(--fg)' }}>
                  {t(
                    'Đọc và tổng hợp hàng trăm bài báo, trích xuất dữ liệu thực nghiệm, xây dựng đề cương 5 cấp, phát hiện khoảng trống tri thức và phát triển giả thuyết mới.',
                    'Synthesizes literature across hundreds of papers, extracts empirical evidence, drafts the 5-level outline, and formulates testable hypotheses.'
                  )}
                </p>
              </div>

              {/* Critic */}
              <div className="panelbox" style={{ padding: 16, borderRadius: 10, border: '1px solid var(--line)', background: 'var(--panel)' }}>
                <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginBottom: 6 }}>
                  <b style={{ fontSize: 14, color: '#f59e0b' }}>{t('3. Chuyên gia Phản biện', '3. Rigorous Peer Reviewer (Critic)')}</b>
                  <span style={{ fontSize: 10.5, padding: '2px 6px', borderRadius: 4, background: 'rgba(245, 158, 11, 0.1)', color: '#f59e0b', fontWeight: 700 }}>Reviewer</span>
                </div>
                <p style={{ margin: 0, fontSize: 12.5, lineHeight: 1.55, color: 'var(--fg)' }}>
                  {t(
                    'Đóng vai trò Reviewer khó tính chuẩn NeurIPS/ICLR/Nature, tìm lỗ hổng logic, nghi vấn dữ liệu thiếu đối chứng, thử thách giả thuyết và chấm điểm R1–R3.',
                    'Emulates a top-tier peer reviewer (NeurIPS/Nature), identifies logical flaws, flags ungrounded claims, and delivers calibrated R1–R3 critiques.'
                  )}
                </p>
              </div>

              {/* Engineer */}
              <div className="panelbox" style={{ padding: 16, borderRadius: 10, border: '1px solid var(--line)', background: 'var(--panel)' }}>
                <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginBottom: 6 }}>
                  <b style={{ fontSize: 14, color: '#10b981' }}>{t('4. Kỹ sư Thực nghiệm', '4. Experiment Engineer (Native Code)')}</b>
                  <span style={{ fontSize: 10.5, padding: '2px 6px', borderRadius: 4, background: 'rgba(16, 185, 129, 0.1)', color: '#10b981', fontWeight: 700 }}>Native Code</span>
                </div>
                <p style={{ margin: 0, fontSize: 12.5, lineHeight: 1.55, color: 'var(--fg)' }}>
                  {t(
                    'Viết mã nguồn Python, chạy mô phỏng tính toán trong môi trường thực thi Native Code, kiểm tra tính tái lập và giám sát tài nguyên phần cứng GPU/CPU.',
                    'Writes clean Python code, runs simulations in Native Code Runtime, verifies computational reproducibility, and monitors GPU/CPU hardware.'
                  )}
                </p>
              </div>

              {/* Writer */}
              <div className="panelbox" style={{ padding: 16, borderRadius: 10, border: '1px solid var(--line)', background: 'var(--panel)' }}>
                <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginBottom: 6 }}>
                  <b style={{ fontSize: 14, color: '#8b5cf6' }}>{t('5. Biên tập viên Bản thảo', '5. Manuscript Scribe (Writer)')}</b>
                  <span style={{ fontSize: 10.5, padding: '2px 6px', borderRadius: 4, background: 'rgba(139, 92, 246, 0.1)', color: '#8b5cf6', fontWeight: 700 }}>LaTeX</span>
                </div>
                <p style={{ margin: 0, fontSize: 12.5, lineHeight: 1.55, color: 'var(--fg)' }}>
                  {t(
                    'Soạn thảo bài báo chuẩn cấu trúc IMRAD bằng LaTeX, khai triển công thức KaTeX, thiết kế bảng dữ liệu khoa học và gắn mã trích dẫn BibTeX chuẩn xác.',
                    'Drafts manuscripts adhering to standard IMRAD structure in LaTeX, formats KaTeX mathematical equations, and generates compliant BibTeX citations.'
                  )}
                </p>
              </div>

              {/* Denoising Worker */}
              <div className="panelbox" style={{ padding: 16, borderRadius: 10, border: '1px solid var(--line)', background: 'var(--panel)' }}>
                <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginBottom: 6 }}>
                  <b style={{ fontSize: 14, color: '#ec4899' }}>{t('6. Kiểm định Bằng chứng', '6. Evidence Verifier (Denoising)')}</b>
                  <span style={{ fontSize: 10.5, padding: '2px 6px', borderRadius: 4, background: 'rgba(236, 72, 153, 0.1)', color: '#ec4899', fontWeight: 700 }}>Audit</span>
                </div>
                <p style={{ margin: 0, fontSize: 12.5, lineHeight: 1.55, color: 'var(--fg)' }}>
                  {t(
                    'Lọc bỏ ảo giác AI, đối chiếu mọi khẳng định khoa học với SHA-256 dữ liệu thực nghiệm và các bài báo gốc trong thư viện.',
                    'Filters out hallucinated statements, grounds scientific claims in raw experimental data, and cross-checks citations against original library PDFs.'
                  )}
                </p>
              </div>
            </div>

            {/* 3D Lab Interactive Tips */}
            <div className="panelbox" style={{ padding: 18, borderRadius: 12, border: '1px solid var(--line)', background: 'var(--panel)' }}>
              <b style={{ fontSize: 14.5 }}>{t('Mẹo Tương tác trong Phòng Lab 3D:', '3D Lab Interaction Tips:')}</b>
              <ul style={{ margin: '8px 0 0', paddingLeft: 20, fontSize: 13, lineHeight: 1.7, color: 'var(--fg)' }}>
                <li>
                  <b>{t('Click vào nhân vật Agent:', 'Click an Agent character:')}</b>{' '}
                  {t('Mở khung chat trực tiếp với Agent đó để giao nhiệm vụ hoặc hỏi tình trạng công việc.', 'Open direct chat with that agent to assign workstreams or query status.')}
                </li>
                <li>
                  <b>{t('Click vào Bàn hội nghị tròn:', 'Click the Conference Table:')}</b>{' '}
                  {t('Khởi chạy Hội đồng Bình duyệt R1–R3 toàn diện.', 'Launches the R1–R3 Academic Peer Review Roundtable.')}
                </li>
                <li>
                  <b>{t('Click vào Giá sách Thư viện:', 'Click the Library Bookshelf:')}</b>{' '}
                  {t('Mở Thư viện tài liệu PDF và công cụ tìm kiếm bài báo Google Scholar.', 'Opens the PDF library and Google Scholar paper search.')}
                </li>
                <li>
                  <b>{t('Click vào Cụm máy chủ HPC:', 'Click the HPC Server Cluster:')}</b>{' '}
                  {t('Mở trung tâm tính toán thực nghiệm Native Code Runtime.', 'Opens the Native Code parallel computing center.')}
                </li>
                <li>
                  <b>{t('Click vào Bảng Đề cương trên tường:', 'Click the Wall Outline Board:')}</b>{' '}
                  {t('Mở bảng biên tập Đề cương nghiên cứu 5 cấp độ.', 'Opens the 5-level interactive research outline editor.')}
                </li>
                <li>
                  <b>{t('Chuyển đổi góc nhìn & Ánh sáng:', 'Camera views & Lighting:')}</b>{' '}
                  {t('Dùng các nút trên thanh công cụ Lab 3D để đổi camera (Toàn cảnh / Cận cảnh) và chế độ ánh sáng (Ban ngày, Studio, Hoàng hôn, Ban đêm).', 'Use top toolbar controls to switch cameras (overview, workspace close-up) and ambient lighting presets.')}
                </li>
              </ul>
              <div style={{ marginTop: 14 }}>
                <button className="btn sm accent" onClick={() => open3DOffice()}>
                  <Bot size={13} style={{ marginRight: 5 }} />
                  {t('Mở Phòng Lab 3D Ngay', 'Launch 3D Lab Now')}
                </button>
              </div>
            </div>
          </div>
        )}

        {/* TAB 3: COMMANDS */}
        {activeTab === 'commands' && (
          <div style={{ display: 'flex', flexDirection: 'column', gap: 24 }}>
            <div>
              <h3 style={{ margin: 0, fontSize: 18, fontWeight: 700, display: 'flex', alignItems: 'center', gap: 8 }}>
                <Terminal size={20} color="var(--accent)" />
                <span>{t('Khung Chat & Hệ thống Lệnh tắt Chuyên dụng gạch chéo', 'Chatbox & Slash Commands (/)')}</span>
              </h3>
              <p style={{ margin: '6px 0 0', fontSize: 13, color: 'var(--muted)', lineHeight: 1.6 }}>
                {t(
                  'Khung trò chuyện tích hợp bộ lệnh tắt chuyên sâu giúp bạn kích hoạt nhanh các quy trình nghiên cứu học thuật phức tạp mà không cần gõ câu lệnh dài dòng.',
                  'The chat composer includes specialized academic slash commands to trigger complex research workflows instantly.'
                )}
              </p>
            </div>

            <div style={{ display: 'flex', flexDirection: 'column', gap: 10 }}>
              {[
                {
                  cmd: '/lit [topic]',
                  title: t('Quét & Tổng quan Tài liệu', 'Literature Survey'),
                  desc: t('Tìm kiếm, phân tích và tổng hợp hàng chục bài báo liên quan từ Google Scholar, arXiv và thư viện nội bộ.', 'Surveys, analyzes, and synthesizes relevant papers from Google Scholar, arXiv, and library PDFs.'),
                },
                {
                  cmd: '/hypothesis [problem]',
                  title: t('Phát triển Giả thuyết', 'Hypothesis Generation'),
                  desc: t('Đề xuất 3 giả thuyết nghiên cứu khả thi kèm cơ chế lý giải và phương án thực nghiệm kiểm chứng.', 'Formulates 3 testable research hypotheses with theoretical justification and validation plans.'),
                },
                {
                  cmd: '/experiment [idea]',
                  title: t('Thiết kế Thí nghiệm', 'Experiment Protocol'),
                  desc: t('Thiết lập giao thức thực nghiệm đối chứng, xác định biến số và chỉ số đo lường định lượng.', 'Designs controlled experimental protocols, variables, baselines, and quantitative metrics.'),
                },
                {
                  cmd: '/review [draft]',
                  title: t('Hội đồng Phản biện R1–R3', 'Rigorous Peer Review'),
                  desc: t('Khởi động quy trình phản biện đa tác nhân theo tiêu chuẩn hội nghị Tier-1, chỉ ra các lỗ hổng và đề xuất sửa đổi.', 'Launches multi-agent peer review following Tier-1 conference rubrics with actionable critique.'),
                },
                {
                  cmd: '/math [formula]',
                  title: t('Khai triển Toán học', 'Mathematical Proof'),
                  desc: t('Khai triển chứng minh định lý, kiểm tra điều kiện hội tụ và biên dịch công thức chuẩn KaTeX.', 'Derives mathematical proofs, checks convergence conditions, and renders formatted KaTeX.'),
                },
                {
                  cmd: '/latex [content]',
                  title: t('Soạn thảo LaTeX Chuẩn', 'LaTeX Manuscript'),
                  desc: t('Chuyển đổi văn bản thành mã nguồn LaTeX theo cấu trúc IMRAD chuẩn của IEEE, ACM hoặc Nature.', 'Formats scientific prose into publication-ready IEEE/ACM/Nature LaTeX manuscripts.'),
                },
                {
                  cmd: '/claims',
                  title: t('Kiểm định Luận điểm', 'Claim Verification'),
                  desc: t('Trích xuất toàn bộ luận điểm khoa học và đối soát mức độ trung thực với bằng chứng thực nghiệm SHA-256.', 'Extracts empirical claims and cross-verifies factual grounding against SHA-256 evidence data.'),
                },
                {
                  cmd: '/outline',
                  title: t('Điều phối Đề cương', 'Outline Manager'),
                  desc: t('Mở bảng điều phối đề cương 5 cấp độ để xem và chỉnh sửa định hướng học thuật.', 'Opens the 5-level outline drawer to review and adjust research direction.'),
                },
                {
                  cmd: '/figures',
                  title: t('Xưởng Đồ họa Khoa học', 'Figure Studio'),
                  desc: t('Mở Figure Studio để thiết kế biểu đồ vector, sơ đồ kiến trúc và đồ thị trực quan cho bài báo.', 'Opens Figure Studio to design vector charts, model architecture diagrams, and scientific figures.'),
                },
                {
                  cmd: '/code',
                  title: t('Môi trường Tính toán', 'Native Code Runtime'),
                  desc: t('Mở nhân tính toán Native Experiment Workspace để chạy mô phỏng Python và kiểm tra mã nguồn.', 'Opens the Native Code parallel runtime to execute Python scripts, train models, and test code.'),
                },
                {
                  cmd: '/status',
                  title: t('Trạng thái Hệ thống', 'System Health & GPU'),
                  desc: t('Kiểm tra mức sử dụng VRAM, tải GPU, bộ nhớ CSDL và danh sách các tác vụ đang chạy ngầm.', 'Inspects VRAM allocation, GPU load, database storage, and active background missions.'),
                },
                {
                  cmd: '/dashboard',
                  title: t('Bảng điều khiển Tổng thể', 'System Dashboard'),
                  desc: t('Mở toàn cảnh tiến độ nghiên cứu, thống kê số bài báo đã đọc, số thí nghiệm đã hoàn thành.', 'Opens holistic progress dashboard with paper metrics, experiment logs, and review summaries.'),
                },
                {
                  cmd: '/learn',
                  title: t('Ghi nhớ Quy tắc Mới', 'Learn Rule / Skill'),
                  desc: t('Lưu trữ quy tắc hoặc chỉ dẫn đặc biệt để toàn bộ hội đồng AI áp dụng cho các phiên sau.', 'Persists custom behavioral instructions or rules across all multi-agent workflows.'),
                },
                {
                  cmd: '/goal',
                  title: t('Nhiệm vụ Xuyên đêm', 'Autonomous Overnight Goal'),
                  desc: t('Kích hoạt chế độ nghiên cứu tự trị chuyên sâu, chạy liên tục cho đến khi đạt được mục tiêu lớn.', 'Enables rigorous long-running autonomous research execution until the goal is fully achieved.'),
                },
              ].map((item) => (
                <div
                  key={item.cmd}
                  style={{
                    display: 'flex',
                    alignItems: 'flex-start',
                    justifyContent: 'space-between',
                    padding: '12px 16px',
                    borderRadius: 8,
                    background: 'var(--panel)',
                    border: '1px solid var(--line)',
                    gap: 16,
                  }}
                >
                  <div style={{ minWidth: 160 }}>
                    <code style={{ fontSize: 13, fontWeight: 700, color: 'var(--accent)', fontFamily: 'var(--mono)' }}>
                      {item.cmd}
                    </code>
                    <div style={{ fontSize: 11.5, color: 'var(--muted)', marginTop: 2, fontWeight: 600 }}>
                      {item.title}
                    </div>
                  </div>
                  <div style={{ fontSize: 12.5, color: 'var(--fg)', flex: 1, lineHeight: 1.5 }}>
                    {item.desc}
                  </div>
                </div>
              ))}
            </div>

            <div className="panelbox" style={{ padding: 16, borderRadius: 10, border: '1px solid var(--line)', background: 'var(--bg-2)' }}>
              <b style={{ fontSize: 13.5 }}>💡 {t('Mẹo dùng phím Tab tự động điền lệnh:', 'Tab Autocomplete Tip:')}</b>
              <p style={{ margin: '6px 0 0', fontSize: 12.5, lineHeight: 1.6, color: 'var(--fg)' }}>
                {t(
                  'Khi gõ ký tự "/" trong khung chat, danh sách gợi ý sẽ xuất hiện tức thì. Dùng phím mũi tên [↑/↓] để di chuyển và bấm [Tab] hoặc [Enter] để tự động điền lệnh nhanh chóng mà không cần nhớ cú pháp.',
                  'Typing "/" in the chat input instantly displays the command popover. Use arrow keys [↑/↓] to navigate and press [Tab] or [Enter] to autocomplete without memorizing syntax.'
                )}
              </p>
            </div>
          </div>
        )}

        {/* TAB 4: LIBRARY */}
        {activeTab === 'library' && (
          <div style={{ display: 'flex', flexDirection: 'column', gap: 24 }}>
            <div>
              <h3 style={{ margin: 0, fontSize: 18, fontWeight: 700, display: 'flex', alignItems: 'center', gap: 8 }}>
                <BookOpen size={20} color="var(--accent)" />
                <span>{t('Thư viện Bài báo Khoa học & Trích dẫn Google Scholar', 'Academic PDF Library & Citations')}</span>
              </h3>
              <p style={{ margin: '6px 0 0', fontSize: 13, color: 'var(--muted)', lineHeight: 1.6 }}>
                {t(
                  'Quản lý hàng trăm bài báo khoa học chất lượng cao, tích hợp tìm kiếm Google Scholar, phân loại tạp chí hàng đầu và xuất trích dẫn BibTeX chuẩn xác.',
                  'Manage high-impact research papers, integrate Google Scholar discovery, venue tier ranking, and instant BibTeX citation export.'
                )}
              </p>
            </div>

            <div className="panelbox" style={{ padding: 20, borderRadius: 12, border: '1px solid var(--line)', background: 'var(--panel)' }}>
              <b style={{ fontSize: 15 }}>{t('Quản lý Siêu dữ liệu & Trích dẫn Google Scholar:', 'Smart Citation & Google Scholar Integration:')}</b>
              <p style={{ margin: '8px 0 14px', fontSize: 13, lineHeight: 1.65, color: 'var(--fg)' }}>
                {t(
                  'Mỗi bài báo trong Thư viện đều được trích xuất tự động: Tiêu đề chuẩn, Danh sách tác giả, Năm xuất bản, Tóm tắt và Xếp hạng tạp chí. Đặc biệt, tính năng trích nguồn tham khảo với thông tin lấy từ Google Scholar giúp bạn có được số lượng trích dẫn, liên kết bài viết liên quan và mã BibTeX hoàn chỉnh.',
                  'Every paper in the library is enriched with normalized title, author list, publication year, abstract, and venue tier. Google Scholar citation lookup provides citation counts, related papers, and formatted BibTeX.'
                )}
              </p>

              <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(210px, 1fr))', gap: 12, marginTop: 12 }}>
                <div style={{ padding: 12, borderRadius: 8, background: 'var(--bg-2)', border: '1px solid var(--line)' }}>
                  <b style={{ color: '#10b981', fontSize: 13 }}>{t('Core A* / Tier 1 Venues', 'Core A* / Top-Tier Venues')}</b>
                  <div style={{ fontSize: 12, color: 'var(--fg)', marginTop: 4, lineHeight: 1.5 }}>
                    {t(
                      'Các hội nghị và tạp chí đỉnh cao như NeurIPS, ICML, CVPR, Nature, Science, ACM CHI.',
                      'Premier conferences and journals including NeurIPS, ICML, CVPR, Nature, Science, ACM CHI.'
                    )}
                  </div>
                </div>
                <div style={{ padding: 12, borderRadius: 8, background: 'var(--bg-2)', border: '1px solid var(--line)' }}>
                  <b style={{ color: '#0ea5e9', fontSize: 13 }}>{t('Tạp chí Q1 / Core A', 'Q1 / Core A Journals')}</b>
                  <div style={{ fontSize: 12, color: 'var(--fg)', marginTop: 4, lineHeight: 1.5 }}>
                    {t(
                      'Tạp chí uy tín thuộc nhóm 25% dẫn đầu ngành với chỉ số trích dẫn cao.',
                      'Top 25% prestigious academic publications with high impact factors.'
                    )}
                  </div>
                </div>
                <div style={{ padding: 12, borderRadius: 8, background: 'var(--bg-2)', border: '1px solid var(--line)' }}>
                  <b style={{ color: '#f59e0b', fontSize: 13 }}>{t('Xuất Trích dẫn 1-Click', '1-Click Citation Export')}</b>
                  <div style={{ fontSize: 12, color: 'var(--fg)', marginTop: 4, lineHeight: 1.5 }}>
                    {t(
                      'Sao chép mục trích dẫn chuẩn BibTeX, APA, IEEE để dán trực tiếp vào file .bib trong LaTeX.',
                      'Copy standard BibTeX, APA, IEEE citations to paste directly into your LaTeX .bib file.'
                    )}
                  </div>
                </div>
                <div style={{ padding: 12, borderRadius: 8, background: 'var(--bg-2)', border: '1px solid var(--line)' }}>
                  <b style={{ color: '#8b5cf6', fontSize: 13 }}>{t('Xem PDF Nhúng Trực tiếp', 'Embedded In-Browser Viewer')}</b>
                  <div style={{ fontSize: 12, color: 'var(--fg)', marginTop: 4, lineHeight: 1.5 }}>
                    {t(
                      'Đọc bài báo ngay trong giao diện web, hỗ trợ phóng to toàn màn hình và xem mục lục.',
                      'Read PDF papers directly in-app with full-screen mode and outline navigation.'
                    )}
                  </div>
                </div>
              </div>

              <div style={{ marginTop: 16 }}>
                <button className="btn sm accent" onClick={() => openDrawer('library')}>
                  <BookOpen size={13} style={{ marginRight: 5 }} />
                  {t('Vào Thư viện Bài báo Ngay', 'Launch Paper Library')}
                </button>
              </div>
            </div>
          </div>
        )}

        {/* TAB 5: SHORTCUTS & FAQ */}
        {activeTab === 'shortcuts' && (
          <div style={{ display: 'flex', flexDirection: 'column', gap: 24 }}>
            <div>
              <h3 style={{ margin: 0, fontSize: 18, fontWeight: 700, display: 'flex', alignItems: 'center', gap: 8 }}>
                <Keyboard size={20} color="var(--accent)" />
                <span>{t('Bảng Phím tắt, Bảo mật Cục bộ & Câu hỏi Thường gặp', 'Keybindings, Local Security & Troubleshooting FAQ')}</span>
              </h3>
              <p style={{ margin: '6px 0 0', fontSize: 13, color: 'var(--muted)', lineHeight: 1.6 }}>
                {t(
                  'Tổng hợp các thao tác phím tắt nhanh và câu trả lời chi tiết cho những câu hỏi thường gặp nhất khi sử dụng PhD Research Lab.',
                  'Comprehensive shortcuts reference and in-depth answers to frequently asked questions.'
                )}
              </p>
            </div>

            {/* Keybindings Table */}
            <div className="panelbox" style={{ padding: 18, borderRadius: 12, border: '1px solid var(--line)', background: 'var(--panel)' }}>
              <b style={{ fontSize: 14.5 }}>{t('Bảng Phím tắt Nhanh:', 'Keyboard Shortcuts:')}</b>
              <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(280px, 1fr))', gap: 10, marginTop: 12 }}>
                <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', padding: '8px 12px', background: 'var(--bg-2)', borderRadius: 6 }}>
                  <span style={{ fontSize: 12.5 }}>{t('Gửi tin nhắn trong Chat', 'Send message in chat')}</span>
                  <kbd style={{ padding: '2px 7px', background: 'var(--panel)', border: '1px solid var(--line)', borderRadius: 4, fontFamily: 'var(--mono)', fontSize: 11, fontWeight: 700 }}>Ctrl + Enter</kbd>
                </div>
                <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', padding: '8px 12px', background: 'var(--bg-2)', borderRadius: 6 }}>
                  <span style={{ fontSize: 12.5 }}>{t('Tự động điền lệnh tắt', 'Autocomplete slash command')}</span>
                  <kbd style={{ padding: '2px 7px', background: 'var(--panel)', border: '1px solid var(--line)', borderRadius: 4, fontFamily: 'var(--mono)', fontSize: 11, fontWeight: 700 }}>/ + Tab</kbd>
                </div>
                <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', padding: '8px 12px', background: 'var(--bg-2)', borderRadius: 6 }}>
                  <span style={{ fontSize: 12.5 }}>{t('Thu nhỏ hoặc Mở rộng Sidebar', 'Collapse/Expand Sidebar')}</span>
                  <kbd style={{ padding: '2px 7px', background: 'var(--panel)', border: '1px solid var(--line)', borderRadius: 4, fontFamily: 'var(--mono)', fontSize: 11, fontWeight: 700 }}>{t('Nhấp đúp thanh phân cách', 'Double-click separator')}</kbd>
                </div>
                <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', padding: '8px 12px', background: 'var(--bg-2)', borderRadius: 6 }}>
                  <span style={{ fontSize: 12.5 }}>{t('Chuyển đổi Ngôn ngữ', 'Switch Language (VI / EN)')}</span>
                  <kbd style={{ padding: '2px 7px', background: 'var(--panel)', border: '1px solid var(--line)', borderRadius: 4, fontFamily: 'var(--mono)', fontSize: 11, fontWeight: 700 }}>{t('Nút VI/EN trên Header', 'VI/EN button in Header')}</kbd>
                </div>
                <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', padding: '8px 12px', background: 'var(--bg-2)', borderRadius: 6 }}>
                  <span style={{ fontSize: 12.5 }}>{t('Chỉnh tỉ lệ hiển thị', 'Adjust UI Zoom Scale')}</span>
                  <kbd style={{ padding: '2px 7px', background: 'var(--panel)', border: '1px solid var(--line)', borderRadius: 4, fontFamily: 'var(--mono)', fontSize: 11, fontWeight: 700 }}>{t('Nút Zoom trên Header', 'Zoom button in Header')}</kbd>
                </div>
                <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', padding: '8px 12px', background: 'var(--bg-2)', borderRadius: 6 }}>
                  <span style={{ fontSize: 12.5 }}>{t('Mở menu Cài đặt duy nhất', 'Open unified settings')}</span>
                  <kbd style={{ padding: '2px 7px', background: 'var(--panel)', border: '1px solid var(--line)', borderRadius: 4, fontFamily: 'var(--mono)', fontSize: 11, fontWeight: 700 }}>{t('Góc dưới bên trái màn hình', 'Bottom-left corner icon')}</kbd>
                </div>
              </div>
            </div>

            {/* In-Depth FAQs */}
            <div style={{ display: 'flex', flexDirection: 'column', gap: 12 }}>
              <div className="panelbox" style={{ padding: 16, borderRadius: 10, border: '1px solid var(--line)', background: 'var(--panel)' }}>
                <b style={{ fontSize: 13.5, color: 'var(--accent)' }}>
                  {t('Hỏi: Dữ liệu nghiên cứu của tôi được lưu trữ ở đâu? Có an toàn không?', 'Q: Where is my research data stored? Is it secure?')}
                </b>
                <p style={{ margin: '6px 0 0', fontSize: 12.5, lineHeight: 1.6, color: 'var(--fg)' }}>
                  {t(
                    'Đáp: PhD Research Lab tuân thủ nghiêm ngặt nguyên tắc bảo mật cục bộ. Toàn bộ cơ sở dữ liệu SQLite (lab.db), các bài báo PDF, vector embeddings và lịch sử chat đều được lưu trữ trực tiếp trong thư mục dự án trên ổ đĩa máy tính của bạn. Khi sử dụng mô hình AI cục bộ (như LM Studio hay Ollama), dữ liệu hoàn toàn không rời khỏi máy tính và không kết nối Internet.',
                    'Answer: PhD Research Lab follows a strict Local-First model. All SQLite databases, PDFs, vector embeddings, and session histories reside directly on your local computer storage (data_dir). When using local models via LM Studio (like Phi-4), no data ever leaves your device.'
                  )}
                </p>
              </div>

              <div className="panelbox" style={{ padding: 16, borderRadius: 10, border: '1px solid var(--line)', background: 'var(--panel)' }}>
                <b style={{ fontSize: 13.5, color: 'var(--accent)' }}>
                  {t('Hỏi: Máy tính của tôi chỉ có 1 GPU, làm sao để chạy cả mô hình Local và code thực nghiệm Python?', 'Q: How to run both a Local LLM and experiment code on a single GPU?')}
                </b>
                <p style={{ margin: '6px 0 0', fontSize: 12.5, lineHeight: 1.6, color: 'var(--fg)' }}>
                  {t(
                    'Đáp: Bạn chỉ cần vào mục Cài đặt (ở góc dưới bên trái màn hình) → Thí nghiệm & Phần cứng → Bật tùy chọn "Tự động giải phóng mô hình cục bộ đang rảnh khỏi VRAM khi cần GPU chạy thí nghiệm". Hệ thống có cơ chế ResourceGuard thông minh sẽ tự động tạm dừng mô hình ngôn ngữ khi phiên Native Code cần tài nguyên GPU, ngăn chặn hoàn toàn lỗi tràn bộ nhớ VRAM.',
                    'Answer: Navigate to Settings (bottom-left corner) → Experiments & Hardware → Enable "Auto-offload idle local models from VRAM during compute experiments". ResourceGuard automatically pauses local LLM memory when Native Code requires GPU allocations.'
                  )}
                </p>
              </div>

              <div className="panelbox" style={{ padding: 16, borderRadius: 10, border: '1px solid var(--line)', background: 'var(--panel)' }}>
                <b style={{ fontSize: 13.5, color: 'var(--accent)' }}>
                  {t('Hỏi: Làm sao để đổi tên hiển thị và thông tin của các Agent 3D theo ý thích?', 'Q: How do I customize names and personal profiles of 3D agents?')}
                </b>
                <p style={{ margin: '6px 0 0', fontSize: 12.5, lineHeight: 1.6, color: 'var(--fg)' }}>
                  {t(
                    'Đáp: Trong màn hình Phòng Lab 3D hoặc danh sách Hội đồng tác nhân, bạn chỉ cần bấm vào nút biểu tượng "Hồ sơ cá nhân" của nhân vật Agent bạn muốn sửa. Một bảng chỉnh sửa sẽ mở ra cho phép bạn nhập tên riêng, chức danh học thuật, màu đại diện và lời chào đón. Sau khi bấm Lưu, Agent sẽ hiển thị tên mới trên toàn bộ giao diện và các bài phản biện.',
                    'Answer: In the 3D Lab or Agent Status list, click the "Personal Profile" icon button on any agent. A modal will open allowing you to input a custom name, title, accent color, and greeting. Once saved, the custom name is reflected across the entire workspace.'
                  )}
                </p>
              </div>

              <div className="panelbox" style={{ padding: 16, borderRadius: 10, border: '1px solid var(--line)', background: 'var(--panel)' }}>
                <b style={{ fontSize: 13.5, color: 'var(--accent)' }}>
                  {t('Hỏi: Làm thế nào để sao lưu hoặc chuyển toàn bộ dự án nghiên cứu sang máy tính khác?', 'Q: How do I backup or transfer a research project to another computer?')}
                </b>
                <p style={{ margin: '6px 0 0', fontSize: 12.5, lineHeight: 1.6, color: 'var(--fg)' }}>
                  {t(
                    'Đáp: Vì toàn bộ dự án nằm trọn vẹn trong một thư mục cục bộ (gồm cả CSDL lab.db và các tệp đính kèm), bạn chỉ cần sao chép thư mục dự án đó qua ổ cứng ngoài hoặc nén file zip gửi sang máy mới. Trên máy mới, mở PhD Research Lab, vào mục "Không gian Dự án" → bấm "Mở dự án" → chọn thư mục đó. Hệ thống sẽ tự động phục hồi mọi phiên chat, tài liệu PDF và tiến độ thí nghiệm nguyên vẹn 100%.',
                    'Answer: Since your research project is completely self-contained in a local directory, simply copy the directory or zip archive to the target computer. In PhD Lab, open Workspaces → "Open Project" → select that folder. All sessions, PDFs, and progress will restore with 100% fidelity.'
                  )}
                </p>
              </div>
            </div>
          </div>
        )}
      </div>
    </div>
  );
};
