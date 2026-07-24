export type Language = "vi" | "en";
export type Workspace = "editor" | "drafts" | "batch" | "templates" | "export";
export type MaterialKind = "video" | "image" | "audio" | "sticker";
export type TrackKind = "video" | "audio" | "text" | "sticker" | "effect" | "filter";

export interface KeyframeDTO {
  property: string;
  time: string;
  value: number;
  id: string;
}

export interface MaterialDTO {
  kind: MaterialKind;
  path: string;
  name: string;
  resource_id: string;
  id: string;
  metadata: {
    duration_us?: number;
    width?: number;
    height?: number;
    fps?: number;
    codec?: string;
  };
}

export interface SegmentDTO {
  kind: TrackKind | "subtitle";
  start: string;
  duration: string;
  material_id: string;
  name: string;
  options: Record<string, unknown>;
  keyframes: KeyframeDTO[];
  id: string;
}

export interface TrackDTO {
  kind: TrackKind;
  name: string;
  mute: boolean;
  relative_index: number;
  absolute_index: number | null;
  segments: SegmentDTO[];
  id: string;
}

export interface ProjectDTO {
  draft_folder: string;
  draft_name: string;
  width: number;
  height: number;
  fps: number;
  overwrite: boolean;
  materials: MaterialDTO[];
  tracks: TrackDTO[];
}

export interface ApiError {
  error_code: string;
  message_vi: string;
  message_en: string;
  path?: string;
  errors?: string[];
}

export interface Job {
  id: string;
  kind: string;
  status: string;
  current: number;
  total: number;
  message: string;
  result?: unknown;
  error?: string;
  logs: Array<{ level: string; message: string; time: string }>;
}

declare global {
  interface Window {
    pywebview?: {
      api: {
        select_files: (types?: string[]) => Promise<string[]>;
        select_folder: () => Promise<string>;
      };
    };
  }
}
