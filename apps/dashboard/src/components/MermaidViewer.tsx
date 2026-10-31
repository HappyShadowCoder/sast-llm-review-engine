"use client";

import React, { useEffect, useRef, useState } from "react";
import mermaid from "mermaid";
import { Copy, Check, ZoomIn, ZoomOut, RefreshCw } from "lucide-react";

interface MermaidViewerProps {
  chart: string;
  theme?: "dark" | "light";
}

export const MermaidViewer: React.FC<MermaidViewerProps> = ({ chart, theme = "dark" }) => {
  const containerRef = useRef<HTMLDivElement>(null);
  const [svgContent, setSvgContent] = useState<string>("");
  const [zoom, setZoom] = useState(1);
  const [isCopied, setIsCopied] = useState(false);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    mermaid.initialize({
      startOnLoad: false,
      theme: theme === "dark" ? "dark" : "default",
      securityLevel: "loose",
      fontFamily: "var(--font-sans, sans-serif)",
      flowchart: {
        curve: "basis",
        padding: 20,
        nodeSpacing: 45,
        rankSpacing: 55,
        useMaxWidth: false,
      },
    });

    const renderChart = async () => {
      if (!chart.trim()) return;
      try {
        setError(null);
        const uniqueId = `mermaid-${Math.random().toString(36).substring(2, 9)}`;
        const { svg } = await mermaid.render(uniqueId, chart);
        setSvgContent(svg);
      } catch (err: any) {
        console.error("Mermaid render error:", err);
        setError("Failed to render architecture diagram.");
      }
    };

    renderChart();
  }, [chart, theme]);

  const handleCopyCode = () => {
    navigator.clipboard.writeText(chart);
    setIsCopied(true);
    setTimeout(() => setIsCopied(false), 2000);
  };

  return (
    <div className="w-full flex flex-col rounded-xl border border-rule dark:border-slate-800 bg-ground-muted/40 dark:bg-slate-950 overflow-hidden shadow-xs">
      {/* Control bar */}
      <div className="flex items-center justify-between px-4 py-2.5 border-b border-rule dark:border-slate-800 bg-panel dark:bg-slate-900/90 text-xs">
        <div className="flex items-center gap-2">
          <span className="font-semibold text-ink dark:text-white">GitDiagram Architecture Flow</span>
          <span className="text-[10px] font-mono px-2 py-0.5 rounded-full bg-accent/10 text-accent border border-accent/20">
            Interactive Mermaid Engine
          </span>
        </div>

        <div className="flex items-center gap-1.5">
          <button
            onClick={() => setZoom((z) => Math.max(0.4, Number((z - 0.15).toFixed(2))))}
            className="p-1 rounded hover:bg-ground-muted dark:hover:bg-slate-800 text-ink-secondary dark:text-slate-400"
            title="Zoom Out"
          >
            <ZoomOut className="w-3.5 h-3.5" />
          </button>
          <span className="text-[11px] font-mono text-ink-secondary dark:text-slate-400 px-1">
            {Math.round(zoom * 100)}%
          </span>
          <button
            onClick={() => setZoom((z) => Math.min(2.5, Number((z + 0.15).toFixed(2))))}
            className="p-1 rounded hover:bg-ground-muted dark:hover:bg-slate-800 text-ink-secondary dark:text-slate-400"
            title="Zoom In"
          >
            <ZoomIn className="w-3.5 h-3.5" />
          </button>
          <button
            onClick={() => setZoom(1)}
            className="px-2 py-0.5 rounded text-[11px] font-mono text-ink-secondary dark:text-slate-400 hover:bg-ground-muted dark:hover:bg-slate-800"
          >
            Reset
          </button>
          <div className="w-px h-4 bg-rule dark:bg-slate-800 mx-1" />
          <button
            onClick={handleCopyCode}
            className="px-2.5 py-1 rounded text-[11px] font-medium bg-ground-muted dark:bg-slate-800 hover:bg-rule/60 text-ink dark:text-slate-200 flex items-center gap-1 transition-colors"
          >
            {isCopied ? <Check className="w-3 h-3 text-emerald-400" /> : <Copy className="w-3 h-3" />}
            <span>{isCopied ? "Copied" : "Copy Mermaid"}</span>
          </button>
        </div>
      </div>

      {/* SVG Container */}
      <div
        ref={containerRef}
        className="w-full min-h-[480px] max-h-[640px] overflow-auto p-6 flex items-center justify-center cursor-grab active:cursor-grabbing select-none"
      >
        {error ? (
          <div className="text-xs text-rose-400 font-mono">{error}</div>
        ) : svgContent ? (
          <div
            style={{
              transform: `scale(${zoom})`,
              transformOrigin: "center center",
              transition: "transform 0.12s ease-out",
            }}
            dangerouslySetInnerHTML={{ __html: svgContent }}
            className="flex items-center justify-center [&_svg]:max-w-none [&_svg]:h-auto"
          />
        ) : (
          <div className="flex items-center gap-2 text-xs text-ink-secondary dark:text-slate-400">
            <RefreshCw className="w-4 h-4 animate-spin text-accent" />
            <span>Rendering architecture diagram...</span>
          </div>
        )}
      </div>
    </div>
  );
};

