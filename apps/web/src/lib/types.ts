export interface Me {
  id: string;
  email: string;
  name: string;
  memberships: { id: string; role: string; org: { id: string; name: string; tier: string } }[];
}

export interface Site {
  id: string;
  name: string;
  timezone: string;
}

export interface Camera {
  id: string;
  site_id: string;
  name: string;
  rtsp_main_masked: string;
  stream_meta: { codec?: string; width?: number; height?: number };
  check_status: string;
  cloud_ai_allowed: boolean;
}

export interface RuleVersion {
  id: string;
  version: number;
  source_text: string;
  spec: Record<string, unknown>;
  summary: string;
  assumptions: string[];
}

export interface Rule {
  id: string;
  site_id: string;
  name: string;
  status: "draft" | "active" | "paused";
  version: RuleVersion | null;
  created_at: string;
}

export interface Compiled {
  kind: "rule" | "question" | "unsupported" | "invalid" | "error";
  spec?: Record<string, unknown>;
  summary?: string;
  assumptions?: string[];
  question?: string;
  options?: string[];
  reason?: string;
  suggestion?: string;
  errors?: string[];
}

export interface Verification {
  answer?: "yes" | "no" | "unsure";
  confidence?: number;
  reason?: string;
  model?: string;
  error?: string;
}

export interface CamEvent {
  id: string;
  camera_id: string;
  camera: string;
  site_id: string;
  rule_id: string;
  rule: string;
  summary: string;
  track_id: number | null;
  state: "verifying" | "confirmed" | "unverified" | "dismissed";
  severity: "info" | "warning" | "critical";
  t_start: string;
  t_end: string | null;
  close_reason: string;
  reason: string;
  verification: Verification;
  feedback: string;
  has_snapshot: boolean;
}

export const GO2RTC_URL = (process.env.NEXT_PUBLIC_GO2RTC_URL ?? "http://localhost:1984").replace(/\/$/, "");
