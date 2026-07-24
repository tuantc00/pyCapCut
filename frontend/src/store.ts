import { produce } from "immer";
import { create } from "zustand";
import { api } from "./api";
import type {
  Job,
  Language,
  MaterialDTO,
  ProjectDTO,
  SegmentDTO,
  TrackDTO,
  TrackKind,
  Workspace
} from "./types";

const id = () => crypto.randomUUID().replaceAll("-", "");
const defaultProject = (): ProjectDTO => ({
  draft_folder: "",
  draft_name: "new_draft",
  width: 1920,
  height: 1080,
  fps: 30,
  overwrite: false,
  materials: [],
  tracks: ["video", "audio", "text"].map((kind) => ({
    kind: kind as TrackKind,
    name: kind,
    mute: false,
    relative_index: 0,
    absolute_index: null,
    segments: [],
    id: id()
  }))
});

interface History {
  past: ProjectDTO[];
  future: ProjectDTO[];
}

interface StudioStore {
  workspace: Workspace;
  language: Language;
  project: ProjectDTO;
  history: History;
  selectedMaterialId: string | null;
  selectedTrackId: string | null;
  selectedSegmentId: string | null;
  jobs: Job[];
  logsOpen: boolean;
  busy: boolean;
  notice: { kind: "success" | "error" | "info"; text: string } | null;
  setWorkspace: (workspace: Workspace) => void;
  setLanguage: (language: Language) => void;
  load: () => Promise<void>;
  mutate: (recipe: (project: ProjectDTO) => void, checkpoint?: boolean) => void;
  undo: () => void;
  redo: () => void;
  selectMaterial: (id: string | null) => void;
  selectTrack: (id: string | null) => void;
  selectSegment: (trackId: string, segmentId: string) => void;
  addMaterial: (material: MaterialDTO) => void;
  removeSelected: () => void;
  addTrack: (kind: TrackKind) => void;
  addEmptySegment: (trackId: string, kind: TrackKind | "subtitle") => void;
  addMaterialSegment: (trackId: string, materialId: string, startSeconds: number) => void;
  updateSegment: (trackId: string, segmentId: string, patch: Partial<SegmentDTO>) => void;
  setJobs: (jobs: Job[]) => void;
  setNotice: (notice: StudioStore["notice"]) => void;
  toggleLogs: () => void;
  validate: () => Promise<void>;
  createDraft: () => Promise<void>;
}

let autosaveTimer = 0;
const scheduleSave = (project: ProjectDTO) => {
  window.clearTimeout(autosaveTimer);
  autosaveTimer = window.setTimeout(() => {
    void api.saveProject(project, true);
  }, 1000);
};

export const useStudio = create<StudioStore>((set, get) => ({
  workspace: "editor",
  language: "vi",
  project: defaultProject(),
  history: { past: [], future: [] },
  selectedMaterialId: null,
  selectedTrackId: null,
  selectedSegmentId: null,
  jobs: [],
  logsOpen: false,
  busy: false,
  notice: null,
  setWorkspace: (workspace) => set({ workspace }),
  setLanguage: (language) => {
    set({ language });
    void api.put("/settings", { language });
  },
  load: async () => {
    const [project, settings, recovery] = await Promise.all([
      api.project(),
      api.get<{ language?: Language }>("/settings"),
      api.get<{ dirty?: boolean; project?: ProjectDTO }>("/recovery")
    ]);
    let active = project;
    if (recovery.dirty && recovery.project) {
      const restore = window.confirm(
        settings.language === "en"
          ? "Restore the last unsaved editing session?"
          : "Khôi phục phiên chỉnh sửa chưa lưu gần nhất?"
      );
      if (restore) active = recovery.project;
      else await api.delete("/recovery");
    }
    await api.saveProject(active, Boolean(recovery.dirty));
    set({ project: active, language: settings.language ?? "vi" });
  },
  mutate: (recipe, checkpoint = true) => {
    const before = get().project;
    const next = produce(before, recipe);
    if (next === before) return;
    set((state) => ({
      project: next,
      history: checkpoint
        ? { past: [...state.history.past.slice(-49), before], future: [] }
        : state.history
    }));
    scheduleSave(next);
  },
  undo: () => {
    const { history, project } = get();
    const previous = history.past.at(-1);
    if (!previous) return;
    set({
      project: previous,
      history: {
        past: history.past.slice(0, -1),
        future: [project, ...history.future].slice(0, 50)
      }
    });
    scheduleSave(previous);
  },
  redo: () => {
    const { history, project } = get();
    const next = history.future[0];
    if (!next) return;
    set({
      project: next,
      history: {
        past: [...history.past, project].slice(-50),
        future: history.future.slice(1)
      }
    });
    scheduleSave(next);
  },
  selectMaterial: (selectedMaterialId) =>
    set({ selectedMaterialId, selectedSegmentId: null, selectedTrackId: null }),
  selectTrack: (selectedTrackId) =>
    set({ selectedTrackId, selectedSegmentId: null, selectedMaterialId: null }),
  selectSegment: (selectedTrackId, selectedSegmentId) =>
    set({ selectedTrackId, selectedSegmentId, selectedMaterialId: null }),
  addMaterial: (material) => {
    get().mutate((project) => {
      project.materials.push(material);
    });
    set({ selectedMaterialId: material.id });
  },
  removeSelected: () => {
    const { selectedTrackId, selectedSegmentId, selectedMaterialId } = get();
    get().mutate((project) => {
      if (selectedSegmentId && selectedTrackId) {
        const track = project.tracks.find((item) => item.id === selectedTrackId);
        if (track) track.segments = track.segments.filter((item) => item.id !== selectedSegmentId);
      } else if (selectedTrackId) {
        project.tracks = project.tracks.filter((item) => item.id !== selectedTrackId);
      } else if (selectedMaterialId) {
        const used = project.tracks.some((track) =>
          track.segments.some((segment) => segment.material_id === selectedMaterialId)
        );
        if (!used) {
          project.materials = project.materials.filter((item) => item.id !== selectedMaterialId);
        }
      }
    });
    set({ selectedTrackId: null, selectedSegmentId: null, selectedMaterialId: null });
  },
  addTrack: (kind) => {
    get().mutate((project) => {
      const count = project.tracks.filter((item) => item.kind === kind).length;
      project.tracks.push({
        kind,
        name: count ? `${kind}_${count + 1}` : kind,
        mute: false,
        relative_index: 0,
        absolute_index: null,
        segments: [],
        id: id()
      });
    });
  },
  addEmptySegment: (trackId, kind) => {
    get().mutate((project) => {
      const track = project.tracks.find((item) => item.id === trackId);
      if (!track) return;
      const accepted = kind === "subtitle" ? "text" : kind;
      if (track.kind !== accepted) return;
      const lastEnd = track.segments.reduce(
        (maximum, segment) =>
          Math.max(
            maximum,
            Number.parseFloat(segment.start) + Number.parseFloat(segment.duration)
          ),
        0
      );
      const defaults: Record<string, unknown> =
        kind === "text"
          ? { text: "New text", style: { size: 8, color: "#FFFFFF", alpha: 1 } }
          : kind === "subtitle"
            ? { srt_path: "", time_offset: "0s", style: { size: 8 } }
            : kind === "sticker"
              ? { resource_id: "", clip: {} }
              : kind === "filter"
                ? { name: "", intensity: 100 }
                : { name: "", family: "scene", params: [] };
      track.segments.push({
        kind,
        start: `${lastEnd.toFixed(3)}s`,
        duration: "3s",
        material_id: "",
        name: `New ${kind}`,
        options: defaults,
        keyframes: [],
        id: id()
      });
    });
  },
  addMaterialSegment: (trackId, materialId, startSeconds) => {
    get().mutate((project) => {
      const material = project.materials.find((item) => item.id === materialId);
      const track = project.tracks.find((item) => item.id === trackId);
      if (!material || !track) return;
      const compatible =
        material.kind === "audio"
          ? track.kind === "audio"
          : material.kind === "sticker"
            ? track.kind === "sticker"
            : track.kind === "video";
      if (!compatible) return;
      const durationUs =
        material.kind === "image"
          ? 5_000_000
          : Math.max(100_000, material.metadata.duration_us ?? 1_000_000);
      track.segments.push({
        kind: material.kind === "image" ? "video" : material.kind,
        start: `${Math.max(0, startSeconds).toFixed(3)}s`,
        duration: `${(durationUs / 1_000_000).toFixed(3)}s`,
        material_id: material.id,
        name: material.name,
        options: { volume: 1, speed: 1, opacity: 1 },
        keyframes: [],
        id: id()
      });
    });
  },
  updateSegment: (trackId, segmentId, patch) => {
    get().mutate((project) => {
      const segment = project.tracks
        .find((item) => item.id === trackId)
        ?.segments.find((item) => item.id === segmentId);
      if (segment) Object.assign(segment, patch);
    });
  },
  setJobs: (jobs) => set({ jobs }),
  setNotice: (notice) => set({ notice }),
  toggleLogs: () => set((state) => ({ logsOpen: !state.logsOpen })),
  validate: async () => {
    set({ busy: true });
    try {
      const result = await api.validate(get().project);
      set({
        notice: result.valid
          ? { kind: "success", text: get().language === "vi" ? "Project hợp lệ" : "Project is valid" }
          : {
              kind: "error",
              text:
                get().language === "vi"
                  ? result.errors[0]?.message_vi ?? "Project chưa hợp lệ"
                  : result.errors[0]?.message_en ?? "Project is invalid"
            }
      });
    } finally {
      set({ busy: false });
    }
  },
  createDraft: async () => {
    set({ busy: true });
    try {
      const result = await api.createDraft(get().project);
      set({
        notice: {
          kind: "success",
          text: `${get().language === "vi" ? "Đã tạo Draft" : "Draft created"}: ${result.path}`
        }
      });
    } catch (error) {
      set({ notice: { kind: "error", text: String(error) } });
    } finally {
      set({ busy: false });
    }
  }
}));
