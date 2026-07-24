import { ExternalLink, FolderOpen, Play, Square } from "lucide-react";
import { useEffect, useState } from "react";
import { api } from "../api";
import { Button, Field, Input, Panel, Select } from "../components/ui";
import { useStudio } from "../store";

export default function ExportQueue() {
  const folder = useStudio((state) => state.project.draft_folder);
  const jobs = useStudio((state) => state.jobs);
  const setNotice = useStudio((state) => state.setNotice);
  const [drafts, setDrafts] = useState<string[]>([]);
  const [selected, setSelected] = useState<string[]>([]);
  const [values, setValues] = useState({ output_folder: "", resolution: "", framerate: "", timeout: 1200 });
  const active = [...jobs].reverse().find((job) => job.kind === "export" && ["started", "progress", "stopping"].includes(job.status));

  const refresh = async () => {
    if (!folder) return;
    try {
      const result = await api.get<{ items: string[] }>(`/drafts?folder=${encodeURIComponent(folder)}`);
      setDrafts(result.items);
    } catch (error) {
      setNotice({ kind: "error", text: String(error) });
    }
  };
  useEffect(() => { void refresh(); }, []);
  const start = async () => {
    try {
      await api.post("/jobs/export", { drafts: selected, ...values });
    } catch (error) {
      setNotice({ kind: "error", text: String(error) });
    }
  };

  return (
    <div className="workspace-page">
      <div className="page-heading">
        <div>
          <h1>Export Queue</h1>
          <p>Windows only · CapCut/Jianying 6 trở xuống · Stop sau item hiện tại.</p>
        </div>
        <Button tooltip={{ vi: "Khởi chạy CapCut khi tìm thấy executable.", en: "Launch CapCut when its executable is found." }} onClick={() => void api.post("/system/open-capcut")}>
          <ExternalLink size={16} /> Open CapCut
        </Button>
      </div>
      <div className="export-grid">
        <Panel title={`Draft queue (${selected.length})`}>
          <div className="select-list">
            {drafts.map((draft) => (
              <label key={draft} className={selected.includes(draft) ? "selected" : ""}>
                <input type="checkbox" checked={selected.includes(draft)} onChange={(event) => setSelected((current) => event.target.checked ? [...current, draft] : current.filter((item) => item !== draft))} />
                <FolderOpen size={16} />
                <span>{draft}</span>
              </label>
            ))}
          </div>
        </Panel>
        <Panel title="Export settings" className="form-card">
          <Field label="Output folder"><Input value={values.output_folder} onChange={(event) => setValues((current) => ({ ...current, output_folder: event.target.value }))} /></Field>
          <Field label="Resolution"><Select value={values.resolution} onChange={(event) => setValues((current) => ({ ...current, resolution: event.target.value }))}><option value="">Default</option><option value="RES_720P">720p</option><option value="RES_1080P">1080p</option><option value="RES_2K">2K</option><option value="RES_4K">4K</option></Select></Field>
          <Field label="Frame rate"><Select value={values.framerate} onChange={(event) => setValues((current) => ({ ...current, framerate: event.target.value }))}><option value="">Default</option><option value="FR_24">24 FPS</option><option value="FR_25">25 FPS</option><option value="FR_30">30 FPS</option><option value="FR_50">50 FPS</option><option value="FR_60">60 FPS</option></Select></Field>
          <Field label="Timeout (seconds)"><Input type="number" min="1" value={values.timeout} onChange={(event) => setValues((current) => ({ ...current, timeout: Number(event.target.value) }))} /></Field>
          <div className="warning-card">Export automation không hỗ trợ hủy item đang chạy. Stop chỉ ngăn item tiếp theo.</div>
          <div className="page-actions">
            <Button tooltip={{ vi: "Export tuần tự các draft đã chọn.", en: "Export selected drafts sequentially." }} variant="primary" disabled={!selected.length || Boolean(active)} onClick={() => void start()}>
              <Play size={16} /> Start queue
            </Button>
            <Button tooltip={{ vi: "Dừng trước draft kế tiếp.", en: "Stop before the next draft." }} variant="danger" disabled={!active} onClick={() => active && void api.post(`/jobs/${active.id}/stop`)}>
              <Square size={15} /> Stop after current
            </Button>
          </div>
        </Panel>
      </div>
    </div>
  );
}
