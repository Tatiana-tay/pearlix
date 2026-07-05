import { useState } from "react";
import { Maximize2, Minus, Plus, RotateCcw } from "lucide-react";
import type { BackendAIResult, BackendAIResultFinding, BackendAttachment } from "../../types/models";
import { aiStatusTone } from "../../utils/statusStyles";
import { Badge } from "../ui/Badge";
import { Button } from "../ui/Button";
import { Card } from "../ui/Card";
import { EmptyState } from "../ui/EmptyState";
import { AiFindingsTable } from "./AiFindingsTable";

interface XrayViewerProps {
  result: BackendAIResult;
  findings: BackendAIResultFinding[];
  attachment?: BackendAttachment;
  onRetryAnalysis?: () => void;
}

export function XrayViewer({ result, findings, attachment, onRetryAnalysis }: XrayViewerProps) {
  const [showOverlay, setShowOverlay] = useState(result.status === "Completed");
  const [zoom, setZoom] = useState(1);

  return (
    <div className="xray-layout">
      <Card className="xray-viewer-card">
        <div className="xray-toolbar">
          <div className="row">
            <button
              type="button"
              className={`switch ${showOverlay ? "active" : ""}`}
              onClick={() => setShowOverlay((value) => !value)}
              aria-label="Show AI overlay"
              disabled={result.status !== "Completed"}
            />
            <strong>Show AI Overlay</strong>
          </div>
          <div className="row">
            <Button variant="secondary" icon={<Plus size={16} />} onClick={() => setZoom((value) => Math.min(value + 0.1, 1.6))}>Zoom in</Button>
            <Button variant="secondary" icon={<Minus size={16} />} onClick={() => setZoom((value) => Math.max(value - 0.1, 0.7))}>Zoom out</Button>
            <Button variant="secondary" icon={<Maximize2 size={16} />} onClick={() => setZoom(1)}>Fit</Button>
            <Button variant="ghost" icon={<RotateCcw size={16} />} onClick={() => setZoom(1)}>Reset</Button>
          </div>
        </div>

        <div className="xray-stage">
          {result.status === "Processing" && (
            <div className="xray-state">
              <EmptyState kind="loading" title="Analyzing uploaded X-ray..." description="Processing the image and preparing assistive overlays." />
            </div>
          )}
          {result.status === "Pending" && (
            <div className="xray-state">
              <EmptyState kind="loading" title="AI analysis pending" description="Run analysis when the doctor is ready to review the uploaded image." />
            </div>
          )}
          {result.status === "Failed" && (
            <div className="xray-state">
              <EmptyState kind="error" title="AI analysis failed" description="The image could not be processed. Check contrast and retry." action={<Button onClick={onRetryAnalysis}>Retry analysis</Button>} />
            </div>
          )}
          <div className="xray-canvas" style={{ transform: `scale(${zoom})` }}>
            <svg className="xray-base" viewBox="0 0 1000 420" role="img" aria-label="Mock panoramic dental X-ray">
              <defs>
                <radialGradient id="jawGlow" cx="50%" cy="45%" r="70%">
                  <stop offset="0%" stopColor="#e2e8f0" stopOpacity="0.86" />
                  <stop offset="55%" stopColor="#64748b" stopOpacity="0.52" />
                  <stop offset="100%" stopColor="#0f172a" stopOpacity="0" />
                </radialGradient>
                <linearGradient id="toothGlow" x1="0%" y1="0%" x2="100%" y2="100%">
                  <stop offset="0%" stopColor="#f8fafc" stopOpacity="0.72" />
                  <stop offset="100%" stopColor="#94a3b8" stopOpacity="0.42" />
                </linearGradient>
              </defs>
              <rect width="1000" height="420" fill="#0f172a" />
              <ellipse cx="500" cy="212" rx="420" ry="162" fill="url(#jawGlow)" />
              <path d="M158 222 C250 112, 392 86, 504 92 C628 98, 766 132, 846 226" fill="none" stroke="#b6c2d5" strokeWidth="36" strokeOpacity="0.3" />
              <path d="M176 228 C260 315, 380 346, 502 344 C628 342, 754 312, 830 228" fill="none" stroke="#a7b5ca" strokeWidth="36" strokeOpacity="0.26" />
              {Array.from({ length: 16 }).map((_, index) => {
                const x = 160 + index * 45;
                const y = 165 + Math.sin(index / 2) * 18;
                const height = 76 + (index % 3) * 10;
                return <rect key={`top-${index}`} x={x} y={y} width="34" height={height} rx="14" fill="url(#toothGlow)" opacity="0.86" />;
              })}
              {Array.from({ length: 16 }).map((_, index) => {
                const x = 170 + index * 43;
                const y = 250 + Math.cos(index / 2) * 14;
                const height = 78 + (index % 4) * 7;
                return <rect key={`bottom-${index}`} x={x} y={y} width="32" height={height} rx="14" fill="url(#toothGlow)" opacity="0.72" />;
              })}
            </svg>
            <svg className={`xray-overlay ${showOverlay ? "visible" : ""}`} viewBox="0 0 1000 420" aria-hidden="true">
              <circle cx="294" cy="210" r="38" fill="rgba(239, 71, 111, 0.24)" stroke="#ef476f" strokeWidth="4" />
              <circle cx="530" cy="165" r="42" fill="rgba(245, 184, 46, 0.2)" stroke="#f5b82e" strokeWidth="4" />
              <rect x="705" y="248" width="74" height="68" rx="20" fill="rgba(91, 174, 247, 0.22)" stroke="#5baef7" strokeWidth="4" />
              <path d="M440 290 C470 250, 512 252, 540 294" fill="none" stroke="#14b8a6" strokeWidth="5" strokeLinecap="round" />
            </svg>
          </div>
        </div>
      </Card>

      <Card className="xray-side-panel">
        <div className="between">
          <h2 className="card-title">AI Review</h2>
          <Badge tone={aiStatusTone[result.status]}>{result.status}</Badge>
        </div>
        <dl className="detail-list">
          <div><dt>X-ray File</dt><dd>{attachment?.fileName ?? result.fileId}</dd></div>
          <div><dt>Base Layer</dt><dd>{attachment ? "Authorized attachment preview" : "Viewer placeholder"}</dd></div>
          <div><dt>AI Overlay</dt><dd>{result.overlayUrl ? "Available from backend" : "Not available"}</dd></div>
          <div><dt>Model Version</dt><dd>{result.modelVersion}</dd></div>
          <div><dt>Processed Date</dt><dd>{result.processedDate}</dd></div>
          <div><dt>Overall Confidence</dt><dd>{Math.round(result.overallConfidence * 100)}%</dd></div>
          <div><dt>Detected Teeth Count</dt><dd>32</dd></div>
        </dl>
        <AiFindingsTable findings={findings} />
        <div className="notice-card">
          AI analysis is assistive educational/research output and must be reviewed by the doctor.
        </div>
      </Card>
    </div>
  );
}
