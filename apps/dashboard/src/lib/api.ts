export interface RepoSummary {
  owner: string;
  name: string;
  description?: string;
  stars: number;
  forks: number;
  default_branch: string;
  languages: Record<string, number>;
  health_score: number;
  executive_summary: string;
  analyzed_target: string;
  target_type: "repository" | "pull_request";
}

export interface CommitReportItem {
  sha: string;
  short_sha: string;
  author: string;
  date: string;
  message: string;
  impact_note: string;
  risk_level: "low" | "medium" | "high";
  files_changed_count: number;
  html_url: string;
}

export interface PRReportItem {
  number: number;
  title: string;
  author: string;
  state: string;
  created_at: string;
  branch: string;
  review_readiness: string;
  summary: string;
  html_url: string;
}

export interface CodeCorrection {
  id: string;
  file_path: string;
  start_line: number;
  end_line: number;
  severity: "critical" | "high" | "medium";
  category: "architecture" | "security" | "performance" | "concurrency" | "bug";
  confidence: number;
  explanation: string;
  original_code: string;
  corrected_code: string;
}

export interface CouplingHotspot {
  file_path: string;
  reason: string;
  risk_score: number;
  callers: string[];
}

export interface ScalabilityBottleneck {
  title: string;
  description: string;
  recommendation: string;
  severity: "critical" | "high" | "medium";
}

export interface ArchitectureAdvice {
  overall_critique: string;
  coupling_hotspots: CouplingHotspot[];
  scalability_bottlenecks: ScalabilityBottleneck[];
  refactoring_recommendations: string[];
  design_patterns_advice: string[];
}

export interface ASTInsights {
  total_symbols: number;
  classes_count: number;
  functions_count: number;
  classes: Array<{ name: string; file_path: string; start_line: number; end_line: number }>;
  functions: Array<{ name: string; file_path: string; start_line: number; end_line: number; calls?: string[] }>;
  dependency_map: Array<{ source: string; target: string; type: string }>;
}

export interface FileTreeItem {
  path: string;
  type: "file" | "directory";
  size_bytes?: number;
  symbols_count: number;
  issues_count: number;
  content?: string;
}

export interface RepoAnalysisReport {
  repo_summary: RepoSummary;
  commits_report: CommitReportItem[];
  prs_report: PRReportItem[];
  code_corrections: CodeCorrection[];
  architecture_advice: ArchitectureAdvice;
  ast_insights: ASTInsights;
  file_tree: FileTreeItem[];
  ai_provider_used: string;
  ai_model_used: string;
  analysis_duration_ms: number;
}

export interface RepoAnalysisRequest {
  git_url: string;
  provider: "openai" | "gemini";
  openai_api_key?: string;
  gemini_api_key?: string;
  github_token?: string;
  model?: string;
}

export interface PublishPRReviewRequest {
  pr_url: string;
  github_token: string;
  findings: CodeCorrection[];
  summary_body?: string;
}

export interface PublishPRReviewResponse {
  success: boolean;
  comments_posted: number;
  review_url: string;
  message: string;
}

export interface CreateFixPRRequest {
  git_url: string;
  github_token: string;
  correction: CodeCorrection;
  branch_name?: string;
  pr_title?: string;
}

export interface CreateFixPRResponse {
  success: boolean;
  pr_url: string;
  branch_name: string;
  message: string;
}

export interface ExportReportRequest {
  format: "sarif" | "markdown";
  report: RepoAnalysisReport;
}

export interface ExportReportResponse {
  content: string;
  filename: string;
  content_type: string;
}

const API_BASE = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000";

/**
 * Executes deep live Git repository or pull request analysis.
 */
export async function analyzeGitRepository(
  req: RepoAnalysisRequest,
  signal?: AbortSignal
): Promise<RepoAnalysisReport> {
  const res = await fetch(`${API_BASE}/api/v1/reviews/analyze-repo`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(req),
    signal,
  });

  if (!res.ok) {
    const errorData = await res.json().catch(() => ({}));
    throw new Error(errorData.detail || `Analysis failed with status ${res.status}`);
  }

  return (await res.json()) as RepoAnalysisReport;
}

/**
 * Publishes line-by-line review comments directly to the target GitHub Pull Request.
 */
export async function publishPRReview(req: PublishPRReviewRequest): Promise<PublishPRReviewResponse> {
  const res = await fetch(`${API_BASE}/api/v1/reviews/publish-pr-review`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(req),
  });

  if (!res.ok) {
    const errorData = await res.json().catch(() => ({}));
    throw new Error(errorData.detail || `Publish review failed with status ${res.status}`);
  }

  return (await res.json()) as PublishPRReviewResponse;
}

/**
 * Commits a suggested fix and opens a Pull Request on GitHub.
 */
export async function createFixPR(req: CreateFixPRRequest): Promise<CreateFixPRResponse> {
  const res = await fetch(`${API_BASE}/api/v1/reviews/create-fix-pr`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(req),
  });

  if (!res.ok) {
    const errorData = await res.json().catch(() => ({}));
    throw new Error(errorData.detail || `Create fix PR failed with status ${res.status}`);
  }

  return (await res.json()) as CreateFixPRResponse;
}

/**
 * Generates SARIF or Markdown export of the audit report.
 */
export async function exportReport(req: ExportReportRequest): Promise<ExportReportResponse> {
  const res = await fetch(`${API_BASE}/api/v1/reviews/export-report`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(req),
  });

  if (!res.ok) {
    const errorData = await res.json().catch(() => ({}));
    throw new Error(errorData.detail || `Export failed with status ${res.status}`);
  }

  return (await res.json()) as ExportReportResponse;
}
