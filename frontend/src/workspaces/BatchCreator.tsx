import { FolderInput, PauseCircle, Play, RotateCcw } from "lucide-react";
import { useState } from "react";
import { api } from "../api";
import { Button, Field, Input, Panel } from "../components/ui";
import { useStudio } from "../store";

export default function BatchCreator() {
  const draftFolder = useStudio((state) => state.project.draft_folder);
  const jobs = useStudio((state) => state.jobs);
  const setNotice = useStudio((state) => state.setNotice);
  const [values, setValues] = useState({
    source_folder: "",
    draft_folder: draftFolder,
    voice_path: "",
    subtitle_path: "",
    duration: "30s",
    width: 1920,
    height: 1080,
    fps: 30,
    voice_volume: 1,
    mute_source: true,
    add_subtitles: true,
    limit: 10,
    test_mode: false,
    overwrite: false,
    prefix: "auto_video"
  });
  const active = [...jobs].reverse().find((job) =>
    ["started", "progress", "stopping"].includes(job.status)
  );
  const resumable = [...jobs].reverse().find(
    (job) =>
      job.kind === "batch" &&
      job.status === "completed" &&
      typeof job.result === "object" &&
      job.result !== null &&
      Number((job.result as { remaining?: number }).remaining ?? 0) > 0
  );
  const set = (key: string, value: unknown) =>
    setValues((current) => ({ ...current, [key]: value }));
  const browse = async (key: "source_folder" | "draft_folder") => {
    const path = await window.pywebview?.api.select_folder();
    if (path) set(key, path);
  };
  const start = async () => {
    try {
      await api.post("/jobs/batch", values);
      setNotice({ kind: "success", text: "Batch started" });
    } catch (error) {
      setNotice({ kind: "error", text: String(error) });
    }
  };
  const stop = async () => {
    if (active) await api.post(`/jobs/${active.id}/stop`);
  };
  const resume = async () => {
    try {
      await api.post("/jobs/batch/resume");
    } catch (error) {
      setNotice({ kind: "error", text: String(error) });
    }
  };

  return (
    <div className="workspace-page compact-page">
      <div className="page-heading">
        <div>
          <h1>Batch Creator</h1>
          <p>Mỗi source video tạo một draft; Resume tiếp tục từ item chưa xử lý.</p>
        </div>
        <span className="feature-badge">source → draft</span>
      </div>
      <div className="form-columns">
        <Panel title="Nguồn / Sources" className="form-card">
          {[
            ["source_folder", "Source videos folder"],
            ["draft_folder", "CapCut draft folder"]
          ].map(([key, label]) => (
            <Field label={label} key={key}>
              <div className="input-action">
                <Input value={String(values[key as keyof typeof values])} onChange={(event) => set(key, event.target.value)} />
                <Button tooltip={{ vi: "Chọn thư mục trên máy.", en: "Choose a folder on this computer." }} onClick={() => void browse(key as "source_folder" | "draft_folder")}>
                  <FolderInput size={15} />
                </Button>
              </div>
            </Field>
          ))}
          <Field label="Voice path"><Input value={values.voice_path} onChange={(event) => set("voice_path", event.target.value)} /></Field>
          <Field label="Subtitle SRT"><Input value={values.subtitle_path} onChange={(event) => set("subtitle_path", event.target.value)} /></Field>
          <Field label="Draft prefix"><Input value={values.prefix} onChange={(event) => set("prefix", event.target.value)} /></Field>
        </Panel>
        <Panel title="Thiết lập / Settings" className="form-card">
          <div className="mini-grid">
            {[
              ["duration", "Duration", "text"],
              ["width", "Width", "number"],
              ["height", "Height", "number"],
              ["fps", "FPS", "number"],
              ["voice_volume", "Voice volume", "number"],
              ["limit", "Quantity", "number"]
            ].map(([key, label, type]) => (
              <Field label={label} key={key}>
                <Input type={type} value={String(values[key as keyof typeof values])} onChange={(event) => set(key, type === "number" ? Number(event.target.value) : event.target.value)} />
              </Field>
            ))}
          </div>
          {[
            ["mute_source", "Mute source audio"],
            ["add_subtitles", "Add subtitles"],
            ["test_mode", "Test mode (max 3)"],
            ["overwrite", "Overwrite existing drafts"]
          ].map(([key, label]) => (
            <label className="switch-row" key={key}>
              <span>{label}</span>
              <input type="checkbox" checked={Boolean(values[key as keyof typeof values])} onChange={(event) => set(key, event.target.checked)} />
            </label>
          ))}
        </Panel>
      </div>
      <Panel title="Progress" className="batch-progress">
        <div className="progress-line">
          <div style={{ width: `${active?.total ? (active.current / active.total) * 100 : 0}%` }} />
        </div>
        <div className="progress-stats">
          <strong>{active?.message || "Ready"}</strong>
          <span>{active ? `${active.current}/${active.total}` : "0/0"}</span>
          <span>Status: {active?.status ?? "idle"}</span>
        </div>
        <div className="page-actions">
          <Button tooltip={{ vi: "Bắt đầu hoặc chạy lại batch.", en: "Start or run the batch again." }} variant="primary" disabled={Boolean(active)} onClick={() => void start()}>
            <Play size={16} /> Start
          </Button>
          <Button tooltip={{ vi: "Tiếp tục từ item chưa xử lý bằng trạng thái batch hiện tại.", en: "Resume from the next unprocessed item in the current batch state." }} disabled={Boolean(active) || !resumable} onClick={() => void resume()}>
            <RotateCcw size={16} /> Resume
          </Button>
          <Button tooltip={{ vi: "Dừng trước item tiếp theo; item đang xử lý không bị hủy cưỡng bức.", en: "Stop before the next item; the current item is not force-cancelled." }} variant="danger" disabled={!active} onClick={() => void stop()}>
            <PauseCircle size={16} /> Stop
          </Button>
        </div>
      </Panel>
    </div>
  );
}
