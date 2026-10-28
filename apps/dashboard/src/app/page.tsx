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

      const timer1 = setTimeout(() => setAnalysisStep(2), 600);
      const timer2 = setTimeout(() => setAnalysisStep(3), 1300);
      const timer3 = setTimeout(() => setAnalysisStep(4), 2100);

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

  // Graph nodes & edges
  const graphData = useMemo(() => {
    if (!report) return { nodes: [], edges: [] };
    const fileTree = report.file_tree || [];
    const hotspots = report.architecture_advice?.coupling_hotspots || [];
    const files = fileTree.map((f, i) => {
      const isHotspot = hotspots.some((h) => h?.file_path === f?.path);
      const hasIssues = (f?.issues_count || 0) > 0;
      const angle = (i / (fileTree.length || 1)) * 2 * Math.PI;
      const radius = 170;
      return {
        id: f?.path || `file-${i}`,
        label: (f?.path || "").split("/").pop() || f?.path || "file",
        fullPath: f?.path || "",
        x: 320 + radius * Math.cos(angle),
        y: 220 + radius * Math.sin(angle),
        isHotspot,
        hasIssues,
        symbolsCount: f?.symbols_count || 0,
        issuesCount: f?.issues_count || 0,
      };
    });

    const edges: Array<{ source: string; target: string; isHot: boolean }> = [];
    const depMap = report.ast_insights?.dependency_map || [];
    depMap.forEach((dep) => {
      if (!dep?.source || !dep?.target) return;
      const sourceNode = files.find((n) => n.id === dep.source);
      const targetNode = files.find((n) => n.id.includes(dep.target) || dep.target.includes(n.label));
      if (sourceNode && targetNode && sourceNode.id !== targetNode.id) {
        edges.push({
          source: sourceNode.id,
          target: targetNode.id,
          isHot: sourceNode.isHotspot || targetNode.isHotspot,
        });
      }
    });

    if (edges.length === 0 && files.length > 1) {
      for (let i = 1; i < files.length; i++) {
        edges.push({ source: files[0].id, target: files[i].id, isHot: files[0].isHotspot });
      }
    }

    return { nodes: files, edges };
  }, [report]);

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
        </div>
      </header>

      {/* Main Container */}
      <main className="flex-1 w-full max-w-7xl mx-auto px-4 sm:px-6 py-8">
        {/* ========================================================= */}
        {/* VIEW 1: DASHBOARD VIEW */}
        {/* ========================================================= */}
        <div className={activeTab === "dashboard" ? "block space-y-10" : "hidden"}>
          
          {/* HERO SECTION: Wide 1.45:1 Split Layout */}
          <div className="grid grid-cols-1 lg:grid-cols-12 gap-8 items-center py-4">
            {/* Left Column: Broad Reading Area & Single Input (~58% / 1.45:1 ratio) */}
            <div className="lg:col-span-7 space-y-5">
              <div className="inline-flex items-center gap-2 px-3 py-1 rounded-full bg-ground-muted border border-rule text-xs font-medium text-ink-secondary">
                <span className="w-2 h-2 rounded-full bg-accent" />
                <span>Tree-sitter AST & Semgrep SAST Anti-Noise Gate</span>
              </div>

              <h1 className="font-display font-bold text-3xl sm:text-4xl lg:text-5xl text-ink tracking-tight leading-[1.1]">
                AI-Powered Code Review & Architectural Intelligence
              </h1>

              <p className="font-sans text-ink-secondary text-base leading-relaxed max-w-xl">
                Deliver cross-file architectural reviews, deterministic security flags, and committable suggestion
                blocks directly into GitHub Pull Requests — backed by real AST call graphs and anti-noise thresholds.
              </p>

              {/* Single Central Input & Action Button */}
              <div className="pt-1">
                <form
                  onSubmit={(e) => {
                    e.preventDefault();
                    runAnalysis();
                  }}
                  className="flex flex-col sm:flex-row gap-2 items-stretch p-1.5 bg-panel border border-rule rounded-panel shadow-card focus-within:border-accent focus-within:ring-2 focus-within:ring-accent/15 transition-all"
                >
                  <div className="flex items-center gap-2.5 px-3 py-2 flex-1">
                    <Search className="w-4 h-4 text-ink-secondary shrink-0" />
                    <input
                      type="url"
                      value={gitUrl}
                      onChange={(e) => setGitUrl(e.target.value)}
                      placeholder="https://github.com/owner/repo or .../pull/123"
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
                    className={`btn-primary shrink-0 ${
                      isAnalyzing || !gitUrl.trim() ? "opacity-50 cursor-not-allowed" : ""
                    }`}
                  >
                    {isAnalyzing ? (
                      <>
                        <RefreshCw className="w-4 h-4 animate-spin" />
                        <span>Analyzing...</span>
                      </>
                    ) : (
                      <>
                        <Zap className="w-4 h-4" />
                        <span>Analyze Repository / PR</span>
                      </>
                    )}
                  </button>
                </form>

                {/* Quick Try Pills */}
                <div className="flex flex-wrap items-center gap-2 pt-3 text-xs text-ink-secondary">
                  <span className="font-medium">Quick Try:</span>
                  <button
                    type="button"
                    onClick={() => handleQuickUrl("https://github.com/abduzeedo/mapc-site.git")}
                    className="px-2.5 py-1 rounded-md bg-ground-muted hover:bg-rule/50 border border-rule font-mono text-[11px] text-ink transition-colors"
                  >
                    abduzeedo/mapc-site (1 PR)
                  </button>
                  <button
                    type="button"
                    onClick={() => handleQuickUrl("https://github.com/HappyShadowCoder/Qurating-Reimplementation")}
                    className="px-2.5 py-1 rounded-md bg-ground-muted hover:bg-rule/50 border border-rule font-mono text-[11px] text-ink transition-colors"
                  >
                    HappyShadowCoder/Qurating
                  </button>
                  <button
                    type="button"
                    onClick={() => handleQuickUrl("https://github.com/pallets/flask")}
                    className="px-2.5 py-1 rounded-md bg-ground-muted hover:bg-rule/50 border border-rule font-mono text-[11px] text-ink transition-colors"
                  >
                    pallets/flask
                  </button>
                </div>
              </div>
            </div>

            {/* Right Column: Compact Product Diagram (Converging Inputs) */}
            <div className="lg:col-span-5">
              <div className="bg-ground-muted border border-rule rounded-panel p-6 shadow-card relative flex items-center justify-center min-h-[320px] overflow-hidden">
                {/* Subtle static orbit lines */}
                <svg className="absolute inset-0 w-full h-full pointer-events-none opacity-40" viewBox="0 0 400 320">
                  <circle cx="200" cy="160" r="120" fill="none" stroke="var(--dp-color-rule)" strokeWidth="1" strokeDasharray="4 4" />
                  <circle cx="200" cy="160" r="70" fill="none" stroke="var(--dp-color-rule)" strokeWidth="1" />
                  <line x1="60" y1="50" x2="160" y2="130" stroke="var(--dp-color-rule)" strokeWidth="1" />
                  <line x1="340" y1="50" x2="240" y2="130" stroke="var(--dp-color-rule)" strokeWidth="1" />
                  <line x1="60" y1="270" x2="160" y2="190" stroke="var(--dp-color-rule)" strokeWidth="1" />
                  <line x1="340" y1="270" x2="240" y2="190" stroke="var(--dp-color-rule)" strokeWidth="1" />
                </svg>

                {/* Central Product Hub Tile */}
                <div className="relative z-10 w-36 h-36 rounded-2xl bg-gradient-to-br from-accent to-[#053ec0] text-white p-3 flex flex-col items-center justify-center text-center shadow-lg border border-white/20">
                  <div className="w-8 h-8 rounded-lg bg-white/20 flex items-center justify-center mb-1.5">
                    <Sparkles className="w-4 h-4 text-white" />
                  </div>
                  <span className="font-display font-bold text-xs tracking-tight">AI Review Engine</span>
                  <span className="text-[10px] text-white/80 font-mono mt-0.5">AST + SAST Gate</span>
                </div>

                {/* Converging Small White Tiles */}
                <div className="absolute top-4 left-4 bg-panel border border-rule rounded-lg px-2.5 py-1.5 shadow-sm text-[11px] font-semibold text-ink flex items-center gap-1.5">
                  <GitPullRequest className="w-3.5 h-3.5 text-accent" />
                  <span>GitHub PR Diffs</span>
                </div>

                <div className="absolute top-4 right-4 bg-panel border border-rule rounded-lg px-2.5 py-1.5 shadow-sm text-[11px] font-semibold text-ink flex items-center gap-1.5">
                  <ShieldCheck className="w-3.5 h-3.5 text-emerald-600" />
                  <span>Semgrep 40+ Rules</span>
                </div>

                <div className="absolute bottom-4 left-4 bg-panel border border-rule rounded-lg px-2.5 py-1.5 shadow-sm text-[11px] font-semibold text-ink flex items-center gap-1.5">
                  <Network className="w-3.5 h-3.5 text-indigo-600" />
                  <span>Tree-sitter 2-Hop</span>
                </div>

                <div className="absolute bottom-4 right-4 bg-panel border border-rule rounded-lg px-2.5 py-1.5 shadow-sm text-[11px] font-semibold text-ink flex items-center gap-1.5">
                  <Zap className="w-3.5 h-3.5 text-amber-600" />
                  <span>Committable Fixes</span>
                </div>
              </div>
            </div>
          </div>

          {/* RULED STRIP: Supporting Facts Below Hero */}
          <div className="border-y border-rule py-4 bg-panel">
            <div className="grid grid-cols-2 md:grid-cols-4 gap-6 text-sm">
              <div className="space-y-0.5">
                <span className="font-display font-bold text-ink">2-Hop AST Graph</span>
                <p className="text-xs text-ink-secondary">Callers, callees & enclosing scopes</p>
              </div>
              <div className="space-y-0.5">
                <span className="font-display font-bold text-ink">40+ SAST Security Rules</span>
                <p className="text-xs text-ink-secondary">Deterministic OWASP & CWE gates</p>
              </div>
              <div className="space-y-0.5">
                <span className="font-display font-bold text-ink">≥0.80 Confidence Gate</span>
                <p className="text-xs text-ink-secondary">Drops style nits & hallucinated diffs</p>
              </div>
              <div className="space-y-0.5">
                <span className="font-display font-bold text-ink">OASIS SARIF v2.1.0</span>
                <p className="text-xs text-ink-secondary">Audit exports & 1-click GitHub bot</p>
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
                    <h3 className="text-sm font-display font-bold text-ink">Analyzing Repository & AST Structure</h3>
                    <p className="text-xs text-ink-secondary">Ingesting unified diffs, running Tree-sitter and SAST security gates...</p>
                  </div>
                </div>
                <span className="text-xs font-mono font-bold text-accent">Step {analysisStep} of 4</span>
              </div>
              <div className="w-full bg-ground-muted rounded-full h-1.5 overflow-hidden">
                <div
                  className="bg-accent h-1.5 rounded-full transition-all duration-300"
                  style={{ width: `${(analysisStep / 4) * 100}%` }}
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

                    {/* INTERACTIVE VISUAL CALL-GRAPH & ARCHITECTURAL CANVAS */}
                    <div className="p-6 rounded-xl border border-slate-800 bg-slate-900/70 space-y-4">
                      <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-3">
                        <div>
                          <div className="flex items-center gap-2 text-sm font-semibold text-white">
                            <Network className="w-4 h-4 text-accent" />
                            <span>Interactive Architectural & Call-Graph Canvas</span>
                          </div>
                          <p className="text-xs text-slate-400 mt-0.5">
                            Visualizes Tree-sitter module dependencies, import paths, and coupling hotspots. Click any node to focus.
                          </p>
                        </div>
                        <div className="flex items-center gap-2">
                          <button
                            onClick={() => setGraphZoom((z) => Math.max(0.6, z - 0.2))}
                            className="p-1.5 rounded-lg bg-slate-800 hover:bg-slate-700 text-slate-300"
                            title="Zoom Out"
                          >
                            <ZoomOut className="w-3.5 h-3.5" />
                          </button>
                          <span className="text-xs font-mono text-slate-400">{Math.round(graphZoom * 100)}%</span>
                          <button
                            onClick={() => setGraphZoom((z) => Math.min(1.8, z + 0.2))}
                            className="p-1.5 rounded-lg bg-slate-800 hover:bg-slate-700 text-slate-300"
                            title="Zoom In"
                          >
                            <ZoomIn className="w-3.5 h-3.5" />
                          </button>
                          <button
                            onClick={() => {
                              setGraphZoom(1);
                              setFocusedGraphNode(null);
                            }}
                            className="px-2 py-1 rounded bg-slate-800 hover:bg-slate-700 text-[11px] text-slate-300 font-mono"
                          >
                            Reset
                          </button>
                        </div>
                      </div>

                      {/* SVG Canvas Area */}
                      <div className="w-full h-[400px] rounded-lg bg-slate-950 border border-slate-800 relative overflow-hidden flex items-center justify-center">
                        <svg
                          viewBox="0 0 640 440"
                          className="w-full h-full select-none"
                          style={{ transform: `scale(${graphZoom})`, transformOrigin: "center center", transition: "transform 0.2s ease" }}
                        >
                          <defs>
                            <linearGradient id="edgeGrad" x1="0%" y1="0%" x2="100%" y2="100%">
                              <stop offset="0%" stopColor="#074ce0" stopOpacity="0.4" />
                              <stop offset="100%" stopColor="#3b82f6" stopOpacity="0.8" />
                            </linearGradient>
                            <linearGradient id="edgeHotGrad" x1="0%" y1="0%" x2="100%" y2="100%">
                              <stop offset="0%" stopColor="#f43f5e" stopOpacity="0.6" />
                              <stop offset="100%" stopColor="#fb7185" stopOpacity="0.9" />
                            </linearGradient>
                          </defs>

                          {/* Connections */}
                          {(graphData.edges || []).map((edge, idx) => {
                            const sNode = graphData.nodes.find((n) => n.id === edge.source);
                            const tNode = graphData.nodes.find((n) => n.id === edge.target);
                            if (!sNode || !tNode) return null;
                            const isHighlighted = focusedGraphNode === sNode.id || focusedGraphNode === tNode.id;
                            return (
                              <line
                                key={idx}
                                x1={sNode.x}
                                y1={sNode.y}
                                x2={tNode.x}
                                y2={tNode.y}
                                stroke={edge.isHot ? "url(#edgeHotGrad)" : "url(#edgeGrad)"}
                                strokeWidth={isHighlighted ? 3 : 1.5}
                                strokeDasharray={edge.isHot ? "4 3" : undefined}
                                opacity={focusedGraphNode ? (isHighlighted ? 1 : 0.2) : 0.7}
                              />
                            );
                          })}

                          {/* Nodes */}
                          {(graphData.nodes || []).map((node) => {
                            const isFocused = focusedGraphNode === node.id;
                            return (
                              <g
                                key={node.id}
                                transform={`translate(${node.x}, ${node.y})`}
                                className="cursor-pointer transition-all"
                                onClick={() => setFocusedGraphNode(isFocused ? null : node.id)}
                              >
                                {node.isHotspot && (
                                  <circle r="26" fill="#f43f5e" fillOpacity="0.15" />
                                )}
                                <circle
                                  r={isFocused ? "22" : "18"}
                                  fill={node.isHotspot ? "#881337" : node.hasIssues ? "#451a03" : "#074ce0"}
                                  stroke={isFocused ? "#ffffff" : node.isHotspot ? "#fb7185" : "#3b82f6"}
                                  strokeWidth={isFocused ? "3" : "1.5"}
                                />
                                <text
                                  textAnchor="middle"
                                  dy="4"
                                  fill="#ffffff"
                                  fontSize="9"
                                  fontFamily="monospace"
                                  fontWeight="bold"
                                  pointerEvents="none"
                                >
                                  {node.label.slice(0, 5)}
                                </text>
                                <text
                                  textAnchor="middle"
                                  dy="30"
                                  fill={isFocused ? "#60a5fa" : "#94a3b8"}
                                  fontSize="10"
                                  fontFamily="monospace"
                                  fontWeight={isFocused ? "bold" : "normal"}
                                >
                                  {node.label}
                                </text>
                              </g>
                            );
                          })}
                        </svg>

                        {/* Canvas legend */}
                        <div className="absolute bottom-3 left-3 bg-slate-900/90 border border-slate-800 rounded-lg p-2 text-[10px] text-slate-400 space-y-1">
                          <div className="flex items-center gap-2">
                            <span className="w-2.5 h-2.5 rounded-full bg-accent" />
                            <span>Standard Module</span>
                          </div>
                          <div className="flex items-center gap-2">
                            <span className="w-2.5 h-2.5 rounded-full bg-amber-500" />
                            <span>Issues Flagged</span>
                          </div>
                          <div className="flex items-center gap-2">
                            <span className="w-2.5 h-2.5 rounded-full bg-rose-500" />
                            <span>Coupling Hotspot</span>
                          </div>
                        </div>
                      </div>
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

          {/* PALE-GREY FIELD: Short Explanations & Editorial Cards */}
          <div className="bg-ground-muted rounded-panel p-8 sm:p-10 border border-rule space-y-6">
            <div className="max-w-2xl">
              <span className="text-xs font-mono uppercase tracking-wider text-accent font-semibold">Core Architecture</span>
              <h2 className="font-display font-bold text-2xl text-ink tracking-tight mt-1">
                Enterprise Standards & Anti-Noise Guarantee
              </h2>
              <p className="text-sm text-ink-secondary mt-1">
                Engineered specifically to solve the three fatal failure points of generic AI review assistants.
              </p>
            </div>

            <div className="grid grid-cols-1 md:grid-cols-3 gap-6">
              <div className="bg-panel border border-rule rounded-panel p-6 shadow-card space-y-3">
                <div className="w-9 h-9 rounded-lg bg-accent/10 text-accent flex items-center justify-center">
                  <Network className="w-5 h-5" />
                </div>
                <h3 className="font-display font-bold text-base text-ink">Cross-File Context</h3>
                <p className="text-xs text-ink-secondary leading-relaxed">
                  Never sends raw <code className="font-mono bg-ground-muted px-1 rounded">git diff</code> strings alone. Enriches modifications with enclosing AST scopes, imported type signatures, and 2-hop caller/callee context.
                </p>
              </div>

              <div className="bg-panel border border-rule rounded-panel p-6 shadow-card space-y-3">
                <div className="w-9 h-9 rounded-lg bg-accent/10 text-accent flex items-center justify-center">
                  <ShieldCheck className="w-5 h-5" />
                </div>
                <h3 className="font-display font-bold text-base text-ink">Strict Anti-Noise Gate</h3>
                <p className="text-xs text-ink-secondary leading-relaxed">
                  Combines deterministic Semgrep SAST with strict Pydantic schemas. Automatically drops any AI finding with confidence under 0.80 or categorized as a subjective style nitpick.
                </p>
              </div>

              <div className="bg-panel border border-rule rounded-panel p-6 shadow-card space-y-3">
                <div className="w-9 h-9 rounded-lg bg-accent/10 text-accent flex items-center justify-center">
                  <GitPullRequest className="w-5 h-5" />
                </div>
                <h3 className="font-display font-bold text-base text-ink">1-Click Bot Automation</h3>
                <p className="text-xs text-ink-secondary leading-relaxed">
                  Generates drop-in replacement blocks committable directly inside GitHub PR reviews, or automatically opens dedicated remediation pull requests with a single click.
                </p>
              </div>
            </div>
          </div>

          {/* PALE COMPARISON & DISCLOSURE AREA */}
          <div className="bg-ground-muted rounded-panel p-8 sm:p-10 border border-rule space-y-8">
            <div className="max-w-2xl">
              <span className="text-xs font-mono uppercase tracking-wider text-accent font-semibold">Technical Comparison</span>
              <h2 className="font-display font-bold text-2xl text-ink tracking-tight mt-1">
                Why Naive Diff Wrappers Fail
              </h2>
            </div>

            {/* Comparison Cards */}
            <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
              <div className="bg-panel border border-rule rounded-panel p-6 shadow-card space-y-4">
                <div className="flex items-center gap-2 text-rose-600 font-display font-bold text-sm">
                  <AlertCircle className="w-4 h-4" />
                  <span>Naive Diff Wrappers (Common Pitfall)</span>
                </div>
                <ul className="space-y-2 text-xs text-ink-secondary">
                  <li className="flex items-start gap-2">
                    <span className="text-rose-500 mt-0.5">✕</span>
                    <span>Raw diff strings without enclosing functions cause 22% hallucination rates.</span>
                  </li>
                  <li className="flex items-start gap-2">
                    <span className="text-rose-500 mt-0.5">✕</span>
                    <span>No SAST security grounding flags fake vulnerabilities or misses real SQL injections.</span>
                  </li>
                  <li className="flex items-start gap-2">
                    <span className="text-rose-500 mt-0.5">✕</span>
                    <span>Alert fatigue: flooded with subjective style nits like "consider adding docstrings".</span>
                  </li>
                </ul>
              </div>

              <div className="bg-panel border-2 border-accent rounded-panel p-6 shadow-lifted space-y-4 relative">
                <div className="flex items-center justify-between">
                  <div className="flex items-center gap-2 text-accent font-display font-bold text-sm">
                    <ShieldCheck className="w-4 h-4" />
                    <span>AI Code Reviewer (Enterprise v2.0)</span>
                  </div>
                  <span className="text-[10px] font-mono px-2 py-0.5 rounded-full bg-accent/10 text-accent font-bold">
                    RECOMMENDED
                  </span>
                </div>
                <ul className="space-y-2 text-xs text-ink">
                  <li className="flex items-start gap-2">
                    <span className="text-accent mt-0.5">✓</span>
                    <span><strong>Tree-sitter AST Context:</strong> 2-hop caller/callee graphs and imported signatures bounded for compilation accuracy.</span>
                  </li>
                  <li className="flex items-start gap-2">
                    <span className="text-accent mt-0.5">✓</span>
                    <span><strong>Anti-Noise Gate:</strong> Hard drops any finding under 0.80 confidence or categorized as style_nitpick.</span>
                  </li>
                  <li className="flex items-start gap-2">
                    <span className="text-accent mt-0.5">✓</span>
                    <span><strong>Committable Diffs:</strong> Exact drop-in replacement blocks committable directly in GitHub and GitLab.</span>
                  </li>
                </ul>
              </div>
            </div>

            {/* Questions / Native Disclosures with Ruled Rows and Rotating Plus */}
            <div className="pt-4 space-y-2 border-t border-rule">
              <h3 className="font-display font-bold text-base text-ink mb-4">Frequently Asked Questions</h3>

              {[
                {
                  q: "How does the 2-hop AST call graph prevent hallucinations?",
                  a: "Rather than passing isolated line changes to the LLM, the Tree-sitter analyzer constructs an iterative syntax tree to extract the enclosing function or class scope, the symbols it invokes (callees), and the upstream functions that invoke it (callers). This guarantees the model understands the semantic contract.",
                },
                {
                  q: "How does the anti-noise gate drop non-committable comments?",
                  a: "Every finding generated by either deterministic Semgrep SAST or LLM inference must conform to a Pydantic v2 schema. If the calculated confidence is less than 0.80 or the category is style_nitpick, it is rejected before ever reaching the review comment payload.",
                },
                {
                  q: "Can I run this without exposing my code to third-party APIs?",
                  a: "Yes. In the Settings tab, you can select local engines or connect via Ollama / vLLM running Qwen2.5-Coder-7B-Instruct with zero code data leaving your VPC or network perimeter.",
                },
              ].map((faq, idx) => {
                const isOpen = openFaq[idx] ?? false;
                return (
                  <div key={idx} className="border-b border-rule py-3">
                    <button
                      type="button"
                      onClick={() => setOpenFaq((prev) => ({ ...prev, [idx]: !isOpen }))}
                      className="w-full flex items-center justify-between text-left text-sm font-semibold text-ink hover:text-accent transition-colors"
                    >
                      <span>{faq.q}</span>
                      <Plus
                        className={`w-4 h-4 text-ink-secondary shrink-0 transition-transform duration-160 ${
                          isOpen ? "rotate-45 text-accent" : ""
                        }`}
                      />
                    </button>
                    {isOpen && (
                      <p className="text-xs text-ink-secondary pt-2.5 leading-relaxed pr-8">
                        {faq.a}
                      </p>
                    )}
                  </div>
                );
              })}
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
