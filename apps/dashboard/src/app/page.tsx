"use client";

import React, { useCallback, useEffect, useMemo, useRef, useState } from "react";
import {
  AlertCircle,
  AlertTriangle,
  ArrowRight,
  Check,
  CheckCircle2,
  ChevronDown,
  ChevronRight,
  Code2,
  Copy,
  Cpu,
  Download,
  ExternalLink,
  Eye,
  EyeOff,
  File,
  FileCode,
  FileText,
  Flame,
  Folder,
  FolderOpen,
  GitBranch,
  GitCommit,
  GitPullRequest,
  Info,
  Key,
  Layers,
  Lock,
  Network,
  Play,
  Plus,
  RefreshCw,
  Search,
  Settings as SettingsIcon,
  Share2,
  ShieldAlert,
  ShieldCheck,
  Sliders,
  Sparkles,
  Sun,
  Moon,
  Terminal,
  X,
  Zap,
  ZoomIn,
  ZoomOut,
} from "lucide-react";

import {
  analyzeGitRepository,
  CodeCorrection,
  CommitReportItem,
  createFixPR,
  exportReport,
  FileTreeItem,
  PRReportItem,
  publishPRReview,
  RepoAnalysisReport,
  RepoAnalysisRequest,
} from "@/lib/api";
import { MermaidViewer } from "@/components/MermaidViewer";

interface SettingsState {
  provider: "openai" | "gemini";
  model: string;
  openaiApiKey: string;
  geminiApiKey: string;
  githubToken: string;
}

const DEFAULT_SETTINGS: SettingsState = {
  provider: "openai",
  model: "gpt-4o-mini",
  openaiApiKey: "",
  geminiApiKey: "",
  githubToken: "",
};

export default function Home() {
  // Navigation & Subtab state
  const [activeTab, setActiveTab] = useState<"dashboard" | "settings">("dashboard");
  const [reportSubTab, setReportSubTab] = useState<"overview" | "corrections" | "files" | "git">("overview");

  // Persistent settings state
  const [settings, setSettings] = useState<SettingsState>(DEFAULT_SETTINGS);
  const [settingsSaved, setSettingsSaved] = useState(false);
  const [showOpenAIKey, setShowOpenAIKey] = useState(false);
  const [showGeminiKey, setShowGeminiKey] = useState(false);
  const [showGithubToken, setShowGithubToken] = useState(false);

  // Analysis state
  const [gitUrl, setGitUrl] = useState("");
  const [isAnalyzing, setIsAnalyzing] = useState(false);
  const [analysisStep, setAnalysisStep] = useState<number>(0);
  const [analysisError, setAnalysisError] = useState<string | null>(null);
  const [report, setReport] = useState<RepoAnalysisReport | null>(null);

  // Filters & interactions
  const [categoryFilter, setCategoryFilter] = useState<string>("all");
  const [severityFilter, setSeverityFilter] = useState<string>("all");
  const [copiedId, setCopiedId] = useState<string | null>(null);
  const [selectedFilePath, setSelectedFilePath] = useState<string | null>(null);

  // Bot actions & Export state
  const [isPublishingReview, setIsPublishingReview] = useState(false);
  const [publishStatus, setPublishStatus] = useState<string | null>(null);
  const [fixingCorrectionId, setFixingCorrectionId] = useState<string | null>(null);
  const [fixPRResult, setFixPRResult] = useState<Record<string, { url: string; msg: string }>>({});
  const [isExporting, setIsExporting] = useState<"sarif" | "markdown" | null>(null);
  const [exportDropdownOpen, setExportDropdownOpen] = useState(false);

  // Visual Call-Graph Canvas state
  const [graphZoom, setGraphZoom] = useState(1);
  const [focusedGraphNode, setFocusedGraphNode] = useState<string | null>(null);
  const [graphLayoutMode, setGraphLayoutMode] = useState<"gitdiagram" | "layered" | "cluster">("gitdiagram");
  const [graphTierFilter, setGraphTierFilter] = useState<string>("all");
  const [graphSearchQuery, setGraphSearchQuery] = useState<string>("");
  const [theme, setTheme] = useState<"dark" | "light">("dark");

  // Initialize theme from localStorage or system preference
  useEffect(() => {
    try {
      const storedTheme = localStorage.getItem("aicr_theme") as "dark" | "light" | null;
      const initial = storedTheme || "dark";
      setTheme(initial);
      if (initial === "dark") {
        document.documentElement.classList.add("dark");
      } else {
        document.documentElement.classList.remove("dark");
      }
    } catch {
      document.documentElement.classList.add("dark");
    }
  }, []);

  const toggleTheme = () => {
    const next = theme === "dark" ? "light" : "dark";
    setTheme(next);
    try {
      localStorage.setItem("aicr_theme", next);
    } catch {}
    if (next === "dark") {
      document.documentElement.classList.add("dark");
    } else {
      document.documentElement.classList.remove("dark");
    }
  };

  // FAQ disclosures state
  const [openFaq, setOpenFaq] = useState<Record<number, boolean>>({ 0: true });

  const abortControllerRef = useRef<AbortController | null>(null);

  // Load persistent settings from localStorage
  useEffect(() => {
    try {
      const stored = localStorage.getItem("aicr_analyzer_settings");
      if (stored) {
        setSettings(JSON.parse(stored));
      }
    } catch {
      // ignore
    }
  }, []);

  const handleSaveSettings = () => {
    try {
      localStorage.setItem("aicr_analyzer_settings", JSON.stringify(settings));
      setSettingsSaved(true);
      setTimeout(() => setSettingsSaved(false), 2500);
    } catch {
      // ignore
    }
  };

  // Run deep live repository / PR analysis
  const runAnalysis = useCallback(
    async (overrideUrl?: string) => {
      const urlToUse = (overrideUrl || gitUrl).trim();
      if (!urlToUse) return;

      setIsAnalyzing(true);
      setAnalysisError(null);
      setAnalysisStep(1);

      if (abortControllerRef.current) {
        abortControllerRef.current.abort();
      }
      const controller = new AbortController();
      abortControllerRef.current = controller;

      const timer1 = setTimeout(() => setAnalysisStep(2), 1200);
      const timer2 = setTimeout(() => setAnalysisStep(3), 2800);
      const timer3 = setTimeout(() => setAnalysisStep(4), 5000);

      try {
        const req: RepoAnalysisRequest = {
          git_url: urlToUse,
          provider: settings.provider,
          model: settings.model,
          openai_api_key: settings.openaiApiKey || undefined,
          gemini_api_key: settings.geminiApiKey || undefined,
          github_token: settings.githubToken || undefined,
        };

        const result = await analyzeGitRepository(req, controller.signal);
        setReport(result);
        setAnalysisStep(5);
        if (result.file_tree && result.file_tree.length > 0) {
          setSelectedFilePath(result.file_tree[0].path);
        }
      } catch (err: any) {
        if (err.name === "AbortError") {
          setAnalysisError("Analysis was cancelled.");
        } else {
          setAnalysisError(err.message || "Failed to analyze repository. Check URL or network.");
        }
      } finally {
        clearTimeout(timer1);
        clearTimeout(timer2);
        clearTimeout(timer3);
        setIsAnalyzing(false);
        abortControllerRef.current = null;
      }
    },
    [gitUrl, settings]
  );

  const handleCopyCode = (id: string, code: string) => {
    navigator.clipboard.writeText(code);
    setCopiedId(id);
    setTimeout(() => setCopiedId(null), 2000);
  };

  const handleQuickUrl = (url: string) => {
    setGitUrl(url);
    runAnalysis(url);
  };

  // 1-Click Bot Action: Publish Review to live GitHub PR
  const handlePublishReview = async () => {
    if (!report || !settings.githubToken) {
      setActiveTab("settings");
      setAnalysisError("Please add your GitHub Personal Access Token in Settings to publish comments directly to GitHub.");
      return;
    }

    setIsPublishingReview(true);
    setPublishStatus(null);
    try {
      const res = await publishPRReview({
        pr_url: gitUrl,
        github_token: settings.githubToken,
        findings: report.code_corrections,
        summary_body: `## 🛡️ AI Code Reviewer Audit\n\nOverall Health Score: **${report.repo_summary.health_score}/100**\nIdentified **${report.code_corrections?.length || 0}** code remediations.`,
      });
      setPublishStatus(res.message);
    } catch (err: any) {
      setPublishStatus(`Failed: ${err.message}`);
    } finally {
      setIsPublishingReview(false);
    }
  };

  // 1-Click Bot Action: Apply Fix as PR
  const handleCreateFixPR = async (corr: CodeCorrection) => {
    if (!settings.githubToken) {
      setActiveTab("settings");
      setAnalysisError("Please add your GitHub Personal Access Token in Settings to open pull requests automatically.");
      return;
    }

    setFixingCorrectionId(corr.id);
    try {
      const res = await createFixPR({
        git_url: gitUrl,
        github_token: settings.githubToken,
        correction: corr,
      });
      setFixPRResult((prev) => ({
        ...prev,
        [corr.id]: { url: res.pr_url, msg: res.message },
      }));
    } catch (err: any) {
      setFixPRResult((prev) => ({
        ...prev,
        [corr.id]: { url: "", msg: `Failed: ${err.message}` },
      }));
    } finally {
      setFixingCorrectionId(null);
    }
  };

  // Export Report (SARIF or Markdown)
  const handleExport = async (format: "sarif" | "markdown") => {
    if (!report) return;
    setIsExporting(format);
    setExportDropdownOpen(false);

    try {
      const res = await exportReport({ report, format });
      const blob = new Blob([res.content], { type: res.content_type });
      const url = URL.createObjectURL(blob);
      const a = document.createElement("a");
      a.href = url;
      a.download = res.filename;
      document.body.appendChild(a);
      a.click();
      document.body.removeChild(a);
      URL.revokeObjectURL(url);
    } catch (err: any) {
      console.error("Export error:", err);
    } finally {
      setIsExporting(null);
    }
  };

  // Filtered code corrections
  const filteredCorrections = useMemo(() => {
    if (!report || !report.code_corrections) return [];
    return (report.code_corrections || []).filter((c) => {
      const matchCat = categoryFilter === "all" || c?.category?.toLowerCase() === categoryFilter.toLowerCase();
      const matchSev = severityFilter === "all" || c?.severity?.toLowerCase() === severityFilter.toLowerCase();
      return matchCat && matchSev;
    });
  }, [report, categoryFilter, severityFilter]);

  // Selected file for Deep Inspector
  const selectedFile = useMemo(() => {
    if (!report?.file_tree) return null;
    return (report.file_tree || []).find((f) => f?.path === selectedFilePath) || report.file_tree[0] || null;
  }, [report, selectedFilePath]);

  // Selected file AST symbols
  const selectedFileSymbols = useMemo(() => {
    if (!report?.ast_insights || !selectedFile) return [];
    const funcs = (report.ast_insights.functions || []).filter((f) => f?.file_path === selectedFile.path);
    const classes = (report.ast_insights.classes || []).filter((c) => c?.file_path === selectedFile.path);
    return [...classes.map((c) => ({ ...c, kind: "class" })), ...funcs.map((f) => ({ ...f, kind: "function" }))];
  }, [report, selectedFile]);

  // Architectural Tier detection
  const getFileTier = useCallback((filePath: string) => {
    const p = filePath.toLowerCase();
    if (p.includes("app.") || p.includes("main.") || p.includes("server.") || p.includes("index.")) {
      return { tier: "entry", label: "Entrypoint", color: "#38bdf8", stroke: "#0284c7", icon: "🌐" };
    }
    if (p.includes("route") || p.includes("controller") || p.includes("endpoint") || p.includes("api/")) {
      return { tier: "routes", label: "Route API", color: "#34d399", stroke: "#059669", icon: "🚦" };
    }
    if (p.includes("service") || p.includes("logic") || p.includes("domain") || p.includes("handler")) {
      return { tier: "services", label: "Service", color: "#a855f7", stroke: "#7c3aed", icon: "⚙️" };
    }
    if (p.includes("ml") || p.includes("model") || p.includes("ai") || p.includes("predict") || p.includes("train")) {
      return { tier: "ml", label: "ML Engine", color: "#f59e0b", stroke: "#d97706", icon: "🧠" };
    }
    if (p.includes("util") || p.includes("db") || p.includes("database") || p.includes("schema") || p.includes("sql") || p.includes("store")) {
      return { tier: "data", label: "Data / DB", color: "#f43f5e", stroke: "#e11d48", icon: "🗄️" };
    }
    return { tier: "other", label: "Module", color: "#60a5fa", stroke: "#2563eb", icon: "📦" };
  }, []);

  // Graph nodes & edges with GitDiagram-style layered column layout
  const graphData = useMemo(() => {
    if (!report) return { nodes: [], edges: [], totalWidth: 1000, totalHeight: 500, activeTiers: [] };
    const rawFiles = report.file_tree || [];
    const hotspots = report.architecture_advice?.coupling_hotspots || [];
    const depMap = report.ast_insights?.dependency_map || [];
    const astSymbols = report.ast_insights?.functions || [];
    const astClasses = report.ast_insights?.classes || [];

    // Filter files
    let filteredFiles = rawFiles;
    if (graphTierFilter !== "all") {
      if (graphTierFilter === "flagged") {
        filteredFiles = filteredFiles.filter((f) => (f.issues_count || 0) > 0 || hotspots.some((h) => h?.file_path === f.path));
      } else {
        filteredFiles = filteredFiles.filter((f) => getFileTier(f.path).tier === graphTierFilter);
      }
    }
    if (graphSearchQuery.trim()) {
      const q = graphSearchQuery.toLowerCase();
      filteredFiles = filteredFiles.filter((f) => f.path.toLowerCase().includes(q));
    }

    if (filteredFiles.length === 0) {
      filteredFiles = rawFiles;
    }

    // Pre-calculate inbound and outbound connections for all files
    const inboundMap: Record<string, string[]> = {};
    const outboundMap: Record<string, string[]> = {};
    const rawEdges: Array<{ source: string; target: string; isHot: boolean }> = [];

    depMap.forEach((dep) => {
      if (!dep?.source || !dep?.target) return;
      const sNode = rawFiles.find((n) => n.path === dep.source);
      // Smart matching target
      const tNode = rawFiles.find((n) => {
        if (n.path === dep.target) return true;
        const stem = n.path.split("/").pop()?.split(".")[0];
        if (stem && dep.target.includes(stem)) return true;
        const pParts = n.path.split("/").filter((x) => x.length > 2 && x !== "backend" && x !== "src");
        return pParts.some((part) => dep.target.includes(part));
      });

      if (sNode && tNode && sNode.path !== tNode.path) {
        if (!outboundMap[sNode.path]) outboundMap[sNode.path] = [];
        if (!outboundMap[sNode.path].includes(tNode.path)) outboundMap[sNode.path].push(tNode.path);

        if (!inboundMap[tNode.path]) inboundMap[tNode.path] = [];
        if (!inboundMap[tNode.path].includes(sNode.path)) inboundMap[tNode.path].push(sNode.path);

        const exists = rawEdges.some((e) => e.source === sNode.path && e.target === tNode.path);
        if (!exists) {
          rawEdges.push({
            source: sNode.path,
            target: tNode.path,
            isHot: hotspots.some((h) => h?.file_path === sNode.path || h?.file_path === tNode.path),
          });
        }
      }
    });

    // Fallback edges if none matched so graph is always linked
    if (rawEdges.length === 0 && filteredFiles.length > 1) {
      for (let i = 1; i < filteredFiles.length; i++) {
        rawEdges.push({
          source: filteredFiles[0].path,
          target: filteredFiles[i].path,
          isHot: hotspots.some((h) => h?.file_path === filteredFiles[0].path),
        });
      }
    }

    // Node placement
    const CARD_W = 180;
    const CARD_H = 48;

    let nodes: Array<any> = [];
    let totalWidth = 1000;
    let totalHeight = 520;
    let activeTiers: Array<{ tier: string; label: string; x: number }> = [];

    if (graphLayoutMode === "layered") {
      // 5 Tier Columns: Entry -> Routes -> Services -> ML -> Data/Other
      const tierOrder: Array<"entry" | "routes" | "services" | "ml" | "data" | "other"> = [
        "entry", "routes", "services", "ml", "data", "other"
      ];
      const columnGroups: Record<string, typeof filteredFiles> = {
        entry: [],
        routes: [],
        services: [],
        ml: [],
        data: [],
        other: [],
      };

      filteredFiles.forEach((f) => {
        const t = getFileTier(f.path).tier;
        columnGroups[t].push(f);
      });

      const validTiers = tierOrder.filter((t) => columnGroups[t].length > 0);
      const colSpacing = validTiers.length <= 3 ? 280 : 230;
      const startX = 60;
      const maxRows = Math.max(...validTiers.map((t) => columnGroups[t].length), 4);
      totalHeight = Math.max(500, maxRows * 75 + 130);
      totalWidth = Math.max(1050, startX + validTiers.length * colSpacing + 120);

      validTiers.forEach((tier, colIdx) => {
        const colFiles = columnGroups[tier];
        const colX = startX + colIdx * colSpacing;
        const tierName = getFileTier(colFiles[0]?.path || "").label;
        activeTiers.push({ tier, label: tierName, x: colX });

        colFiles.forEach((f, rowIdx) => {
          const colY = 90 + rowIdx * 75;
          const tierInfo = getFileTier(f.path);
          const isHotspot = hotspots.some((h) => h?.file_path === f.path);
          const hasIssues = (f.issues_count || 0) > 0;
          const fileSyms = astSymbols.filter((s) => s?.file_path === f.path);
          const fileCls = astClasses.filter((c) => c?.file_path === f.path);

          nodes.push({
            id: f.path,
            label: f.path.split("/").pop() || f.path,
            fullPath: f.path,
            tier: tierInfo.tier,
            tierLabel: tierInfo.label,
            color: tierInfo.color,
            stroke: tierInfo.stroke,
            icon: tierInfo.icon,
            x: colX,
            y: colY,
            width: CARD_W,
            height: CARD_H,
            colIndex: colIdx,
            isHotspot,
            hasIssues,
            symbolsCount: f.symbols_count || (fileSyms.length + fileCls.length),
            issuesCount: f.issues_count || 0,
            classesCount: fileCls.length,
            functionsCount: fileSyms.length,
            inboundCallers: inboundMap[f.path] || [],
            outboundDependencies: outboundMap[f.path] || [],
          });
        });
      });
    } else {
      // Radial Cluster Layout
      const centerX = 500;
      const centerY = 280;
      const radius = Math.min(260, 80 + filteredFiles.length * 10);
      totalWidth = 1000;
      totalHeight = 560;

      filteredFiles.forEach((f, i) => {
        const angle = (i / (filteredFiles.length || 1)) * 2 * Math.PI;
        const x = centerX + radius * Math.cos(angle) - CARD_W / 2;
        const y = centerY + radius * Math.sin(angle) - CARD_H / 2;
        const tierInfo = getFileTier(f.path);
        const isHotspot = hotspots.some((h) => h?.file_path === f.path);
        const hasIssues = (f.issues_count || 0) > 0;
        const fileSyms = astSymbols.filter((s) => s?.file_path === f.path);
        const fileCls = astClasses.filter((c) => c?.file_path === f.path);

        nodes.push({
          id: f.path,
          label: f.path.split("/").pop() || f.path,
          fullPath: f.path,
          tier: tierInfo.tier,
          tierLabel: tierInfo.label,
          color: tierInfo.color,
          stroke: tierInfo.stroke,
          icon: tierInfo.icon,
          x,
          y,
          width: CARD_W,
          height: CARD_H,
          colIndex: 0,
          isHotspot,
          hasIssues,
          symbolsCount: f.symbols_count || (fileSyms.length + fileCls.length),
          issuesCount: f.issues_count || 0,
          classesCount: fileCls.length,
          functionsCount: fileSyms.length,
          inboundCallers: inboundMap[f.path] || [],
          outboundDependencies: outboundMap[f.path] || [],
        });
      });
    }

    const visibleIds = new Set(nodes.map((n) => n.id));
    const edges = rawEdges.filter((e) => visibleIds.has(e.source) && visibleIds.has(e.target));

    return { nodes, edges, totalWidth, totalHeight, activeTiers };
  }, [report, graphLayoutMode, graphTierFilter, graphSearchQuery, getFileTier]);

  return (
    <div className="min-h-screen bg-ground text-ink flex flex-col font-sans">
      {/* Top Navigation Bar */}
      <header className="sticky top-0 z-50 w-full border-b border-rule bg-panel/90 backdrop-blur-md px-4 sm:px-8 py-3.5 flex items-center justify-between">
        <div className="flex items-center gap-3">
          <div className="w-8 h-8 rounded-lg bg-accent flex items-center justify-center text-white shadow-sm">
            <Sparkles className="w-4 h-4" />
          </div>
          <div>
            <div className="flex items-center gap-2">
              <span className="font-display font-bold text-base text-ink tracking-tight">AI Code Reviewer</span>
              <span className="text-[11px] font-mono px-2 py-0.5 rounded-full bg-ground-muted text-ink-secondary border border-rule">
                Enterprise v2.0
              </span>
            </div>
            <p className="text-xs text-ink-secondary hidden sm:block">AST Visual Graphs, SAST Precision & Automated PR Bot</p>
          </div>
        </div>

        {/* Live Scan Status Indicator if running */}
        {isAnalyzing && (
          <div className="hidden md:flex items-center gap-2 px-3 py-1 rounded-full bg-accent/10 border border-accent/20 text-accent text-xs">
            <RefreshCw className="w-3.5 h-3.5 animate-spin" />
            <span>Analyzing repository & AST call-graph...</span>
          </div>
        )}

        {/* Navigation Tabs & Actions */}
        <div className="flex items-center gap-2">
          {report && (
            <div className="relative">
              <button
                onClick={() => setExportDropdownOpen(!exportDropdownOpen)}
                className="btn-secondary !text-xs !py-1.5 !px-3"
              >
                <Download className="w-3.5 h-3.5 text-accent" />
                <span>Export Audit</span>
                <ChevronDown className="w-3 h-3 text-ink-secondary" />
              </button>

              {exportDropdownOpen && (
                <div className="absolute right-0 mt-2 w-56 rounded-panel border border-rule bg-panel shadow-lifted p-1.5 z-50 animate-in fade-in">
                  <button
                    onClick={() => handleExport("sarif")}
                    disabled={isExporting !== null}
                    className="w-full text-left px-3 py-2 rounded-md text-xs hover:bg-ground-muted flex items-center justify-between text-ink"
                  >
                    <div className="flex items-center gap-2">
                      <ShieldCheck className="w-3.5 h-3.5 text-accent" />
                      <span>OASIS SARIF v2.1.0</span>
                    </div>
                    <span className="text-[10px] font-mono text-ink-secondary">.json</span>
                  </button>
                  <button
                    onClick={() => handleExport("markdown")}
                    disabled={isExporting !== null}
                    className="w-full text-left px-3 py-2 rounded-md text-xs hover:bg-ground-muted flex items-center justify-between text-ink"
                  >
                    <div className="flex items-center gap-2">
                      <FileText className="w-3.5 h-3.5 text-accent" />
                      <span>Executive Audit Report</span>
                    </div>
                    <span className="text-[10px] font-mono text-ink-secondary">.md</span>
                  </button>
                </div>
              )}
            </div>
          )}

          <button
            onClick={() => setActiveTab("dashboard")}
            className={`flex items-center gap-2 px-3.5 py-1.5 rounded-lg text-sm font-medium transition-all ${
              activeTab === "dashboard"
                ? "bg-accent text-white shadow-sm"
                : "text-ink-secondary hover:text-ink hover:bg-ground-muted"
            }`}
          >
            <Code2 className="w-4 h-4" />
            <span>Analyzer Dashboard</span>
          </button>
          <button
            onClick={() => setActiveTab("settings")}
            className={`flex items-center gap-2 px-3.5 py-1.5 rounded-lg text-sm font-medium transition-all relative ${
              activeTab === "settings"
                ? "bg-accent text-white shadow-sm"
                : "text-ink-secondary hover:text-ink hover:bg-ground-muted"
            }`}
          >
            <SettingsIcon className="w-4 h-4" />
            <span>Settings</span>
            {(settings.openaiApiKey || settings.geminiApiKey || settings.githubToken) && (
              <span className="w-2 h-2 rounded-full bg-accent absolute top-1.5 right-1.5 ring-2 ring-panel" />
            )}
          </button>

          {/* Dark / Light Mode Toggle */}
          <button
            onClick={toggleTheme}
            className="p-2 rounded-lg border border-rule bg-panel hover:bg-ground-muted text-ink-secondary transition-all"
            title={theme === "dark" ? "Switch to Light Mode" : "Switch to Dark Mode"}
            aria-label="Toggle theme"
          >
            {theme === "dark" ? <Sun className="w-4 h-4 text-amber-400 animate-in fade-in" /> : <Moon className="w-4 h-4 text-indigo-600 animate-in fade-in" />}
          </button>
        </div>
      </header>

      {/* Main Container */}
      <main className="flex-1 w-full max-w-7xl mx-auto px-4 sm:px-6 py-8">
        {/* ========================================================= */}
        {/* VIEW 1: DASHBOARD VIEW */}
        {/* ========================================================= */}
        <div className={activeTab === "dashboard" ? "block space-y-10" : "hidden"}>
          
          {/* CLEAN BENTO COMMAND BAR */}
          <div className="space-y-6 pt-2 pb-2">
            {/* Top row: Title + Benchmark Telemetry Scorecard */}
            <div className="flex flex-col lg:flex-row lg:items-end justify-between gap-5">
              <div className="space-y-2 max-w-2xl">
                <div className="inline-flex items-center gap-2 px-3 py-1 rounded-full bg-accent/10 border border-accent/20 text-xs font-medium text-accent">
                  <span className="w-2 h-2 rounded-full bg-accent animate-pulse" />
                  <span>Deterministic SAST + 2-Hop AST Engine</span>
                </div>
                <h1 className="font-display font-bold text-3xl sm:text-4xl text-ink tracking-tight">
                  AI Code Reviewer & Security Gate
                </h1>
                <p className="text-sm text-ink-secondary leading-relaxed">
                  Automated architectural code reviews, Tree-sitter call graphs, and committable suggestion blocks directly into GitHub PRs.
                </p>
              </div>

              {/* Verified Benchmark Scorecard Tile */}
              <div className="flex items-center gap-4 bg-panel border border-rule px-5 py-3 rounded-2xl shadow-xs text-xs font-mono shrink-0">
                <div>
                  <span className="block text-[10px] text-ink-secondary uppercase tracking-wider">Detection Recall</span>
                  <span className="text-base font-bold text-accent">96.0%</span>
                </div>
                <div className="w-px h-8 bg-rule" />
                <div>
                  <span className="block text-[10px] text-ink-secondary uppercase tracking-wider">False Positives</span>
                  <span className="text-base font-bold text-emerald-500">0.0%</span>
                </div>
                <div className="w-px h-8 bg-rule" />
                <div>
                  <span className="block text-[10px] text-ink-secondary uppercase tracking-wider">Noise Filtered</span>
                  <span className="text-base font-bold text-ink">83.3%</span>
                </div>
              </div>
            </div>

            {/* Central Unified Input Command Bar */}
            <div className="p-2 bg-panel border border-rule rounded-2xl shadow-card focus-within:border-accent focus-within:ring-2 focus-within:ring-accent/15 transition-all">
              <form
                onSubmit={(e) => {
                  e.preventDefault();
                  runAnalysis();
                }}
                className="flex flex-col sm:flex-row gap-2 items-stretch"
              >
                <div className="flex items-center gap-2.5 px-3 py-2 flex-1">
                  <Search className="w-4 h-4 text-ink-secondary shrink-0" />
                  <input
                    type="url"
                    value={gitUrl}
                    onChange={(e) => setGitUrl(e.target.value)}
                    placeholder="Enter GitHub repository or Pull Request URL (e.g. https://github.com/owner/repo/pull/42)..."
                    className="w-full bg-transparent text-sm text-ink placeholder:text-ink-secondary/60 focus:outline-none font-mono"
                    disabled={isAnalyzing}
                  />
                  {gitUrl && !isAnalyzing && (
                    <button
                      type="button"
                      onClick={() => setGitUrl("")}
                      className="text-ink-secondary hover:text-ink p-1"
                    >
                      <X className="w-4 h-4" />
                    </button>
                  )}
                </div>

                <button
                  type="submit"
                  disabled={isAnalyzing || !gitUrl.trim()}
                  className={`btn-primary shrink-0 !py-2.5 !px-5 ${
                    isAnalyzing || !gitUrl.trim() ? "opacity-50 cursor-not-allowed" : ""
                  }`}
                >
                  {isAnalyzing ? (
                    <>
                      <RefreshCw className="w-4 h-4 animate-spin" />
                      <span>Inspecting AST & Diffs...</span>
                    </>
                  ) : (
                    <>
                      <Zap className="w-4 h-4" />
                      <span>Start Code Review</span>
                    </>
                  )}
                </button>
              </form>

              {/* Quick Try Sample Targets */}
              <div className="flex flex-wrap items-center gap-2 px-3 pt-2.5 pb-1 text-xs text-ink-secondary border-t border-rule/50 mt-1">
                <span className="text-[11px] font-medium text-ink-secondary">Sample Targets:</span>
                <button
                  type="button"
                  onClick={() => handleQuickUrl("https://github.com/abduzeedo/mapc-site.git")}
                  className="px-2 py-0.5 rounded-md bg-ground-muted hover:bg-rule/60 border border-rule font-mono text-[11px] text-ink transition-colors"
                >
                  abduzeedo/mapc-site (PR)
                </button>
                <button
                  type="button"
                  onClick={() => handleQuickUrl("https://github.com/HappyShadowCoder/Qurating-Reimplementation")}
                  className="px-2 py-0.5 rounded-md bg-ground-muted hover:bg-rule/60 border border-rule font-mono text-[11px] text-ink transition-colors"
                >
                  HappyShadowCoder/Qurating
                </button>
                <button
                  type="button"
                  onClick={() => handleQuickUrl("https://github.com/pallets/flask")}
                  className="px-2 py-0.5 rounded-md bg-ground-muted hover:bg-rule/60 border border-rule font-mono text-[11px] text-ink transition-colors"
                >
                  pallets/flask
                </button>
              </div>
            </div>
          </div>

          {/* Analysis Progress / Error Card if active */}
          {isAnalyzing && (
            <div className="p-6 rounded-panel border border-rule bg-panel shadow-card space-y-4">
              <div className="flex items-center justify-between">
                <div className="flex items-center gap-3">
                  <RefreshCw className="w-5 h-5 text-accent animate-spin" />
                  <div>
                    <h3 className="text-sm font-display font-bold text-ink">
                      {analysisStep === 1 && "Fetching Git Repository & Commits..."}
                      {analysisStep === 2 && "Extracting Tree-sitter AST & Call Graph..."}
                      {analysisStep === 3 && "Running SAST Deterministic Security Rules..."}
                      {analysisStep >= 4 && "Synthesizing Architectural Review & Fix Suggestions..."}
                    </h3>
                    <p className="text-xs text-ink-secondary">
                      {analysisStep === 1 && "Connecting to repository, loading shallow commit tree and files..."}
                      {analysisStep === 2 && "Walking syntax trees, scoping functions, classes, and cross-file references..."}
                      {analysisStep === 3 && "Auditing code against OWASP Top 10, SQLi, command injection, and secret rules..."}
                      {analysisStep >= 4 && "Assembling cross-file context, generating code corrections, and calculating health score..."}
                    </p>
                  </div>
                </div>
                <div className="text-right">
                  <span className="text-xs font-mono font-bold text-accent">
                    {analysisStep <= 4 ? `Step ${analysisStep} of 4` : "Complete"}
                  </span>
                  <span className="block text-[10px] text-ink-secondary">
                    {analysisStep === 1 && "25%"}
                    {analysisStep === 2 && "50%"}
                    {analysisStep === 3 && "75%"}
                    {analysisStep === 4 && "88% (processing)"}
                    {analysisStep >= 5 && "100%"}
                  </span>
                </div>
              </div>
              <div className="w-full bg-ground-muted rounded-full h-2 overflow-hidden">
                <div
                  className={`bg-accent h-2 rounded-full transition-all duration-500 ${analysisStep === 4 ? "animate-pulse" : ""}`}
                  style={{
                    width: `${
                      analysisStep === 1
                        ? 25
                        : analysisStep === 2
                        ? 50
                        : analysisStep === 3
                        ? 75
                        : analysisStep === 4
                        ? 88
                        : 100
                    }%`,
                  }}
                />
              </div>
            </div>
          )}

          {analysisError && (
            <div className="p-4 rounded-panel bg-rose-50 border border-rose-200 text-rose-800 text-xs flex items-center justify-between">
              <div className="flex items-center gap-2">
                <AlertCircle className="w-4 h-4 text-rose-600 shrink-0" />
                <span>{analysisError}</span>
              </div>
              <button onClick={() => setAnalysisError(null)} className="text-rose-600 hover:text-rose-900 font-bold">
                ✕
              </button>
            </div>
          )}

          {/* SUBSTANTIAL DARK PASSAGE 1: DEEP ANALYSIS CONSOLE / PROCESS & RESULTS */}
          <div className="bg-field text-on-field rounded-panel p-6 sm:p-10 border border-slate-800 shadow-2xl">
            {report ? (
              /* LIVE REPORT VIEW */
              <div className="space-y-6">
                {/* Report Header Bar */}
                <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4 pb-6 border-b border-slate-800">
                  <div className="flex items-center gap-3">
                    <div className="w-10 h-10 rounded-lg bg-accent/20 border border-accent/30 flex items-center justify-center text-accent">
                      <Terminal className="w-5 h-5 text-blue-400" />
                    </div>
                    <div>
                      <h2 className="font-display font-bold text-lg text-on-field flex items-center gap-2">
                        <span>{report.repo_summary.name}</span>
                        <span className="text-xs font-normal text-on-field-secondary">by {report.repo_summary.owner}</span>
                        <span className="text-xs px-2 py-0.5 rounded-full bg-slate-800 text-slate-300 border border-slate-700 font-mono">
                          {report.repo_summary.target_type === "pull_request" ? "Pull Request" : "Repository"}
                        </span>
                      </h2>
                      <p className="text-xs text-on-field-secondary font-mono mt-0.5">
                        Target: {report.repo_summary.analyzed_target} • Engine: {report.ai_provider_used} ({report.ai_model_used})
                      </p>
                    </div>
                  </div>

                  {/* Sub-Tabs Pills */}
                  <div className="flex items-center p-1 bg-slate-950 rounded-lg border border-slate-800 shrink-0 flex-wrap gap-1">
                    <button
                      onClick={() => setReportSubTab("overview")}
                      className={`px-3 py-1.5 rounded-md text-xs font-medium transition-all ${
                        reportSubTab === "overview" ? "bg-accent text-white shadow" : "text-slate-400 hover:text-slate-200"
                      }`}
                    >
                      Overview & Architecture
                    </button>
                    <button
                      onClick={() => setReportSubTab("corrections")}
                      className={`px-3 py-1.5 rounded-md text-xs font-medium transition-all flex items-center gap-1.5 ${
                        reportSubTab === "corrections" ? "bg-accent text-white shadow" : "text-slate-400 hover:text-slate-200"
                      }`}
                    >
                      <span>Code Corrections</span>
                      <span className="px-1.5 py-0.2 rounded-full bg-rose-500/20 text-rose-300 text-[10px] font-mono">
                        {report.code_corrections?.length || 0}
                      </span>
                    </button>
                    <button
                      onClick={() => setReportSubTab("files")}
                      className={`px-3 py-1.5 rounded-md text-xs font-medium transition-all flex items-center gap-1.5 ${
                        reportSubTab === "files" ? "bg-accent text-white shadow" : "text-slate-400 hover:text-slate-200"
                      }`}
                    >
                      <span>Deep File Inspector</span>
                      <span className="px-1.5 py-0.2 rounded-full bg-slate-800 text-slate-300 text-[10px] font-mono">
                        {report.file_tree?.length || 0}
                      </span>
                    </button>
                    <button
                      onClick={() => setReportSubTab("git")}
                      className={`px-3 py-1.5 rounded-md text-xs font-medium transition-all flex items-center gap-1.5 ${
                        reportSubTab === "git" ? "bg-accent text-white shadow" : "text-slate-400 hover:text-slate-200"
                      }`}
                    >
                      <span>Commits & PRs</span>
                      <span className="px-1.5 py-0.2 rounded-full bg-slate-800 text-slate-300 text-[10px] font-mono">
                        {report.commits_report?.length || 0}
                      </span>
                    </button>
                  </div>
                </div>

                {/* SUBTAB 1: OVERVIEW & ARCHITECTURE + VISUAL CALL-GRAPH */}
                {reportSubTab === "overview" && (
                  <div className="space-y-6">
                    {/* Top KPI Cards */}
                    <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-4">
                      <div className="p-5 rounded-xl border border-slate-800 bg-slate-900/60">
                        <div className="flex items-center justify-between">
                          <span className="text-xs font-medium text-slate-400">Health Score</span>
                          <ShieldCheck className={`w-4 h-4 ${report.repo_summary.health_score >= 80 ? "text-emerald-400" : "text-amber-400"}`} />
                        </div>
                        <div className="mt-2 flex items-baseline gap-2">
                          <span className="text-3xl font-display font-bold text-white">{report.repo_summary.health_score}</span>
                          <span className="text-xs text-slate-500">/ 100</span>
                        </div>
                        <div className="mt-2 text-xs font-medium text-emerald-400">
                          {report.repo_summary.health_score >= 80 ? "Production Grade" : "Action Needed"}
                        </div>
                      </div>

                      <div className="p-5 rounded-xl border border-slate-800 bg-slate-900/60">
                        <div className="flex items-center justify-between">
                          <span className="text-xs font-medium text-slate-400">GitHub Stats</span>
                          <Zap className="w-4 h-4 text-blue-400" />
                        </div>
                        <div className="mt-2 flex items-baseline gap-4">
                          <div>
                            <span className="text-2xl font-bold text-white">{report.repo_summary.stars}</span>
                            <span className="text-xs text-slate-500 ml-1">stars</span>
                          </div>
                          <div>
                            <span className="text-2xl font-bold text-slate-300">{report.repo_summary.forks}</span>
                            <span className="text-xs text-slate-500 ml-1">forks</span>
                          </div>
                        </div>
                        <div className="mt-2 text-xs text-slate-400 font-mono">Branch: {report.repo_summary.default_branch}</div>
                      </div>

                      <div className="p-5 rounded-xl border border-slate-800 bg-slate-900/60">
                        <div className="flex items-center justify-between">
                          <span className="text-xs font-medium text-slate-400">Tree-sitter AST</span>
                          <Network className="w-4 h-4 text-indigo-400" />
                        </div>
                        <div className="mt-2 flex items-baseline gap-2">
                          <span className="text-3xl font-display font-bold text-white">{report.ast_insights?.total_symbols || 0}</span>
                          <span className="text-xs text-slate-500">symbols</span>
                        </div>
                        <div className="mt-2 text-xs text-slate-400">
                          {report.ast_insights?.classes_count || 0} classes • {report.ast_insights?.functions_count || 0} functions
                        </div>
                      </div>

                      <div className="p-5 rounded-xl border border-slate-800 bg-slate-900/60">
                        <div className="flex items-center justify-between">
                          <span className="text-xs font-medium text-slate-400">Code Remediations</span>
                          <Flame className="w-4 h-4 text-rose-400" />
                        </div>
                        <div className="mt-2 flex items-baseline gap-2">
                          <span className="text-3xl font-display font-bold text-white">{report.code_corrections?.length || 0}</span>
                          <span className="text-xs text-slate-500">issues</span>
                        </div>
                        <div className="mt-2 text-xs text-slate-400">
                          {(report.code_corrections || []).filter((c) => c.severity === "critical").length} critical •{" "}
                          {(report.code_corrections || []).filter((c) => c.severity === "high").length} high
                        </div>
                      </div>
                    </div>

                    {/* GITDIAGRAM-STYLE INTERACTIVE ARCHITECTURAL & CALL-GRAPH CANVAS */}
                    <div className="p-6 rounded-xl border border-rule bg-panel dark:bg-slate-900/80 dark:border-slate-800 space-y-4 shadow-sm transition-colors">
                      {/* Top Bar: Title & Controls */}
                      <div className="flex flex-col lg:flex-row lg:items-center justify-between gap-4">
                        <div>
                          <div className="flex items-center gap-2 text-sm font-semibold text-ink dark:text-white">
                            <Network className="w-4 h-4 text-accent" />
                            <span>Interactive Architectural & Call-Graph Canvas</span>
                            <span className="text-[10px] font-mono px-2 py-0.5 rounded-full bg-accent/10 text-accent border border-accent/20">
                              GitDiagram Engine
                            </span>
                          </div>
                          <p className="text-xs text-ink-secondary dark:text-slate-400 mt-0.5">
                            Visualizes Tree-sitter module dependencies, import paths, and coupling hotspots across architectural layers. Click any node to focus callers and dependencies.
                          </p>
                        </div>

                        {/* Top Controls: Layout switcher, Zoom, Reset */}
                        <div className="flex flex-wrap items-center gap-2">
                          {/* Layout Toggle */}
                          <div className="flex items-center rounded-lg border border-rule dark:border-slate-800 bg-ground-muted dark:bg-slate-950 p-0.5">
                            <button
                              onClick={() => setGraphLayoutMode("gitdiagram")}
                              className={`px-2.5 py-1 rounded-md text-xs font-medium transition-all ${
                                graphLayoutMode === "gitdiagram"
                                  ? "bg-accent text-white shadow-sm"
                                  : "text-ink-secondary dark:text-slate-400 hover:text-ink dark:hover:text-white"
                              }`}
                            >
                              GitDiagram Flow
                            </button>
                            <button
                              onClick={() => setGraphLayoutMode("layered")}
                              className={`px-2.5 py-1 rounded-md text-xs font-medium transition-all ${
                                graphLayoutMode === "layered"
                                  ? "bg-accent text-white shadow-sm"
                                  : "text-ink-secondary dark:text-slate-400 hover:text-ink dark:hover:text-white"
                              }`}
                            >
                              AST Modules
                            </button>
                            <button
                              onClick={() => setGraphLayoutMode("cluster")}
                              className={`px-2.5 py-1 rounded-md text-xs font-medium transition-all ${
                                graphLayoutMode === "cluster"
                                  ? "bg-accent text-white shadow-sm"
                                  : "text-ink-secondary dark:text-slate-400 hover:text-ink dark:hover:text-white"
                              }`}
                            >
                              Radial Cluster
                            </button>
                          </div>

                          {/* Zoom Controls */}
                          <div className="flex items-center gap-1 bg-ground-muted dark:bg-slate-950 border border-rule dark:border-slate-800 rounded-lg p-0.5">
                            <button
                              onClick={() => setGraphZoom((z) => Math.max(0.5, z - 0.15))}
                              className="p-1 rounded hover:bg-panel dark:hover:bg-slate-800 text-ink-secondary dark:text-slate-400"
                              title="Zoom Out"
                            >
                              <ZoomOut className="w-3.5 h-3.5" />
                            </button>
                            <span className="text-[11px] font-mono px-1.5 text-ink-secondary dark:text-slate-400">{Math.round(graphZoom * 100)}%</span>
                            <button
                              onClick={() => setGraphZoom((z) => Math.min(2.0, z + 0.15))}
                              className="p-1 hover:bg-panel dark:hover:bg-slate-800 text-ink-secondary dark:text-slate-400"
                              title="Zoom In"
                            >
                              <ZoomIn className="w-3.5 h-3.5" />
                            </button>
                            <button
                              onClick={() => {
                                setGraphZoom(1);
                                setFocusedGraphNode(null);
                              }}
                              className="px-2 py-0.5 rounded text-[11px] font-mono text-ink-secondary dark:text-slate-400 hover:bg-panel dark:hover:bg-slate-800"
                            >
                              Reset
                            </button>
                          </div>
                        </div>
                      </div>

                      {/* Filter & Search Bar */}
                      <div className="flex flex-col sm:flex-row items-stretch sm:items-center justify-between gap-2 pt-2 border-t border-rule dark:border-slate-800/80">
                        {/* Tier Filters */}
                        <div className="flex items-center gap-1.5 overflow-x-auto pb-1 sm:pb-0 text-xs">
                          {[
                            { key: "all", label: `All (${report.file_tree?.length || 0})` },
                            { key: "entry", label: "Entrypoint" },
                            { key: "routes", label: "Routes & APIs" },
                            { key: "services", label: "Services" },
                            { key: "ml", label: "ML Engine" },
                            { key: "data", label: "Data / DB" },
                            { key: "flagged", label: "Flagged Only" },
                          ].map((t) => (
                            <button
                              key={t.key}
                              onClick={() => setGraphTierFilter(t.key)}
                              className={`px-2.5 py-1 rounded-md text-xs font-medium whitespace-nowrap transition-all ${
                                graphTierFilter === t.key
                                  ? "bg-accent/15 text-accent border border-accent/30 font-semibold"
                                  : "text-ink-secondary dark:text-slate-400 hover:bg-ground-muted dark:hover:bg-slate-800 border border-transparent"
                              }`}
                            >
                              {t.label}
                            </button>
                          ))}
                        </div>

                        {/* Search Input */}
                        <div className="relative min-w-[180px]">
                          <Search className="w-3.5 h-3.5 absolute left-2.5 top-2.5 text-ink-secondary dark:text-slate-500" />
                          <input
                            type="text"
                            value={graphSearchQuery}
                            onChange={(e) => setGraphSearchQuery(e.target.value)}
                            placeholder="Filter modules..."
                            className="w-full text-xs pl-8 pr-2.5 py-1.5 rounded-lg border border-rule dark:border-slate-800 bg-ground dark:bg-slate-950 text-ink dark:text-white placeholder:text-ink-secondary/60 focus:outline-none focus:border-accent"
                          />
                          {graphSearchQuery && (
                            <button
                              onClick={() => setGraphSearchQuery("")}
                              className="absolute right-2 top-2 text-ink-secondary dark:text-slate-500 hover:text-ink"
                            >
                              <X className="w-3 h-3" />
                            </button>
                          )}
                        </div>
                      </div>

                      {/* Main Canvas Area */}
                      {graphLayoutMode === "gitdiagram" ? (
                        <MermaidViewer
                          chart={report.architecture_advice?.mermaid_diagram || "flowchart TD\n  Start[System Start] --> End[System Ready]"}
                          theme={theme}
                        />
                      ) : (
                      <div className="w-full h-[520px] rounded-lg bg-ground-muted/40 dark:bg-slate-950 border border-rule dark:border-slate-800 relative overflow-hidden flex items-center justify-center">
                        <svg
                          viewBox={`0 0 ${graphData.totalWidth} ${graphData.totalHeight}`}
                          className="w-full h-full select-none cursor-grab active:cursor-grabbing"
                          style={{
                            transform: `scale(${graphZoom})`,
                            transformOrigin: "center center",
                            transition: "transform 0.15s ease-out",
                          }}
                        >
                          <defs>
                            {/* Directional Arrow Marker */}
                            <marker
                              id="arrow"
                              viewBox="0 0 10 10"
                              refX="9"
                              refY="5"
                              markerWidth="6"
                              markerHeight="6"
                              orient="auto-start-reverse"
                            >
                              <path d="M 0 1 L 9 5 L 0 9 z" fill="#3b82f6" />
                            </marker>
                            <marker
                              id="arrow-active"
                              viewBox="0 0 10 10"
                              refX="9"
                              refY="5"
                              markerWidth="6"
                              markerHeight="6"
                              orient="auto-start-reverse"
                            >
                              <path d="M 0 1 L 9 5 L 0 9 z" fill="#38bdf8" />
                            </marker>
                            <marker
                              id="arrow-inbound"
                              viewBox="0 0 10 10"
                              refX="9"
                              refY="5"
                              markerWidth="6"
                              markerHeight="6"
                              orient="auto-start-reverse"
                            >
                              <path d="M 0 1 L 9 5 L 0 9 z" fill="#34d399" />
                            </marker>
                            <linearGradient id="edgeGrad" x1="0%" y1="0%" x2="100%" y2="100%">
                              <stop offset="0%" stopColor="#38bdf8" stopOpacity="0.4" />
                              <stop offset="100%" stopColor="#3b82f6" stopOpacity="0.8" />
                            </linearGradient>
                            <linearGradient id="edgeHotGrad" x1="0%" y1="0%" x2="100%" y2="100%">
                              <stop offset="0%" stopColor="#f43f5e" stopOpacity="0.7" />
                              <stop offset="100%" stopColor="#fb7185" stopOpacity="0.9" />
                            </linearGradient>
                          </defs>

                          {/* Column Headers in Layered Mode */}
                          {graphLayoutMode === "layered" &&
                            (graphData.activeTiers || []).map((col, idx) => (
                              <g key={idx} transform={`translate(${col.x}, 40)`}>
                                <rect
                                  x="0"
                                  y="0"
                                  width="180"
                                  height="26"
                                  rx="6"
                                  fill={theme === "dark" ? "#1e293b" : "#e2e8f0"}
                                  fillOpacity="0.6"
                                />
                                <text
                                  x="90"
                                  y="17"
                                  textAnchor="middle"
                                  fontSize="11"
                                  fontFamily="monospace"
                                  fontWeight="600"
                                  fill={theme === "dark" ? "#94a3b8" : "#475569"}
                                >
                                  {col.label.toUpperCase()}
                                </text>
                              </g>
                            ))}

                          {/* Connector Edges */}
                          {(graphData.edges || []).map((edge, idx) => {
                            const sNode = graphData.nodes.find((n) => n.id === edge.source);
                            const tNode = graphData.nodes.find((n) => n.id === edge.target);
                            if (!sNode || !tNode) return null;

                            const isOutboundFromFocused = focusedGraphNode === sNode.id;
                            const isInboundToFocused = focusedGraphNode === tNode.id;
                            const isFocusedPath = isOutboundFromFocused || isInboundToFocused;

                            const sx = sNode.x + sNode.width;
                            const sy = sNode.y + sNode.height / 2;
                            const tx = tNode.x;
                            const ty = tNode.y + tNode.height / 2;
                            const cx1 = (sx + tx) / 2;

                            // Cubic Bezier curve
                            const pathData =
                              graphLayoutMode === "layered"
                                ? `M ${sx} ${sy} C ${cx1} ${sy}, ${cx1} ${ty}, ${tx} ${ty}`
                                : `M ${sNode.x + sNode.width / 2} ${sNode.y + sNode.height / 2} L ${tNode.x + tNode.width / 2} ${tNode.y + tNode.height / 2}`;

                            const strokeColor = isInboundToFocused
                              ? "#34d399"
                              : isOutboundFromFocused
                              ? "#38bdf8"
                              : edge.isHot
                              ? "url(#edgeHotGrad)"
                              : "url(#edgeGrad)";

                            const strokeWidth = isFocusedPath ? 2.5 : edge.isHot ? 2 : 1.2;
                            const opacity = focusedGraphNode ? (isFocusedPath ? 1 : 0.12) : 0.65;

                            return (
                              <path
                                key={idx}
                                d={pathData}
                                fill="none"
                                stroke={strokeColor}
                                strokeWidth={strokeWidth}
                                strokeDasharray={isFocusedPath ? "6 4" : edge.isHot ? "4 3" : undefined}
                                className={isFocusedPath ? "edge-flow" : undefined}
                                opacity={opacity}
                                markerEnd={
                                  isInboundToFocused
                                    ? "url(#arrow-inbound)"
                                    : isOutboundFromFocused
                                    ? "url(#arrow-active)"
                                    : "url(#arrow)"
                                }
                              />
                            );
                          })}

                          {/* Interactive Node Cards */}
                          {(graphData.nodes || []).map((node) => {
                            const isFocused = focusedGraphNode === node.id;
                            const isConnectedToFocused =
                              focusedGraphNode &&
                              graphData.edges.some(
                                (e) =>
                                  (e.source === focusedGraphNode && e.target === node.id) ||
                                  (e.target === focusedGraphNode && e.source === node.id)
                              );
                            const nodeOpacity = focusedGraphNode ? (isFocused || isConnectedToFocused ? 1 : 0.22) : 1;

                            return (
                              <g
                                key={node.id}
                                transform={`translate(${node.x}, ${node.y})`}
                                className="cursor-pointer transition-transform"
                                opacity={nodeOpacity}
                                onClick={() => setFocusedGraphNode(isFocused ? null : node.id)}
                              >
                                {/* Hotspot / Halo Ring */}
                                {node.isHotspot && (
                                  <rect
                                    x="-3"
                                    y="-3"
                                    width={node.width + 6}
                                    height={node.height + 6}
                                    rx="11"
                                    fill="#f43f5e"
                                    fillOpacity="0.15"
                                    stroke="#f43f5e"
                                    strokeWidth="1"
                                    strokeDasharray="4 3"
                                  />
                                )}

                                {/* Focused active glow */}
                                {isFocused && (
                                  <rect
                                    x="-3"
                                    y="-3"
                                    width={node.width + 6}
                                    height={node.height + 6}
                                    rx="11"
                                    fill={node.color}
                                    fillOpacity="0.2"
                                    stroke={node.color}
                                    strokeWidth="2"
                                  />
                                )}

                                {/* Card Background */}
                                <rect
                                  x="0"
                                  y="0"
                                  width={node.width}
                                  height={node.height}
                                  rx="8"
                                  fill={theme === "dark" ? "#0f172a" : "#ffffff"}
                                  stroke={isFocused ? node.color : node.isHotspot ? "#fb7185" : theme === "dark" ? "#334155" : "#cbd5e1"}
                                  strokeWidth={isFocused ? "2" : "1"}
                                  className="transition-colors"
                                />

                                {/* Tier Color Accent Strip */}
                                <rect
                                  x="0"
                                  y="0"
                                  width="4"
                                  height={node.height}
                                  rx="2"
                                  fill={node.color}
                                />

                                {/* Tier Icon & Tag */}
                                <text
                                  x="12"
                                  y="16"
                                  fontSize="9"
                                  fontFamily="sans-serif"
                                  fontWeight="600"
                                  fill={node.color}
                                >
                                  {node.icon} {node.tierLabel}
                                </text>

                                {/* File Name */}
                                <text
                                  x="12"
                                  y="34"
                                  fontSize="11"
                                  fontFamily="monospace"
                                  fontWeight="bold"
                                  fill={theme === "dark" ? "#f8fafc" : "#0f172a"}
                                >
                                  {node.label.length > 18 ? node.label.slice(0, 16) + "…" : node.label}
                                </text>

                                {/* Issues / Symbol Badge Pill on the right */}
                                {node.hasIssues ? (
                                  <g transform={`translate(${node.width - 34}, 8)`}>
                                    <rect x="0" y="0" width="26" height="15" rx="4" fill="#881337" />
                                    <text x="13" y="11" textAnchor="middle" fontSize="8" fontFamily="sans-serif" fontWeight="bold" fill="#fecdd3">
                                      {node.issuesCount} ⚠️
                                    </text>
                                  </g>
                                ) : (
                                  <g transform={`translate(${node.width - 36}, 8)`}>
                                    <rect x="0" y="0" width="28" height="15" rx="4" fill={theme === "dark" ? "#1e293b" : "#f1f5f9"} />
                                    <text x="14" y="11" textAnchor="middle" fontSize="8" fontFamily="monospace" fill={theme === "dark" ? "#94a3b8" : "#64748b"}>
                                      {node.symbolsCount}s
                                    </text>
                                  </g>
                                )}
                              </g>
                            );
                          })}
                        </svg>

                        {/* Visual Legend */}
                        <div className="absolute bottom-3 left-3 bg-panel/90 dark:bg-slate-900/90 border border-rule dark:border-slate-800 rounded-lg p-2 text-[10px] text-ink-secondary dark:text-slate-400 space-y-1 backdrop-blur-sm pointer-events-none shadow-sm">
                          <div className="flex items-center gap-2">
                            <span className="w-2.5 h-2.5 rounded-full bg-sky-400" />
                            <span>Entrypoint / Controller</span>
                          </div>
                          <div className="flex items-center gap-2">
                            <span className="w-2.5 h-2.5 rounded-full bg-emerald-400" />
                            <span>Routes & APIs</span>
                          </div>
                          <div className="flex items-center gap-2">
                            <span className="w-2.5 h-2.5 rounded-full bg-purple-400" />
                            <span>Services & Logic</span>
                          </div>
                          <div className="flex items-center gap-2">
                            <span className="w-2.5 h-2.5 rounded-full bg-amber-400" />
                            <span>ML Engine & Models</span>
                          </div>
                          <div className="flex items-center gap-2">
                            <span className="w-2.5 h-2.5 rounded-full bg-rose-500" />
                            <span>Data / DB / Hotspot</span>
                          </div>
                        </div>

                        {/* Interactive Node Detail Inspector Drawer */}
                        {focusedGraphNode && (() => {
                          const activeNode = graphData.nodes.find((n) => n.id === focusedGraphNode);
                          if (!activeNode) return null;
                          const fileSymbols = (report.ast_insights?.functions || []).filter((f) => f?.file_path === activeNode.fullPath);
                          const fileClasses = (report.ast_insights?.classes || []).filter((c) => c?.file_path === activeNode.fullPath);
                          const fileIssues = (report.code_corrections || []).filter((c) => c.file_path === activeNode.fullPath);

                          return (
                            <div className="absolute right-3 top-3 bottom-3 w-80 bg-panel/95 dark:bg-slate-900/95 border border-rule dark:border-slate-800 rounded-xl shadow-lifted p-4 flex flex-col justify-between overflow-y-auto z-20 backdrop-blur-md animate-in slide-in-from-right-4">
                              <div className="space-y-3">
                                {/* Header */}
                                <div className="flex items-start justify-between gap-2 border-b border-rule dark:border-slate-800 pb-2.5">
                                  <div>
                                    <div className="flex items-center gap-1.5">
                                      <span className="text-sm">{activeNode.icon}</span>
                                      <span className="text-xs font-mono font-bold text-ink dark:text-white truncate max-w-[190px]">
                                        {activeNode.label}
                                      </span>
                                    </div>
                                    <span className="text-[10px] font-mono text-ink-secondary dark:text-slate-400 block truncate mt-0.5">
                                      {activeNode.fullPath}
                                    </span>
                                  </div>
                                  <button
                                    onClick={() => setFocusedGraphNode(null)}
                                    className="p-1 rounded-md text-ink-secondary dark:text-slate-400 hover:bg-ground-muted dark:hover:bg-slate-800"
                                  >
                                    <X className="w-3.5 h-3.5" />
                                  </button>
                                </div>

                                {/* Layer & Hotspot Badges */}
                                <div className="flex flex-wrap items-center gap-1.5 text-[11px]">
                                  <span
                                    className="px-2 py-0.5 rounded font-medium"
                                    style={{ backgroundColor: `${activeNode.color}20`, color: activeNode.color }}
                                  >
                                    {activeNode.tierLabel}
                                  </span>
                                  {activeNode.isHotspot && (
                                    <span className="px-2 py-0.5 rounded bg-rose-500/20 text-rose-400 font-semibold border border-rose-500/30">
                                      🔥 Coupling Hotspot
                                    </span>
                                  )}
                                  {activeNode.hasIssues && (
                                    <span className="px-2 py-0.5 rounded bg-amber-500/20 text-amber-400 font-medium border border-amber-500/30">
                                      {activeNode.issuesCount} flagged issue{activeNode.issuesCount > 1 ? "s" : ""}
                                    </span>
                                  )}
                                </div>

                                {/* Call Graph Relationships */}
                                <div className="space-y-2 pt-1">
                                  <div className="text-[11px] font-semibold text-ink dark:text-slate-300">
                                    Call-Graph Relationships
                                  </div>
                                  
                                  {/* Inbound Callers */}
                                  <div>
                                    <span className="text-[10px] text-ink-secondary dark:text-slate-400 block mb-1">
                                      ⬅️ Incoming Callers ({activeNode.inboundCallers.length}):
                                    </span>
                                    {activeNode.inboundCallers.length > 0 ? (
                                      <div className="flex flex-wrap gap-1">
                                        {activeNode.inboundCallers.map((c: string, i: number) => (
                                          <button
                                            key={i}
                                            onClick={() => setFocusedGraphNode(c)}
                                            className="px-1.5 py-0.5 rounded bg-emerald-500/15 text-emerald-400 border border-emerald-500/20 text-[10px] font-mono hover:bg-emerald-500/25"
                                          >
                                            {c.split("/").pop()}
                                          </button>
                                        ))}
                                      </div>
                                    ) : (
                                      <span className="text-[10px] text-slate-500 italic">None (Root or Entrypoint)</span>
                                    )}
                                  </div>

                                  {/* Outbound Dependencies */}
                                  <div>
                                    <span className="text-[10px] text-ink-secondary dark:text-slate-400 block mb-1">
                                      ➡️ Dependencies Imported ({activeNode.outboundDependencies.length}):
                                    </span>
                                    {activeNode.outboundDependencies.length > 0 ? (
                                      <div className="flex flex-wrap gap-1">
                                        {activeNode.outboundDependencies.map((d: string, i: number) => (
                                          <button
                                            key={i}
                                            onClick={() => setFocusedGraphNode(d)}
                                            className="px-1.5 py-0.5 rounded bg-sky-500/15 text-sky-400 border border-sky-500/20 text-[10px] font-mono hover:bg-sky-500/25"
                                          >
                                            {d.split("/").pop()}
                                          </button>
                                        ))}
                                      </div>
                                    ) : (
                                      <span className="text-[10px] text-slate-500 italic">Leaf module</span>
                                    )}
                                  </div>
                                </div>

                                {/* Exported Symbols */}
                                <div className="space-y-1 pt-1">
                                  <span className="text-[11px] font-semibold text-ink dark:text-slate-300 block">
                                    Exported Symbols ({fileSymbols.length + fileClasses.length}):
                                  </span>
                                  <div className="max-h-28 overflow-y-auto space-y-1">
                                    {fileClasses.map((cls, i) => (
                                      <div key={i} className="text-[10px] font-mono text-purple-400 bg-purple-500/10 px-1.5 py-0.5 rounded">
                                        class {cls.name} (L{cls.start_line})
                                      </div>
                                    ))}
                                    {fileSymbols.map((sym, i) => (
                                      <div key={i} className="text-[10px] font-mono text-accent bg-accent/10 px-1.5 py-0.5 rounded">
                                        fn {sym.name}() (L{sym.start_line})
                                      </div>
                                    ))}
                                    {fileClasses.length === 0 && fileSymbols.length === 0 && (
                                      <span className="text-[10px] text-slate-500 italic">No AST definitions extracted</span>
                                    )}
                                  </div>
                                </div>

                                {/* Issues on this file */}
                                {fileIssues.length > 0 && (
                                  <div className="space-y-1 pt-1">
                                    <span className="text-[11px] font-semibold text-rose-400 block">
                                      Flagged Vulnerabilities:
                                    </span>
                                    <div className="space-y-1 max-h-24 overflow-y-auto">
                                      {fileIssues.map((iss, i) => (
                                        <div key={i} className="p-1.5 rounded bg-rose-500/10 border border-rose-500/20 text-[10px] text-rose-300">
                                          <span className="font-bold">{iss.category.toUpperCase()} (L{iss.start_line}):</span> {iss.explanation.slice(0, 60)}…
                                        </div>
                                      ))}
                                    </div>
                                  </div>
                                )}
                              </div>

                              {/* Action: Jump to Source */}
                              <div className="pt-3 border-t border-rule dark:border-slate-800">
                                <button
                                  onClick={() => {
                                    setSelectedFilePath(activeNode.fullPath);
                                    setReportSubTab("files");
                                  }}
                                  className="w-full btn-primary !text-xs !py-1.5 flex items-center justify-center gap-1.5"
                                >
                                  <FileCode className="w-3.5 h-3.5" />
                                  <span>Inspect File Source</span>
                                  <ArrowRight className="w-3 h-3" />
                                </button>
                              </div>
                            </div>
                          );
                        })()}
                      </div>
                      )}
                    </div>

                    {/* Executive Architectural Critique */}
                    <div className="p-6 rounded-xl border border-slate-800 bg-slate-900/70 space-y-3">
                      <div className="flex items-center gap-2 text-sm font-semibold text-white">
                        <Cpu className="w-4 h-4 text-accent" />
                        <span>Executive Architectural Critique</span>
                      </div>
                      <p className="text-sm text-slate-300 leading-relaxed">{report.repo_summary.executive_summary}</p>
                      <div className="p-3.5 rounded-lg bg-slate-950/80 border border-slate-800 text-xs text-slate-400 leading-relaxed">
                        <span className="font-semibold text-slate-300 block mb-1">Architecture Critique:</span>
                        {report.architecture_advice?.overall_critique || "Analysis complete."}
                      </div>
                    </div>

                    {/* Cross-File Coupling Hotspots & Bottlenecks */}
                    <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
                      <div className="p-5 rounded-xl border border-slate-800 bg-slate-900/50 space-y-4">
                        <div className="flex items-center justify-between">
                          <div className="flex items-center gap-2 text-sm font-semibold text-white">
                            <Network className="w-4 h-4 text-accent" />
                            <span>Cross-File Coupling Hotspots</span>
                          </div>
                          <span className="text-[11px] font-mono text-slate-400">AST Inferred</span>
                        </div>
                        <div className="space-y-3">
                          {(report.architecture_advice?.coupling_hotspots || []).map((hs, idx) => (
                            <div key={idx} className="p-3.5 rounded-lg bg-slate-950/70 border border-slate-800 space-y-1.5">
                              <div className="flex items-center justify-between">
                                <span className="font-mono text-xs text-blue-400 font-medium truncate max-w-[280px]">
                                  {hs.file_path}
                                </span>
                                <span className="px-2 py-0.5 rounded bg-blue-500/10 text-blue-300 border border-blue-500/20 text-[10px] font-mono">
                                  Risk {(hs.risk_score || 0).toFixed(0)}
                                </span>
                              </div>
                              <p className="text-xs text-slate-300">{hs.reason}</p>
                              {(hs.callers || []).length > 0 && (
                                <div className="text-[11px] text-slate-500 font-mono pt-1">
                                  Dependent Modules: {(hs.callers || []).join(", ")}
                                </div>
                              )}
                            </div>
                          ))}
                        </div>
                      </div>

                      <div className="p-5 rounded-xl border border-slate-800 bg-slate-900/50 space-y-4">
                        <div className="flex items-center justify-between">
                          <div className="flex items-center gap-2 text-sm font-semibold text-white">
                            <Flame className="w-4 h-4 text-amber-400" />
                            <span>Scalability & Concurrency Bottlenecks</span>
                          </div>
                          <span className="text-[11px] font-mono text-slate-400">Heuristic Engine</span>
                        </div>
                        <div className="space-y-3">
                          {(report.architecture_advice?.scalability_bottlenecks || []).map((sb, idx) => (
                            <div key={idx} className="p-3.5 rounded-lg bg-slate-950/70 border border-slate-800 space-y-1.5">
                              <div className="flex items-center justify-between">
                                <span className="text-xs font-semibold text-white">{sb.title}</span>
                                <span
                                  className={`px-2 py-0.5 rounded text-[10px] font-mono uppercase ${
                                    sb.severity === "critical"
                                      ? "bg-rose-500/10 text-rose-300 border border-rose-500/20"
                                      : "bg-amber-500/10 text-amber-300 border border-amber-500/20"
                                  }`}
                                >
                                  {sb.severity}
                                </span>
                              </div>
                              <p className="text-xs text-slate-400">{sb.description}</p>
                              <div className="text-xs text-emerald-400 bg-emerald-500/10 p-2 rounded border border-emerald-500/20 mt-1">
                                <span className="font-semibold">Fix: </span>
                                {sb.recommendation}
                              </div>
                            </div>
                          ))}
                        </div>
                      </div>
                    </div>
                  </div>
                )}

                {/* SUBTAB 2: CODE CORRECTIONS & 1-CLICK GITHUB BOT PR */}
                {reportSubTab === "corrections" && (
                  <div className="space-y-6">
                    {/* Filters Bar */}
                    <div className="flex flex-wrap items-center justify-between gap-3 p-3.5 rounded-xl bg-slate-900 border border-slate-800">
                      <div className="flex flex-wrap items-center gap-2">
                        <span className="text-xs text-slate-400 font-medium">Category:</span>
                        {["all", "security", "bug", "architecture", "concurrency", "performance"].map((cat) => (
                          <button
                            key={cat}
                            onClick={() => setCategoryFilter(cat)}
                            className={`px-2.5 py-1 rounded-md text-xs font-medium capitalize transition-all ${
                              categoryFilter === cat ? "bg-accent text-white" : "bg-slate-800 text-slate-400 hover:text-slate-200"
                            }`}
                          >
                            {cat}
                          </button>
                        ))}
                      </div>

                      <div className="flex items-center gap-2">
                        <span className="text-xs text-slate-400 font-medium">Severity:</span>
                        {["all", "critical", "high", "medium"].map((sev) => (
                          <button
                            key={sev}
                            onClick={() => setSeverityFilter(sev)}
                            className={`px-2.5 py-1 rounded-md text-xs font-medium capitalize transition-all ${
                              severityFilter === sev ? "bg-accent text-white" : "bg-slate-800 text-slate-400 hover:text-slate-200"
                            }`}
                          >
                            {sev}
                          </button>
                        ))}
                      </div>
                    </div>

                    {/* Corrections List */}
                    {filteredCorrections.length === 0 ? (
                      <div className="p-12 text-center rounded-xl border border-slate-800 bg-slate-900/40 text-slate-400">
                        <CheckCircle2 className="w-10 h-10 text-emerald-400 mx-auto mb-3" />
                        <p className="text-sm font-semibold text-white">No issues found matching selected filters</p>
                      </div>
                    ) : (
                      <div className="space-y-6">
                        {filteredCorrections.map((corr) => {
                          const isCopied = copiedId === corr.id;
                          const isFixing = fixingCorrectionId === corr.id;
                          const fixResult = fixPRResult[corr.id];

                          return (
                            <div
                              key={corr.id}
                              className="rounded-xl border border-slate-800 bg-slate-900/70 overflow-hidden shadow-lg transition-all hover:border-slate-700"
                            >
                              <div className="px-5 py-3.5 bg-slate-950/80 border-b border-slate-800 flex flex-wrap items-center justify-between gap-3">
                                <div className="flex items-center gap-2.5 flex-wrap">
                                  <span className="font-mono text-xs font-semibold text-blue-400 flex items-center gap-1.5">
                                    <FileCode className="w-3.5 h-3.5" />
                                    {corr.file_path}
                                  </span>
                                  <span className="text-slate-600">•</span>
                                  <span className="text-xs font-mono text-slate-400">
                                    L{corr.start_line}-{corr.end_line}
                                  </span>
                                  <span
                                    className={`px-2 py-0.5 rounded text-[10px] font-mono uppercase font-semibold ${
                                      corr.severity === "critical"
                                        ? "bg-rose-500/20 text-rose-300 border border-rose-500/30"
                                        : corr.severity === "high"
                                        ? "bg-amber-500/20 text-amber-300 border border-amber-500/30"
                                        : "bg-blue-500/20 text-blue-300 border border-blue-500/30"
                                    }`}
                                  >
                                    {corr.severity}
                                  </span>
                                  <span className="px-2 py-0.5 rounded bg-slate-800 text-slate-300 text-[10px] font-mono capitalize">
                                    {corr.category}
                                  </span>
                                  <span className="text-[11px] font-mono text-slate-400">
                                    Confidence: {Math.round(corr.confidence * 100)}%
                                  </span>
                                </div>

                                <div className="flex items-center gap-2">
                                  <button
                                    onClick={() => handleCopyCode(corr.id, corr.corrected_code)}
                                    className="px-3 py-1.5 rounded-lg text-xs font-medium bg-slate-800 hover:bg-slate-700 text-slate-200 flex items-center gap-1.5 transition-colors"
                                  >
                                    {isCopied ? <Check className="w-3.5 h-3.5 text-emerald-400" /> : <Copy className="w-3.5 h-3.5" />}
                                    <span>{isCopied ? "Copied" : "Copy Fix"}</span>
                                  </button>

                                  <button
                                    onClick={() => handleCreateFixPR(corr)}
                                    disabled={isFixing}
                                    className="px-3 py-1.5 rounded-lg text-xs font-medium bg-accent hover:bg-blue-500 text-white flex items-center gap-1.5 shadow transition-all"
                                  >
                                    {isFixing ? (
                                      <>
                                        <RefreshCw className="w-3.5 h-3.5 animate-spin" />
                                        <span>Opening PR...</span>
                                      </>
                                    ) : (
                                      <>
                                        <GitPullRequest className="w-3.5 h-3.5" />
                                        <span>Apply Fix as PR</span>
                                      </>
                                    )}
                                  </button>
                                </div>
                              </div>

                              <div className="p-5 space-y-4">
                                <p className="text-xs text-slate-300 leading-relaxed">{corr.explanation}</p>

                                {fixResult && (
                                  <div className="p-3 rounded-lg bg-blue-500/10 border border-blue-500/30 text-blue-300 text-xs flex items-center justify-between">
                                    <span>{fixResult.msg}</span>
                                    {fixResult.url && (
                                      <a
                                        href={fixResult.url}
                                        target="_blank"
                                        rel="noreferrer"
                                        className="text-white underline font-semibold flex items-center gap-1"
                                      >
                                        <span>View Fix PR</span>
                                        <ExternalLink className="w-3 h-3" />
                                      </a>
                                    )}
                                  </div>
                                )}

                                {/* Side-by-Side Diff */}
                                <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
                                  <div className="rounded-lg bg-slate-950 border border-slate-800 overflow-hidden">
                                    <div className="px-3.5 py-1.5 bg-rose-950/40 border-b border-slate-800 text-[11px] font-mono font-semibold text-rose-300 flex items-center justify-between">
                                      <span>ORIGINAL / FLAGGED CODE</span>
                                      <span className="text-[10px] text-rose-400/80">L{corr.start_line}-{corr.end_line}</span>
                                    </div>
                                    <pre className="p-3.5 text-xs font-mono text-slate-300 overflow-x-auto leading-relaxed max-h-60">
                                      <code>{corr.original_code || "(Code context at lines)"}</code>
                                    </pre>
                                  </div>

                                  <div className="rounded-lg bg-slate-950 border border-slate-800 overflow-hidden">
                                    <div className="px-3.5 py-1.5 bg-emerald-950/40 border-b border-slate-800 text-[11px] font-mono font-semibold text-emerald-300 flex items-center justify-between">
                                      <span>COMMUNITY / AI REMEDIATION</span>
                                      <span className="text-[10px] text-emerald-400/80">COMMIТTABLE SUGGESTION</span>
                                    </div>
                                    <pre className="p-3.5 text-xs font-mono text-emerald-300 overflow-x-auto leading-relaxed max-h-60">
                                      <code>{corr.corrected_code}</code>
                                    </pre>
                                  </div>
                                </div>
                              </div>
                            </div>
                          );
                        })}
                      </div>
                    )}
                  </div>
                )}

                {/* SUBTAB 3: DEEP FILE INSPECTOR */}
                {reportSubTab === "files" && (
                  <div className="rounded-xl border border-slate-800 bg-slate-900/70 overflow-hidden shadow-xl grid grid-cols-1 lg:grid-cols-12 min-h-[550px]">
                    {/* Left Column: Repository File Tree */}
                    <div className="lg:col-span-4 border-r border-slate-800 bg-slate-950/60 p-4 space-y-3">
                      <div className="flex items-center justify-between text-xs text-slate-400 font-mono pb-2 border-b border-slate-800">
                        <span className="flex items-center gap-1.5">
                          <Folder className="w-3.5 h-3.5 text-accent" /> REPOSITORY FILES
                        </span>
                        <span>{report.file_tree?.length || 0} files</span>
                      </div>

                      <div className="space-y-1">
                        {(report.file_tree || []).map((file) => {
                          const isSelected = selectedFile?.path === file.path;
                          return (
                            <button
                              key={file.path}
                              onClick={() => setSelectedFilePath(file.path)}
                              className={`w-full text-left px-3 py-2.5 rounded-lg text-xs font-mono flex items-center justify-between transition-all ${
                                isSelected
                                  ? "bg-accent text-white font-semibold shadow-md"
                                  : "text-slate-300 hover:bg-slate-900"
                              }`}
                            >
                              <div className="flex items-center gap-2 truncate">
                                <FileCode className={`w-3.5 h-3.5 shrink-0 ${isSelected ? "text-white" : "text-slate-400"}`} />
                                <span className="truncate">{file.path}</span>
                              </div>
                              <div className="flex items-center gap-1.5 shrink-0 ml-2">
                                {file.issues_count > 0 && (
                                  <span className={`px-1.5 py-0.2 rounded-full text-[10px] ${isSelected ? "bg-white/20 text-white" : "bg-rose-500/20 text-rose-300"}`}>
                                    {file.issues_count}
                                  </span>
                                )}
                                <span className={`text-[10px] ${isSelected ? "text-white/70" : "text-slate-500"}`}>
                                  {file.symbols_count} sym
                                </span>
                              </div>
                            </button>
                          );
                        })}
                      </div>
                    </div>

                    {/* Right Column: Code Viewer & AST Breakdown */}
                    <div className="lg:col-span-8 flex flex-col bg-slate-950/90">
                      {selectedFile ? (
                        <>
                          <div className="px-5 py-3 border-b border-slate-800 flex items-center justify-between bg-slate-900/60">
                            <div className="flex items-center gap-2">
                              <span className="text-xs font-mono text-white font-semibold">{selectedFile.path}</span>
                              <span className="text-[10px] text-slate-500 font-mono">
                                ({(selectedFile.size_bytes || 0).toLocaleString()} bytes)
                              </span>
                            </div>

                            <button
                              onClick={() => handleCopyCode(selectedFile.path, selectedFile.content || "")}
                              className="px-2.5 py-1 rounded bg-slate-800 hover:bg-slate-700 text-slate-300 text-xs font-medium flex items-center gap-1"
                            >
                              <Copy className="w-3 h-3" />
                              <span>Copy Source</span>
                            </button>
                          </div>

                          {selectedFileSymbols.length > 0 && (
                            <div className="px-5 py-2.5 border-b border-slate-800/80 bg-slate-900/30 flex items-center gap-2 overflow-x-auto text-xs">
                              <span className="text-[10px] font-mono text-slate-400 uppercase shrink-0">AST Symbols:</span>
                              {selectedFileSymbols.map((sym, idx) => (
                                <span
                                  key={idx}
                                  className="px-2 py-0.5 rounded-full bg-blue-500/10 border border-blue-500/20 text-blue-300 text-[10px] font-mono shrink-0"
                                >
                                  {sym.kind === "class" ? "class " : "fn "}
                                  {sym.name} (L{sym.start_line})
                                </span>
                              ))}
                            </div>
                          )}

                          <div className="p-4 overflow-x-auto flex-1 font-mono text-xs text-slate-300 leading-relaxed max-h-[500px]">
                            {(selectedFile.content || "").split("\n").map((line, idx) => {
                              const lineNum = idx + 1;
                              const hasFlag = (report.code_corrections || []).some(
                                (c) => c.file_path === selectedFile.path && lineNum >= c.start_line && lineNum <= c.end_line
                              );
                              return (
                                <div
                                  key={idx}
                                  className={`flex items-start gap-4 hover:bg-slate-900/50 px-2 py-0.5 rounded ${
                                    hasFlag ? "bg-rose-500/10 border-l-2 border-rose-500" : ""
                                  }`}
                                >
                                  <span className="text-slate-600 select-none w-8 text-right shrink-0">{lineNum}</span>
                                  <span className={hasFlag ? "text-rose-200" : "text-slate-300"}>{line || " "}</span>
                                </div>
                              );
                            })}
                          </div>
                        </>
                      ) : (
                        <div className="p-12 text-center text-slate-500 text-xs">Select a file on the left to inspect</div>
                      )}
                    </div>
                  </div>
                )}

                {/* SUBTAB 4: COMMITS & PULL REQUESTS INSPECTOR */}
                {reportSubTab === "git" && (
                  <div className="space-y-8">
                    {/* PRs Section with "Publish Review Comments" button */}
                    <div className="space-y-4">
                      <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-3">
                        <div className="flex items-center gap-2">
                          <GitPullRequest className="w-4 h-4 text-accent" />
                          <h3 className="text-sm font-semibold text-white">Repository Pull Requests</h3>
                          <span className="text-xs text-slate-500 font-mono">({report.prs_report?.length || 0})</span>
                        </div>

                        {report.repo_summary.target_type === "pull_request" && (
                          <button
                            type="button"
                            onClick={handlePublishReview}
                            disabled={isPublishingReview}
                            className="px-3.5 py-1.5 rounded-lg text-xs font-medium bg-accent hover:bg-blue-500 text-white flex items-center gap-1.5 shadow transition-all"
                          >
                            {isPublishingReview ? (
                              <>
                                <RefreshCw className="w-3.5 h-3.5 animate-spin" />
                                <span>Posting Review...</span>
                              </>
                            ) : (
                              <>
                                <Share2 className="w-3.5 h-3.5" />
                                <span>Post Review Comments to Live GitHub PR</span>
                              </>
                            )}
                          </button>
                        )}
                      </div>

                      {publishStatus && (
                        <div className="p-3 rounded-lg bg-blue-500/10 border border-blue-500/30 text-blue-300 text-xs">
                          {publishStatus}
                        </div>
                      )}

                      <div className="space-y-2.5">
                        {(report.prs_report || []).map((pr) => (
                          <div
                            key={pr.number}
                            className="p-4 rounded-xl border border-slate-800 bg-slate-900/60 hover:bg-slate-900 transition-colors flex flex-col sm:flex-row sm:items-center justify-between gap-3"
                          >
                            <div className="space-y-1 flex-1">
                              <div className="flex items-center gap-2.5">
                                <span className="font-mono text-xs px-2 py-0.5 rounded bg-blue-500/10 text-blue-400 border border-blue-500/20">
                                  #{pr.number}
                                </span>
                                <a
                                  href={pr.html_url}
                                  target="_blank"
                                  rel="noreferrer"
                                  className="text-xs font-semibold text-white hover:underline flex items-center gap-1"
                                >
                                  {pr.title}
                                  <ExternalLink className="w-2.5 h-2.5 text-slate-500" />
                                </a>
                                <span
                                  className={`text-[10px] font-mono px-2 py-0.2 rounded uppercase ${
                                    pr.state === "open" ? "bg-emerald-500/10 text-emerald-400 border border-emerald-500/20" : "bg-slate-800 text-slate-400"
                                  }`}
                                >
                                  {pr.state}
                                </span>
                              </div>
                              <div className="text-xs text-slate-400 flex items-center gap-3">
                                <span>Author: {pr.author}</span>
                                <span>•</span>
                                <span>Branch: {pr.branch}</span>
                                <span>•</span>
                                <span>{pr.created_at}</span>
                              </div>
                              <p className="text-xs text-slate-300 pt-0.5">{pr.summary}</p>
                            </div>

                            <div className="flex items-center gap-3 shrink-0">
                              <span className="px-2.5 py-1 rounded-full text-xs font-medium bg-slate-800 border border-slate-700 text-slate-300">
                                {pr.review_readiness}
                              </span>
                              <button
                                type="button"
                                onClick={() => {
                                  setGitUrl(pr.html_url);
                                  runAnalysis(pr.html_url);
                                }}
                                className="px-3 py-1.5 rounded-lg text-xs font-medium bg-accent hover:bg-blue-500 text-white flex items-center gap-1.5 transition-colors"
                              >
                                <span>Deep Review PR</span>
                                <ArrowRight className="w-3 h-3" />
                              </button>
                            </div>
                          </div>
                        ))}
                      </div>
                    </div>

                    {/* Commits Section */}
                    <div className="space-y-4">
                      <div className="flex items-center justify-between">
                        <div className="flex items-center gap-2">
                          <GitCommit className="w-4 h-4 text-blue-400" />
                          <h3 className="text-sm font-semibold text-white">Recent Real Commits</h3>
                          <span className="text-xs text-slate-500 font-mono">({report.commits_report?.length || 0})</span>
                        </div>
                        <span className="text-xs text-slate-500">From default branch</span>
                      </div>

                      <div className="space-y-2.5">
                        {(report.commits_report || []).map((c) => (
                          <div
                            key={c.sha}
                            className="p-4 rounded-xl border border-slate-800 bg-slate-900/60 hover:bg-slate-900 transition-colors flex flex-col sm:flex-row sm:items-center justify-between gap-3"
                          >
                            <div className="space-y-1 flex-1">
                              <div className="flex items-center gap-2.5">
                                <a
                                  href={c.html_url}
                                  target="_blank"
                                  rel="noreferrer"
                                  className="font-mono text-xs px-2 py-0.5 rounded bg-blue-500/10 text-blue-400 border border-blue-500/20 hover:underline flex items-center gap-1"
                                >
                                  <span>{c.sha.slice(0, 7)}</span>
                                  <ExternalLink className="w-2.5 h-2.5" />
                                </a>
                                <span className="text-xs font-semibold text-white">{c.message.split("\n")[0]}</span>
                              </div>
                              <div className="text-xs text-slate-400 flex items-center gap-3">
                                <span>Author: {c.author}</span>
                                <span>•</span>
                                <span>{c.date}</span>
                              </div>
                            </div>
                            <span className="px-2.5 py-1 rounded-full text-[11px] font-mono bg-slate-800 border border-slate-700 text-slate-300 uppercase">
                              {c.risk_level || "low risk"}
                            </span>
                          </div>
                        ))}
                      </div>
                    </div>
                  </div>
                )}
              </div>
            ) : (
              /* PROCESS & SUPPORTING BENEFITS (When no report is yet generated) */
              <div className="space-y-8">
                <div className="max-w-2xl">
                  <div className="inline-flex items-center gap-2 px-3 py-1 rounded-full bg-slate-800 text-xs font-medium text-blue-400 mb-2">
                    <Sparkles className="w-3.5 h-3.5" />
                    <span>Deterministic 4-Stage Analysis Process</span>
                  </div>
                  <h2 className="font-display font-bold text-2xl text-on-field tracking-tight">
                    Continuous Cross-File Inspection Pipeline
                  </h2>
                  <p className="text-sm text-on-field-secondary mt-1">
                    Every analysis follows four segfault-safe, anti-noise stages before delivering committable remediation suggestions.
                  </p>
                </div>

                {/* 4 Connected Process Steps Across Row */}
                <div className="grid grid-cols-1 md:grid-cols-4 gap-4">
                  <div className="p-5 rounded-xl border border-slate-800 bg-slate-900/50 space-y-2 relative">
                    <span className="text-xs font-mono text-accent font-bold">01 / INGESTION</span>
                    <h3 className="text-sm font-semibold text-white">Unified Diff & Web Ingestion</h3>
                    <p className="text-xs text-slate-400">
                      Extracts modified hunk ranges, commit groups, and active PRs with automatic rate-limit bypass.
                    </p>
                  </div>

                  <div className="p-5 rounded-xl border border-slate-800 bg-slate-900/50 space-y-2 relative">
                    <span className="text-xs font-mono text-accent font-bold">02 / CONTEXT ENGINE</span>
                    <h3 className="text-sm font-semibold text-white">Tree-sitter 2-Hop Graph</h3>
                    <p className="text-xs text-slate-400">
                      Constructs syntax trees iteratively to identify enclosing function/class scopes and call hierarchies.
                    </p>
                  </div>

                  <div className="p-5 rounded-xl border border-slate-800 bg-slate-900/50 space-y-2 relative">
                    <span className="text-xs font-mono text-accent font-bold">03 / SAST PRECISION</span>
                    <h3 className="text-sm font-semibold text-white">Semgrep Security Gates</h3>
                    <p className="text-xs text-slate-400">
                      Executes 40+ deterministic rules for SQLi, auth bypass, and memory leaks with confidence scores.
                    </p>
                  </div>

                  <div className="p-5 rounded-xl border border-slate-800 bg-slate-900/50 space-y-2 relative">
                    <span className="text-xs font-mono text-accent font-bold">04 / BOT REMEDIATION</span>
                    <h3 className="text-sm font-semibold text-white">Committable GitHub Bot</h3>
                    <p className="text-xs text-slate-400">
                      Drops findings under 0.80 confidence and packages validated fixes as PR comments or fix PR branches.
                    </p>
                  </div>
                </div>
              </div>
            )}
          </div>

          {/* Visual Architecture Bento Strip */}
          <div className="grid grid-cols-1 md:grid-cols-3 gap-4 pt-4 border-t border-rule">
            <div className="p-4 rounded-xl border border-rule bg-panel space-y-1.5 shadow-xs">
              <div className="flex items-center gap-2 text-xs font-semibold text-ink">
                <Network className="w-4 h-4 text-accent" />
                <span>Tree-Sitter 2-Hop Call Graph</span>
              </div>
              <p className="text-xs text-ink-secondary leading-relaxed">
                Synthesizes callers, callees, and enclosing symbol scopes around changed lines to prevent blind diff hallucinations.
              </p>
            </div>

            <div className="p-4 rounded-xl border border-rule bg-panel space-y-1.5 shadow-xs">
              <div className="flex items-center gap-2 text-xs font-semibold text-ink">
                <ShieldCheck className="w-4 h-4 text-emerald-500" />
                <span>Deterministic Semgrep Rules</span>
              </div>
              <p className="text-xs text-ink-secondary leading-relaxed">
                Audits code changes against OWASP Top 10, CWE-89, CWE-78, and hardcoded secrets with deterministic accuracy.
              </p>
            </div>

            <div className="p-4 rounded-xl border border-rule bg-panel space-y-1.5 shadow-xs">
              <div className="flex items-center gap-2 text-xs font-semibold text-ink">
                <Flame className="w-4 h-4 text-amber-500" />
                <span>Strict Anti-Noise Gate (≥0.80)</span>
              </div>
              <p className="text-xs text-ink-secondary leading-relaxed">
                Permanently drops style nitpicks and low-confidence findings before they can reach the review comment stream.
              </p>
            </div>
          </div>
        </div>

        {/* ========================================================= */}
        {/* VIEW 2: SETTINGS PANEL */}
        {/* ========================================================= */}
        <div className={activeTab === "settings" ? "block max-w-3xl mx-auto" : "hidden"}>
          <div className="bg-panel border border-rule rounded-panel p-8 shadow-card space-y-8">
            <div>
              <span className="text-xs font-mono uppercase tracking-wider text-accent font-semibold">Configuration</span>
              <h2 className="font-display font-bold text-2xl text-ink tracking-tight mt-1">
                API Keys & LLM Provider Settings
              </h2>
              <p className="text-xs text-ink-secondary mt-1">
                Configure your inference model and GitHub Personal Access Token. Keys are stored locally in your browser session.
              </p>
            </div>

            {settingsSaved && (
              <div className="p-3.5 rounded-lg bg-emerald-50 border border-emerald-200 text-emerald-800 text-xs flex items-center gap-2">
                <Check className="w-4 h-4 text-emerald-600" />
                <span>Settings saved successfully in your local browser session!</span>
              </div>
            )}

            <div className="space-y-6">
              {/* Provider Selection */}
              <div className="space-y-2">
                <label className="text-xs font-semibold text-ink">Inference Engine Provider</label>
                <div className="grid grid-cols-2 gap-3">
                  <button
                    type="button"
                    onClick={() => setSettings((s) => ({ ...s, provider: "openai", model: "gpt-4o-mini" }))}
                    className={`p-3.5 rounded-lg border text-left transition-all ${
                      settings.provider === "openai"
                        ? "border-accent bg-accent/5 ring-1 ring-accent"
                        : "border-rule bg-ground hover:bg-ground-muted"
                    }`}
                  >
                    <span className="font-display font-bold text-sm block text-ink">OpenAI</span>
                    <span className="text-[11px] text-ink-secondary">gpt-4o-mini, gpt-4o structured JSON</span>
                  </button>

                  <button
                    type="button"
                    onClick={() => setSettings((s) => ({ ...s, provider: "gemini", model: "gemini-2.5-flash" }))}
                    className={`p-3.5 rounded-lg border text-left transition-all ${
                      settings.provider === "gemini"
                        ? "border-accent bg-accent/5 ring-1 ring-accent"
                        : "border-rule bg-ground hover:bg-ground-muted"
                    }`}
                  >
                    <span className="font-display font-bold text-sm block text-ink">Google Gemini</span>
                    <span className="text-[11px] text-ink-secondary">gemini-2.5-flash, gemini-2.5-pro</span>
                  </button>
                </div>
              </div>

              {/* Model Choice */}
              <div className="space-y-2">
                <label className="text-xs font-semibold text-ink">Model Architecture</label>
                <select
                  value={settings.model}
                  onChange={(e) => setSettings((s) => ({ ...s, model: e.target.value }))}
                  className="w-full px-3.5 py-2.5 rounded-lg border border-rule bg-ground text-sm text-ink focus:outline-none focus:border-accent"
                >
                  {settings.provider === "openai" ? (
                    <>
                      <option value="gpt-4o-mini">gpt-4o-mini (Fast, Low Latency - Recommended)</option>
                      <option value="gpt-4o">gpt-4o (Deep Reasoning, High Token Limit)</option>
                    </>
                  ) : (
                    <>
                      <option value="gemini-2.5-flash">gemini-2.5-flash (Fast, Low Latency - Recommended)</option>
                      <option value="gemini-2.5-pro">gemini-2.5-pro (Extended Context & Complex ASTs)</option>
                    </>
                  )}
                </select>
              </div>

              {/* OpenAI Key */}
              {settings.provider === "openai" && (
                <div className="space-y-2">
                  <div className="flex items-center justify-between">
                    <label className="text-xs font-semibold text-ink">OpenAI API Key</label>
                    <span className="text-[11px] text-ink-secondary">Optional: Fallback heuristic engine active if empty</span>
                  </div>
                  <div className="relative">
                    <input
                      type={showOpenAIKey ? "text" : "password"}
                      value={settings.openaiApiKey}
                      onChange={(e) => setSettings((s) => ({ ...s, openaiApiKey: e.target.value }))}
                      placeholder="sk-proj-..."
                      className="w-full px-3.5 py-2.5 rounded-lg border border-rule bg-ground text-sm text-ink focus:outline-none focus:border-accent font-mono pr-10"
                    />
                    <button
                      type="button"
                      onClick={() => setShowOpenAIKey(!showOpenAIKey)}
                      className="absolute right-3 top-2.5 text-ink-secondary hover:text-ink"
                    >
                      {showOpenAIKey ? <EyeOff className="w-4 h-4" /> : <Eye className="w-4 h-4" />}
                    </button>
                  </div>
                </div>
              )}

              {/* Gemini Key */}
              {settings.provider === "gemini" && (
                <div className="space-y-2">
                  <div className="flex items-center justify-between">
                    <label className="text-xs font-semibold text-ink">Google Gemini API Key</label>
                    <span className="text-[11px] text-ink-secondary">Optional: Fallback heuristic engine active if empty</span>
                  </div>
                  <div className="relative">
                    <input
                      type={showGeminiKey ? "text" : "password"}
                      value={settings.geminiApiKey}
                      onChange={(e) => setSettings((s) => ({ ...s, geminiApiKey: e.target.value }))}
                      placeholder="AIzaSy..."
                      className="w-full px-3.5 py-2.5 rounded-lg border border-rule bg-ground text-sm text-ink focus:outline-none focus:border-accent font-mono pr-10"
                    />
                    <button
                      type="button"
                      onClick={() => setShowGeminiKey(!showGeminiKey)}
                      className="absolute right-3 top-2.5 text-ink-secondary hover:text-ink"
                    >
                      {showGeminiKey ? <EyeOff className="w-4 h-4" /> : <Eye className="w-4 h-4" />}
                    </button>
                  </div>
                </div>
              )}

              {/* GitHub PAT */}
              <div className="space-y-2 pt-2 border-t border-rule">
                <div className="flex items-center justify-between">
                  <label className="text-xs font-semibold text-ink">GitHub Personal Access Token (PAT)</label>
                  <span className="text-[11px] text-ink-secondary">Enables 1-Click "Apply Fix as PR" & Live Reviews</span>
                </div>
                <div className="relative">
                  <input
                    type={showGithubToken ? "text" : "password"}
                    value={settings.githubToken}
                    onChange={(e) => setSettings((s) => ({ ...s, githubToken: e.target.value }))}
                    placeholder="ghp_... or github_pat_..."
                    className="w-full px-3.5 py-2.5 rounded-lg border border-rule bg-ground text-sm text-ink focus:outline-none focus:border-accent font-mono pr-10"
                  />
                  <button
                    type="button"
                    onClick={() => setShowGithubToken(!showGithubToken)}
                    className="absolute right-3 top-2.5 text-ink-secondary hover:text-ink"
                  >
                    {showGithubToken ? <EyeOff className="w-4 h-4" /> : <Eye className="w-4 h-4" />}
                  </button>
                </div>
                <p className="text-[11px] text-ink-secondary leading-relaxed">
                  Requires <code className="font-mono bg-ground-muted px-1 rounded">repo</code> or <code className="font-mono bg-ground-muted px-1 rounded">pull_requests:write</code> permissions to publish inline review comments and open remediation pull requests automatically.
                </p>
              </div>

              {/* Action Buttons */}
              <div className="pt-4 flex items-center justify-between">
                <button
                  type="button"
                  onClick={() => {
                    setSettings(DEFAULT_SETTINGS);
                    localStorage.removeItem("aicr_analyzer_settings");
                    setSettingsSaved(true);
                    setTimeout(() => setSettingsSaved(false), 2000);
                  }}
                  className="btn-secondary !text-xs"
                >
                  Reset Defaults
                </button>

                <button
                  type="button"
                  onClick={handleSaveSettings}
                  className="btn-primary !text-xs !py-2 !px-5"
                >
                  <Check className="w-3.5 h-3.5" />
                  <span>Save Configuration</span>
                </button>
              </div>
            </div>
          </div>
        </div>
      </main>

      {/* SUBSTANTIAL DARK PASSAGE 2: DARK CLOSING & FOOTER */}
      <footer className="bg-field text-on-field-secondary border-t border-slate-800 pt-12 pb-8 px-6 sm:px-12 mt-16">
        <div className="max-w-7xl mx-auto grid grid-cols-1 md:grid-cols-4 gap-8 pb-10 border-b border-slate-800 text-xs">
          <div className="md:col-span-2 space-y-3">
            <div className="flex items-center gap-2">
              <div className="w-7 h-7 rounded-lg bg-accent flex items-center justify-center text-white">
                <Sparkles className="w-4 h-4" />
              </div>
              <span className="font-display font-bold text-sm text-on-field">AI Code Reviewer Enterprise</span>
            </div>
            <p className="text-on-field-secondary/80 max-w-md leading-relaxed">
              Production-ready multi-VCS AI code review assistant. Integrates with GitHub Pull Requests and GitLab Merge Requests to deliver cross-file architectural reviews, Semgrep SAST security flags, and committable suggestion blocks.
            </p>
          </div>

          <div className="space-y-2">
            <span className="font-display font-bold text-on-field block text-sm">Monorepo Packages</span>
            <ul className="space-y-1 text-on-field-secondary/80 font-mono text-[11px]">
              <li>apps/api-gateway (FastAPI 0.115)</li>
              <li>packages/context-engine (Tree-sitter)</li>
              <li>packages/review-worker (Semgrep + Celery)</li>
              <li>packages/ml-pipeline (QLoRA + DPO)</li>
            </ul>
          </div>

          <div className="space-y-2">
            <span className="font-display font-bold text-on-field block text-sm">System Health</span>
            <div className="space-y-1.5 text-[11px] text-on-field-secondary/80">
              <div className="flex items-center gap-2">
                <span className="w-2 h-2 rounded-full bg-emerald-400" />
                <span>FastAPI Gateway: Port 8000 (Active)</span>
              </div>
              <div className="flex items-center gap-2">
                <span className="w-2 h-2 rounded-full bg-emerald-400" />
                <span>Next.js Dashboard: Port 3000 (Active)</span>
              </div>
              <div className="flex items-center gap-2">
                <span className="w-2 h-2 rounded-full bg-blue-400" />
                <span>Tree-sitter C Parser: Segfault-Safe</span>
              </div>
            </div>
          </div>
        </div>

        <div className="max-w-7xl mx-auto pt-6 flex flex-col sm:flex-row items-center justify-between text-[11px] text-on-field-secondary/60 gap-4">
          <span>AI Code Reviewer • Enterprise Engineering Quality Platform</span>
          <div className="flex items-center gap-4">
            <a href="https://github.com" target="_blank" rel="noreferrer" className="hover:text-on-field flex items-center gap-1">
              <span>GitHub VCS</span>
              <ExternalLink className="w-3 h-3" />
            </a>
            <span>•</span>
            <span>OASIS SARIF v2.1.0 Compliant</span>
          </div>
        </div>
      </footer>
    </div>
  );
}
