import { useVirtualizer } from "@tanstack/react-virtual";
import {
  AudioLines,
  Film,
  Image as ImageIcon,
  Lock,
  Plus,
  Search,
  Trash2,
  Type,
  Upload,
  Volume2
} from "lucide-react";
import {
  useEffect,
  useMemo,
  useRef,
  useState,
  type ChangeEvent,
  type PointerEvent as ReactPointerEvent
} from "react";
import { api } from "../api";
import { Button, Field, Input, Panel, Select } from "../components/ui";
import { useI18n } from "../i18n";
import { useStudio } from "../store";
import type {
  MaterialDTO,
  MaterialKind,
  SegmentDTO,
  TrackDTO,
  TrackKind
} from "../types";

const parseSeconds = (value: string | number) => {
  if (typeof value === "number") return value;
  const number = Number.parseFloat(value);
  if (/^-?\d+(\.\d+)?$/.test(value.trim())) return number;
  const parts = [...value.toLowerCase().matchAll(/(\d+(?:\.\d+)?)\s*([hms])/g)];
  return parts.reduce(
    (sum, part) =>
      sum + Number(part[1]) * (part[2] === "h" ? 3600 : part[2] === "m" ? 60 : 1),
    0
  );
};

const secondsText = (seconds: number) => `${Math.max(0, seconds).toFixed(3)}s`;
const kindFromName = (name: string): MaterialKind => {
  const extension = name.split(".").at(-1)?.toLowerCase();
  if (["mp3", "wav", "aac", "flac", "m4a"].includes(extension ?? "")) return "audio";
  if (["png", "jpg", "jpeg", "webp", "gif", "bmp"].includes(extension ?? "")) return "image";
  return "video";
};

function MaterialIcon({ kind }: { kind: MaterialKind }) {
  if (kind === "audio") return <AudioLines size={24} />;
  if (kind === "image") return <ImageIcon size={24} />;
  return <Film size={24} />;
}

function MediaLibrary() {
  const { t } = useI18n();
  const materials = useStudio((state) => state.project.materials);
  const selectedId = useStudio((state) => state.selectedMaterialId);
  const selectMaterial = useStudio((state) => state.selectMaterial);
  const addMaterial = useStudio((state) => state.addMaterial);
  const removeSelected = useStudio((state) => state.removeSelected);
  const setNotice = useStudio((state) => state.setNotice);
  const [query, setQuery] = useState("");
  const inputRef = useRef<HTMLInputElement>(null);
  const scrollRef = useRef<HTMLDivElement>(null);
  const filtered = materials.filter((item) =>
    item.name.toLowerCase().includes(query.toLowerCase())
  );
  const virtualizer = useVirtualizer({
    count: filtered.length,
    getScrollElement: () => scrollRef.current,
    estimateSize: () => 82,
    overscan: 5
  });

  const registerPaths = async (paths: string[]) => {
    for (const path of paths) {
      try {
        addMaterial(await api.registerMedia(path, kindFromName(path)));
      } catch (error) {
        setNotice({ kind: "error", text: String(error) });
      }
    }
  };
  const importMedia = async () => {
    if (window.pywebview?.api) {
      const paths = await window.pywebview.api.select_files();
      await registerPaths(paths);
    } else {
      inputRef.current?.click();
    }
  };
  const upload = async (event: ChangeEvent<HTMLInputElement>) => {
    for (const file of Array.from(event.target.files ?? [])) {
      try {
        addMaterial(await api.uploadMedia(file, kindFromName(file.name)));
      } catch (error) {
        setNotice({ kind: "error", text: String(error) });
      }
    }
    event.target.value = "";
  };

  return (
    <Panel
      title={t("media")}
      className="media-panel"
      actions={
        <Button
          tooltip={{
            vi: "Nhập video, ảnh hoặc audio. Desktop giữ đường dẫn gốc; browser upload bản sao.",
            en: "Import video, image or audio. Desktop keeps the source path; browser uploads a copy."
          }}
          variant="primary"
          onClick={() => void importMedia()}
        >
          <Plus size={16} /> {t("importMedia")}
        </Button>
      }
    >
      <input ref={inputRef} type="file" multiple hidden onChange={(event) => void upload(event)} />
      <div className="media-search">
        <Search size={15} />
        <Input
          placeholder={t("search")}
          value={query}
          onChange={(event) => setQuery(event.target.value)}
        />
        <Button
          tooltip={{
            vi: "Xóa media được chọn nếu chưa được segment sử dụng.",
            en: "Remove the selected media when no segment is using it."
          }}
          variant="ghost"
          disabled={!selectedId}
          onClick={removeSelected}
        >
          <Trash2 size={16} />
        </Button>
      </div>
      <div className="media-list" ref={scrollRef}>
        <div style={{ height: virtualizer.getTotalSize(), position: "relative" }}>
          {virtualizer.getVirtualItems().map((row) => {
            const material = filtered[row.index];
            const duration = (material.metadata.duration_us ?? 0) / 1_000_000;
            return (
              <button
                key={material.id}
                className={`media-card ${selectedId === material.id ? "selected" : ""}`}
                style={{ transform: `translateY(${row.start}px)` }}
                onClick={() => selectMaterial(material.id)}
                draggable
                onDragStart={(event) => {
                  event.dataTransfer.setData("application/x-pycapcut-material", material.id);
                  event.dataTransfer.effectAllowed = "copy";
                }}
              >
                <span className={`media-thumb media-${material.kind}`}>
                  {material.kind === "image" ? (
                    <img src={`/api/v1/media/${material.id}/stream`} alt="" loading="lazy" />
                  ) : (
                    <MaterialIcon kind={material.kind} />
                  )}
                </span>
                <span className="media-info">
                  <strong>{material.name}</strong>
                  <small>
                    {material.kind.toUpperCase()}
                    {duration ? ` · ${duration.toFixed(1)}s` : ""}
                  </small>
                  <small>
                    {material.metadata.width && material.metadata.height
                      ? `${material.metadata.width}×${material.metadata.height}`
                      : material.metadata.codec ?? ""}
                  </small>
                </span>
              </button>
            );
          })}
        </div>
        {!filtered.length && (
          <div className="empty-state">
            <Upload size={28} />
            <span>{t("importMedia")}</span>
          </div>
        )}
      </div>
    </Panel>
  );
}

function SourcePreview() {
  const { t } = useI18n();
  const project = useStudio((state) => state.project);
  const materialId = useStudio((state) => state.selectedMaterialId);
  const segmentId = useStudio((state) => state.selectedSegmentId);
  let selected = project.materials.find((item) => item.id === materialId);
  if (!selected && segmentId) {
    const segment = project.tracks
      .flatMap((track) => track.segments)
      .find((item) => item.id === segmentId);
    selected = project.materials.find((item) => item.id === segment?.material_id);
  }
  return (
    <Panel title={`${t("sourcePreview")} (Raw)`} className="preview-panel">
      <div className="preview-stage">
        {selected?.kind === "audio" && (
          <div className="audio-preview">
            <AudioLines size={64} />
            <strong>{selected.name}</strong>
            <audio controls src={`/api/v1/media/${selected.id}/stream`} />
          </div>
        )}
        {selected?.kind === "image" && (
          <img src={`/api/v1/media/${selected.id}/stream`} alt={selected.name} />
        )}
        {selected?.kind === "video" && (
          <video controls src={`/api/v1/media/${selected.id}/stream`} />
        )}
        {!selected && (
          <div className="empty-state">
            <Film size={34} />
            <span>Chọn media hoặc segment / Select media or segment</span>
          </div>
        )}
        <span className="raw-badge">RAW · no CapCut effects</span>
      </div>
    </Panel>
  );
}

function Clip({
  track,
  segment,
  pxPerSecond,
  overlap
}: {
  track: TrackDTO;
  segment: SegmentDTO;
  pxPerSecond: number;
  overlap: boolean;
}) {
  const selected = useStudio((state) => state.selectedSegmentId === segment.id);
  const selectSegment = useStudio((state) => state.selectSegment);
  const updateSegment = useStudio((state) => state.updateSegment);
  const start = parseSeconds(segment.start);
  const duration = parseSeconds(segment.duration);

  const pointerDown = (
    event: ReactPointerEvent<HTMLElement>,
    resize: boolean
  ) => {
    event.stopPropagation();
    selectSegment(track.id, segment.id);
    const originX = event.clientX;
    const originStart = start;
    const originDuration = duration;
    const element = event.currentTarget;
    let deltaSeconds = 0;
    const move = (moveEvent: PointerEvent) => {
      deltaSeconds = (moveEvent.clientX - originX) / pxPerSecond;
      if (resize) {
        element.style.width = `${Math.max(10, (originDuration + deltaSeconds) * pxPerSecond)}px`;
      } else {
        element.style.transform = `translateX(${deltaSeconds * pxPerSecond}px)`;
      }
    };
    const up = () => {
      element.style.transform = "";
      if (resize) element.style.width = "";
      if (resize) {
        updateSegment(track.id, segment.id, {
          duration: secondsText(Math.max(0.1, originDuration + deltaSeconds))
        });
      } else {
        updateSegment(track.id, segment.id, {
          start: secondsText(Math.max(0, originStart + deltaSeconds))
        });
      }
      window.removeEventListener("pointermove", move);
      window.removeEventListener("pointerup", up);
    };
    window.addEventListener("pointermove", move);
    window.addEventListener("pointerup", up, { once: true });
  };

  return (
    <button
      className={`timeline-clip clip-${track.kind} ${selected ? "selected" : ""} ${
        overlap ? "overlap" : ""
      }`}
      style={{ left: start * pxPerSecond, width: Math.max(10, duration * pxPerSecond) }}
      onPointerDown={(event) => pointerDown(event, false)}
      title={`${segment.name} · ${segment.start} → ${segment.duration}`}
    >
      <span>{segment.name || segment.kind}</span>
      <i onPointerDown={(event) => pointerDown(event, true)} />
    </button>
  );
}

function Timeline() {
  const { t } = useI18n();
  const project = useStudio((state) => state.project);
  const addTrack = useStudio((state) => state.addTrack);
  const addEmptySegment = useStudio((state) => state.addEmptySegment);
  const addMaterialSegment = useStudio((state) => state.addMaterialSegment);
  const selectTrack = useStudio((state) => state.selectTrack);
  const selectedTrackId = useStudio((state) => state.selectedTrackId);
  const [pxPerSecond, setPxPerSecond] = useState(56);
  const [newTrack, setNewTrack] = useState<TrackKind>("video");
  const [newSegment, setNewSegment] = useState<TrackKind | "subtitle">("text");
  const bodyRef = useRef<HTMLDivElement>(null);
  const projectDuration = Math.max(
    30,
    ...project.tracks.flatMap((track) =>
      track.segments.map((segment) => parseSeconds(segment.start) + parseSeconds(segment.duration))
    )
  );
  const timelineWidth = projectDuration * pxPerSecond + 180;
  const ticks = Array.from({ length: Math.ceil(projectDuration) + 1 }, (_, index) => index);

  const overlapping = (track: TrackDTO, segment: SegmentDTO) => {
    const start = parseSeconds(segment.start);
    const end = start + parseSeconds(segment.duration);
    return track.segments.some((other) => {
      if (other.id === segment.id) return false;
      const otherStart = parseSeconds(other.start);
      return start < otherStart + parseSeconds(other.duration) && end > otherStart;
    });
  };

  return (
    <Panel
      title={t("timeline")}
      className="timeline-panel"
      actions={
        <div className="timeline-tools">
          <Select value={newTrack} onChange={(event) => setNewTrack(event.target.value as TrackKind)}>
            {["video", "audio", "text", "sticker", "effect", "filter"].map((kind) => (
              <option key={kind}>{kind}</option>
            ))}
          </Select>
          <Button
            tooltip={{
              vi: "Thêm rãnh mới. Tên rãnh được tạo duy nhất tự động.",
              en: "Add a track. A unique track name is generated automatically."
            }}
            onClick={() => addTrack(newTrack)}
          >
            <Plus size={15} />
          </Button>
          <Select
            value={newSegment}
            onChange={(event) => setNewSegment(event.target.value as TrackKind | "subtitle")}
          >
            {["text", "subtitle", "sticker", "effect", "filter"].map((kind) => (
              <option key={kind}>{kind}</option>
            ))}
          </Select>
          <Button
            tooltip={{
              vi: "Thêm text, subtitle, sticker, effect hoặc filter vào rãnh tương thích đang chọn.",
              en: "Add text, subtitle, sticker, effect or filter to the selected compatible track."
            }}
            disabled={!selectedTrackId}
            onClick={() => selectedTrackId && addEmptySegment(selectedTrackId, newSegment)}
          >
            + Segment
          </Button>
          <span>−</span>
          <input
            aria-label="Timeline zoom"
            type="range"
            min="24"
            max="180"
            value={pxPerSecond}
            onChange={(event) => setPxPerSecond(Number(event.target.value))}
          />
          <span>+</span>
        </div>
      }
    >
      <div
        className="timeline-scroll"
        ref={bodyRef}
        onWheel={(event) => {
          if (event.ctrlKey) {
            event.preventDefault();
            setPxPerSecond((value) =>
              Math.max(24, Math.min(180, value + (event.deltaY < 0 ? 8 : -8)))
            );
          }
        }}
      >
        <div className="timeline-content" style={{ width: timelineWidth }}>
          <div className="ruler">
            <div className="track-label ruler-label">Tracks</div>
            <div className="ruler-ticks">
              {ticks.map((tick) => (
                <span key={tick} style={{ left: tick * pxPerSecond }}>
                  {tick}s
                </span>
              ))}
            </div>
          </div>
          {project.tracks.map((track) => (
            <div
              key={track.id}
              className={`track-row ${selectedTrackId === track.id ? "selected" : ""}`}
              onClick={() => selectTrack(track.id)}
              onDragOver={(event) => event.preventDefault()}
              onDrop={(event) => {
                const materialId = event.dataTransfer.getData("application/x-pycapcut-material");
                if (!materialId) return;
                const rect = event.currentTarget.getBoundingClientRect();
                const scrolled = bodyRef.current?.scrollLeft ?? 0;
                const seconds = (event.clientX - rect.left - 130 + scrolled) / pxPerSecond;
                addMaterialSegment(track.id, materialId, Math.max(0, seconds));
              }}
            >
              <button className="track-label" onClick={() => selectTrack(track.id)}>
                <span className={`track-icon icon-${track.kind}`}>
                  {track.kind === "audio" ? <Volume2 size={15} /> : track.kind === "text" ? <Type size={15} /> : <Film size={15} />}
                </span>
                <strong>{track.name}</strong>
                <Lock size={12} />
              </button>
              <div className="track-lane">
                {track.segments.map((segment) => (
                  <Clip
                    key={segment.id}
                    track={track}
                    segment={segment}
                    pxPerSecond={pxPerSecond}
                    overlap={overlapping(track, segment)}
                  />
                ))}
              </div>
            </div>
          ))}
        </div>
      </div>
    </Panel>
  );
}

const optionValue = (segment: SegmentDTO, path: string, fallback: unknown = "") => {
  let value: unknown = segment.options;
  for (const part of path.split(".")) {
    if (!value || typeof value !== "object") return fallback;
    value = (value as Record<string, unknown>)[part];
  }
  return (value ?? fallback) as string | number | boolean;
};

function InspectorInput({
  label,
  value,
  type = "text",
  onChange,
  hint
}: {
  label: string;
  value: string | number;
  type?: string;
  onChange: (value: string) => void;
  hint?: string;
}) {
  return (
    <Field label={label} hint={hint}>
      <Input type={type} value={value} onChange={(event) => onChange(event.target.value)} />
    </Field>
  );
}

function SegmentInspector({
  track,
  segment
}: {
  track: TrackDTO;
  segment: SegmentDTO;
}) {
  const mutate = useStudio((state) => state.mutate);
  const setNotice = useStudio((state) => state.setNotice);
  const [advanced, setAdvanced] = useState(() => JSON.stringify(segment.options, null, 2));
  useEffect(() => {
    setAdvanced(JSON.stringify(segment.options, null, 2));
  }, [segment.id]);
  const update = (recipe: (draft: SegmentDTO) => void) =>
    mutate((project) => {
      const current = project.tracks
        .find((item) => item.id === track.id)
        ?.segments.find((item) => item.id === segment.id);
      if (current) recipe(current);
    });
  const option = (path: string, value: unknown) =>
    update((draft) => {
      const parts = path.split(".");
      let target = draft.options;
      for (const part of parts.slice(0, -1)) {
        const existing = target[part];
        if (!existing || typeof existing !== "object" || Array.isArray(existing)) {
          target[part] = {};
        }
        target = target[part] as Record<string, unknown>;
      }
      target[parts.at(-1)!] = value;
    });
  const numeric = (path: string, value: string) =>
    option(path, value === "" ? "" : Number(value));
  const addKeyframe = () =>
    update((draft) => {
      draft.keyframes.push({
        property: track.kind === "audio" ? "volume" : "position_x",
        time: "0s",
        value: 0,
        id: crypto.randomUUID().replaceAll("-", "")
      });
    });

  return (
    <div className="inspector-scroll">
      <div className="inspector-title">
        <span className={`track-icon icon-${track.kind}`} />
        <strong>{segment.kind.toUpperCase()}</strong>
        <small>{track.name}</small>
      </div>
      <div className="property-group">
        <h3>Cơ bản / Basic</h3>
        <InspectorInput label="Tên / Name" value={segment.name} onChange={(value) => update((draft) => { draft.name = value; })} />
        <InspectorInput label="Bắt đầu / Start" value={segment.start} hint="1.5s, 2m3s" onChange={(value) => update((draft) => { draft.start = value; })} />
        <InspectorInput label="Thời lượng / Duration" value={segment.duration} hint="> 0s" onChange={(value) => update((draft) => { draft.duration = value; })} />
        {(track.kind === "video" || track.kind === "audio") && (
          <>
            <InspectorInput label="Nguồn / Source start" value={String(optionValue(segment, "source_start", "0s"))} onChange={(value) => option("source_start", value)} />
            <InspectorInput label="Độ dài nguồn" value={String(optionValue(segment, "source_duration", ""))} onChange={(value) => option("source_duration", value)} />
            <InspectorInput label="Tốc độ / Speed" type="number" value={Number(optionValue(segment, "speed", 1))} onChange={(value) => numeric("speed", value)} />
            <InspectorInput label="Âm lượng / Volume" type="number" value={Number(optionValue(segment, "volume", 1))} onChange={(value) => numeric("volume", value)} />
          </>
        )}
      </div>

      {(track.kind === "video" || track.kind === "sticker" || track.kind === "text") && (
        <div className="property-group">
          <h3>Transform</h3>
          {["transform_x", "transform_y", "scale_x", "scale_y", "rotation", "alpha"].map((key) => (
            <InspectorInput
              key={key}
              label={key === "alpha" ? "opacity / alpha" : key}
              type="number"
              value={Number(optionValue(segment, `clip.${key}`, key.startsWith("scale") || key === "alpha" ? 1 : 0))}
              onChange={(value) => numeric(`clip.${key}`, value)}
            />
          ))}
          {track.kind === "video" && (
            <>
              <InspectorInput label="Crop upper-left X" type="number" value={Number(optionValue(segment, "crop.upper_left_x", 0))} onChange={(value) => numeric("crop.upper_left_x", value)} />
              <InspectorInput label="Crop upper-left Y" type="number" value={Number(optionValue(segment, "crop.upper_left_y", 0))} onChange={(value) => numeric("crop.upper_left_y", value)} />
              <label className="checkbox-row">
                <input type="checkbox" checked={Boolean(optionValue(segment, "clip.flip_horizontal", false))} onChange={(event) => option("clip.flip_horizontal", event.target.checked)} />
                Flip horizontal
              </label>
              <label className="checkbox-row">
                <input type="checkbox" checked={Boolean(optionValue(segment, "clip.flip_vertical", false))} onChange={(event) => option("clip.flip_vertical", event.target.checked)} />
                Flip vertical
              </label>
            </>
          )}
        </div>
      )}

      {track.kind === "video" && (
        <div className="property-group">
          <h3>Fade · Animation · FX</h3>
          <label className="checkbox-row"><input type="checkbox" checked={Boolean(optionValue(segment, "fade.enabled", false))} onChange={(event) => option("fade.enabled", event.target.checked)} />Enable fade</label>
          <InspectorInput label="Fade in" value={String(optionValue(segment, "fade.in", "0s"))} onChange={(value) => option("fade.in", value)} />
          <InspectorInput label="Fade out" value={String(optionValue(segment, "fade.out", "0s"))} onChange={(value) => option("fade.out", value)} />
          <label className="checkbox-row"><input type="checkbox" checked={Boolean(optionValue(segment, "mask.enabled", false))} onChange={(event) => option("mask.enabled", event.target.checked)} />Enable mask</label>
          <InspectorInput label="Mask name" value={String(optionValue(segment, "mask.name", ""))} onChange={(value) => option("mask.name", value)} />
          <InspectorInput label="Mask size" type="number" value={Number(optionValue(segment, "mask.size", .5))} onChange={(value) => numeric("mask.size", value)} />
          <InspectorInput label="Mask feather" type="number" value={Number(optionValue(segment, "mask.feather", 0))} onChange={(value) => numeric("mask.feather", value)} />
          <label className="checkbox-row"><input type="checkbox" checked={Boolean(optionValue(segment, "transition.enabled", false))} onChange={(event) => option("transition.enabled", event.target.checked)} />Enable transition</label>
          <InspectorInput label="Transition name" value={String(optionValue(segment, "transition.name", ""))} onChange={(value) => option("transition.name", value)} />
          <InspectorInput label="Transition duration" value={String(optionValue(segment, "transition.duration", ""))} onChange={(value) => option("transition.duration", value)} />
          <label className="checkbox-row"><input type="checkbox" checked={Boolean(optionValue(segment, "background.enabled", false))} onChange={(event) => option("background.enabled", event.target.checked)} />Enable background</label>
          <InspectorInput label="Background type" value={String(optionValue(segment, "background.type", "blur"))} onChange={(value) => option("background.type", value)} />
          <InspectorInput label="Background color" value={String(optionValue(segment, "background.color", "#00000000"))} onChange={(value) => option("background.color", value)} />
        </div>
      )}

      {track.kind === "audio" && (
        <div className="property-group">
          <h3>Audio</h3>
          <label className="checkbox-row"><input type="checkbox" checked={Boolean(optionValue(segment, "fade.enabled", false))} onChange={(event) => option("fade.enabled", event.target.checked)} />Enable fade</label>
          <InspectorInput label="Fade in" value={String(optionValue(segment, "fade.in", "0s"))} onChange={(value) => option("fade.in", value)} />
          <InspectorInput label="Fade out" value={String(optionValue(segment, "fade.out", "0s"))} onChange={(value) => option("fade.out", value)} />
        </div>
      )}

      {track.kind === "text" && segment.kind !== "subtitle" && (
        <>
          <div className="property-group">
            <h3>Text</h3>
            <label className="field">
              <span>Nội dung / Content</span>
              <textarea className="input" value={String(optionValue(segment, "text", ""))} onChange={(event) => option("text", event.target.value)} />
            </label>
            <InspectorInput label="font" value={String(optionValue(segment, "font", ""))} onChange={(value) => option("font", value)} />
            <InspectorInput label="color" value={String(optionValue(segment, "style.color", "#FFFFFF"))} onChange={(value) => option("style.color", value)} />
            <InspectorInput label="align" type="number" value={Number(optionValue(segment, "style.align", 0))} onChange={(value) => numeric("style.align", value)} />
            {["size", "alpha", "letter_spacing", "line_spacing"].map((key) => (
              <InspectorInput key={key} label={key} type="number" value={Number(optionValue(segment, `style.${key}`, key === "alpha" ? 1 : 0))} onChange={(value) => numeric(`style.${key}`, value)} />
            ))}
            {["bold", "italic", "underline", "vertical", "auto_wrapping"].map((key) => (
              <label className="checkbox-row" key={key}>
                <input type="checkbox" checked={Boolean(optionValue(segment, `style.${key}`, false))} onChange={(event) => option(`style.${key}`, event.target.checked)} />
                {key}
              </label>
            ))}
            {[
              ["border.enabled", "border"],
              ["text_background.enabled", "background"],
              ["shadow.enabled", "shadow"],
              ["bubble.enabled", "bubble"],
              ["flower_text.enabled", "flower text"]
            ].map(([path, label]) => (
              <label className="checkbox-row" key={path}>
                <input type="checkbox" checked={Boolean(optionValue(segment, path, false))} onChange={(event) => option(path, event.target.checked)} />
                {label}
              </label>
            ))}
            <InspectorInput label="Bubble effect ID" value={String(optionValue(segment, "bubble.effect_id", ""))} onChange={(value) => option("bubble.effect_id", value)} />
            <InspectorInput label="Bubble resource ID" value={String(optionValue(segment, "bubble.resource_id", ""))} onChange={(value) => option("bubble.resource_id", value)} />
            <InspectorInput label="Flower effect ID" value={String(optionValue(segment, "flower_text.effect_id", ""))} onChange={(value) => option("flower_text.effect_id", value)} />
          </div>
        </>
      )}

      {segment.kind === "subtitle" && (
        <div className="property-group">
          <h3>Subtitle</h3>
          <InspectorInput label="SRT path" value={String(optionValue(segment, "srt_path", ""))} onChange={(value) => option("srt_path", value)} />
          <InspectorInput label="Time offset" value={String(optionValue(segment, "time_offset", "0s"))} onChange={(value) => option("time_offset", value)} />
          <InspectorInput label="Style reference" value={String(optionValue(segment, "style_reference_id", ""))} onChange={(value) => option("style_reference_id", value)} />
        </div>
      )}

      {(track.kind === "effect" || track.kind === "filter") && (
        <div className="property-group">
          <h3>Metadata</h3>
          <InspectorInput label="Name" value={String(optionValue(segment, "name", ""))} onChange={(value) => option("name", value)} />
          <InspectorInput label="Intensity" type="number" value={Number(optionValue(segment, "intensity", 1))} onChange={(value) => numeric("intensity", value)} />
          <InspectorInput label="Parameters" value={String(optionValue(segment, "params", ""))} onChange={(value) => option("params", value)} />
        </div>
      )}

      {track.kind === "sticker" && (
        <div className="property-group">
          <h3>Sticker</h3>
          <InspectorInput label="Resource ID" value={String(optionValue(segment, "resource_id", ""))} onChange={(value) => option("resource_id", value)} />
        </div>
      )}

      <div className="property-group">
        <h3>Advanced options JSON</h3>
        <textarea
          className="input advanced-json"
          value={advanced}
          spellCheck={false}
          onChange={(event) => setAdvanced(event.target.value)}
        />
        <Button
          tooltip={{
            vi: "Áp dụng schema options nâng cao đúng như adapter GUI hỗ trợ: animations, effects, filters, mask, transition, background, decoration…",
            en: "Apply advanced options supported by the GUI adapter: animations, effects, filters, mask, transition, background, decoration and more."
          }}
          onClick={() => {
            try {
              const parsed = JSON.parse(advanced) as Record<string, unknown>;
              update((draft) => {
                draft.options = parsed;
              });
            } catch (error) {
              setNotice({ kind: "error", text: `Invalid JSON: ${String(error)}` });
            }
          }}
        >
          Apply JSON
        </Button>
      </div>

      <div className="property-group">
        <h3>Keyframes</h3>
        {segment.keyframes.map((keyframe) => (
          <div className="keyframe-row" key={keyframe.id}>
            <Input value={keyframe.property} onChange={(event) => update((draft) => { const item = draft.keyframes.find((entry) => entry.id === keyframe.id); if (item) item.property = event.target.value; })} />
            <Input value={keyframe.time} onChange={(event) => update((draft) => { const item = draft.keyframes.find((entry) => entry.id === keyframe.id); if (item) item.time = event.target.value; })} />
            <Input type="number" value={keyframe.value} onChange={(event) => update((draft) => { const item = draft.keyframes.find((entry) => entry.id === keyframe.id); if (item) item.value = Number(event.target.value); })} />
            <button onClick={() => update((draft) => { draft.keyframes = draft.keyframes.filter((entry) => entry.id !== keyframe.id); })}><Trash2 size={13} /></button>
          </div>
        ))}
        <Button tooltip={{ vi: "Thêm keyframe trong khoảng thời lượng segment.", en: "Add a keyframe inside the segment duration." }} onClick={addKeyframe}>
          <Plus size={14} /> Keyframe
        </Button>
      </div>
    </div>
  );
}

function Inspector() {
  const { t } = useI18n();
  const project = useStudio((state) => state.project);
  const trackId = useStudio((state) => state.selectedTrackId);
  const segmentId = useStudio((state) => state.selectedSegmentId);
  const mutate = useStudio((state) => state.mutate);
  const track = project.tracks.find((item) => item.id === trackId);
  const segment = track?.segments.find((item) => item.id === segmentId);
  return (
    <Panel title={t("properties")} className="inspector-panel">
      {track && segment ? (
        <SegmentInspector track={track} segment={segment} />
      ) : track ? (
        <div className="inspector-scroll">
          <div className="property-group">
            <h3>Track</h3>
            <InspectorInput label="Name" value={track.name} onChange={(value) => mutate((projectDraft) => { const draft = projectDraft.tracks.find((item) => item.id === track.id); if (draft) draft.name = value; })} />
            <InspectorInput label="Relative index" type="number" value={track.relative_index} onChange={(value) => mutate((projectDraft) => { const draft = projectDraft.tracks.find((item) => item.id === track.id); if (draft) draft.relative_index = Number(value); })} />
            <InspectorInput label="Absolute index" type="number" value={track.absolute_index ?? ""} onChange={(value) => mutate((projectDraft) => { const draft = projectDraft.tracks.find((item) => item.id === track.id); if (draft) draft.absolute_index = value === "" ? null : Number(value); })} />
            <label className="checkbox-row">
              <input type="checkbox" checked={track.mute} onChange={(event) => mutate((projectDraft) => { const draft = projectDraft.tracks.find((item) => item.id === track.id); if (draft) draft.mute = event.target.checked; })} />
              Mute
            </label>
          </div>
        </div>
      ) : (
        <div className="inspector-scroll">
          <div className="property-group">
            <h3>Project / Draft</h3>
            <InspectorInput label="Draft name" value={project.draft_name} onChange={(value) => mutate((draft) => { draft.draft_name = value; })} />
            <Field label="Draft folder">
              <div className="input-action">
                <Input value={project.draft_folder} onChange={(event) => mutate((draft) => { draft.draft_folder = event.target.value; })} />
                <Button
                  tooltip={{ vi: "Chọn thư mục CapCut Drafts.", en: "Choose the CapCut Drafts folder." }}
                  onClick={() => void window.pywebview?.api.select_folder().then((path) => {
                    if (path) mutate((draft) => { draft.draft_folder = path; });
                  })}
                >
                  …
                </Button>
              </div>
            </Field>
            <InspectorInput label="Width" type="number" value={project.width} onChange={(value) => mutate((draft) => { draft.width = Number(value); })} />
            <InspectorInput label="Height" type="number" value={project.height} onChange={(value) => mutate((draft) => { draft.height = Number(value); })} />
            <InspectorInput label="FPS" type="number" value={project.fps} onChange={(value) => mutate((draft) => { draft.fps = Number(value); })} />
            <label className="checkbox-row">
              <input type="checkbox" checked={project.overwrite} onChange={(event) => mutate((draft) => { draft.overwrite = event.target.checked; })} />
              Overwrite existing draft
            </label>
          </div>
          <div className="empty-state inspector-empty">{t("noSelection")}</div>
        </div>
      )}
    </Panel>
  );
}

export default function Editor() {
  const undo = useStudio((state) => state.undo);
  const redo = useStudio((state) => state.redo);
  const removeSelected = useStudio((state) => state.removeSelected);
  useEffect(() => {
    const key = (event: KeyboardEvent) => {
      const target = event.target as HTMLElement;
      if (target.matches("input, textarea, select")) return;
      if (event.ctrlKey && event.key.toLowerCase() === "z") {
        event.preventDefault();
        undo();
      }
      if (event.ctrlKey && event.key.toLowerCase() === "y") {
        event.preventDefault();
        redo();
      }
      if (event.key === "Delete") removeSelected();
    };
    window.addEventListener("keydown", key);
    return () => window.removeEventListener("keydown", key);
  }, [redo, removeSelected, undo]);

  return (
    <div className="editor-layout">
      <MediaLibrary />
      <div className="editor-center">
        <SourcePreview />
        <Timeline />
      </div>
      <Inspector />
    </div>
  );
}
