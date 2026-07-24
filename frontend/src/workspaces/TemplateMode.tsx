import { Copy, FilePenLine, Import, Save, Search } from "lucide-react";
import { useState } from "react";
import { api } from "../api";
import { Button, Field, Input, Panel, Select } from "../components/ui";
import { useStudio } from "../store";

export default function TemplateMode() {
  const defaultFolder = useStudio((state) => state.project.draft_folder);
  const setNotice = useStudio((state) => state.setNotice);
  const [folder, setFolder] = useState(defaultFolder);
  const [name, setName] = useState("");
  const [inspect, setInspect] = useState("");
  const [tracks, setTracks] = useState<Array<{ index: number; name: string; type: string }>>([]);
  const [replace, setReplace] = useState({
    mode: "name",
    material_name: "",
    path: "",
    kind: "video",
    track_kind: "video",
    track_name: "",
    track_index: 0,
    segment_index: 0,
    source_start: "0s",
    source_duration: "",
    shrink: "cut_tail",
    extend_modes: "cut_material_tail",
    replace_crop: true
  });
  const [text, setText] = useState({ track_name: "", track_index: 0, segment_index: 0, text: "", recalc_style: true });
  const [trackImport, setTrackImport] = useState({
    source_folder: defaultFolder,
    source_name: "",
    track_kind: "video",
    track_name: "",
    track_index: 0,
    offset: "0s",
    new_name: "",
    relative_index: 0
  });
  const updateReplace = (key: string, value: unknown) => setReplace((current) => ({ ...current, [key]: value }));

  const load = async () => {
    try {
      const result = await api.post<{ inspect: string; tracks: typeof tracks }>("/template/load", { folder, name });
      setInspect(result.inspect);
      setTracks(result.tracks);
    } catch (error) {
      setNotice({ kind: "error", text: String(error) });
    }
  };
  const duplicate = async () => {
    const target = window.prompt("Duplicate template as", `${name}_copy`);
    if (!target) return;
    try {
      const result = await api.post<{ inspect: string }>("/template/duplicate", { target, overwrite: false });
      setName(target);
      setInspect(result.inspect);
    } catch (error) {
      setNotice({ kind: "error", text: String(error) });
    }
  };
  const replaceMaterial = async () => {
    try {
      await api.post("/template/replace-material", {
        ...replace,
        extend_modes: replace.extend_modes.split(",").map((item) => item.trim()).filter(Boolean)
      });
      setNotice({ kind: "success", text: "Material replaced in memory; press Save to write." });
    } catch (error) {
      setNotice({ kind: "error", text: String(error) });
    }
  };
  const replaceText = async () => {
    try {
      await api.post("/template/replace-text", text);
      setNotice({ kind: "success", text: "Text replaced in memory; press Save to write." });
    } catch (error) {
      setNotice({ kind: "error", text: String(error) });
    }
  };
  const save = async () => {
    try {
      await api.post("/template/save");
      setNotice({ kind: "success", text: "Template saved" });
    } catch (error) {
      setNotice({ kind: "error", text: String(error) });
    }
  };
  const importTrack = async () => {
    try {
      await api.post("/template/import-track", trackImport);
      setNotice({ kind: "success", text: "Track imported in memory; press Save to write." });
    } catch (error) {
      setNotice({ kind: "error", text: String(error) });
    }
  };

  return (
    <div className="workspace-page">
      <div className="page-heading">
        <div>
          <h1>Template Mode</h1>
          <p>Mặc định duplicate trước khi sửa để bảo vệ template gốc.</p>
        </div>
        <div className="page-actions">
          <Button tooltip={{ vi: "Lưu các thay đổi template qua API pycapcut.", en: "Save template changes through the pycapcut API." }} variant="primary" onClick={() => void save()}>
            <Save size={16} /> Save
          </Button>
        </div>
      </div>
      <Panel className="page-toolbar">
        <Field label="Draft folder"><Input value={folder} onChange={(event) => setFolder(event.target.value)} /></Field>
        <Field label="Template name"><Input value={name} onChange={(event) => setName(event.target.value)} /></Field>
        <Button tooltip={{ vi: "Load template và inspect metadata.", en: "Load the template and inspect metadata." }} onClick={() => void load()}>
          <Search size={15} /> Load
        </Button>
        <Button tooltip={{ vi: "Nhân bản template trước khi sửa.", en: "Duplicate the template before editing." }} variant="primary" disabled={!name} onClick={() => void duplicate()}>
          <Copy size={15} /> Duplicate first
        </Button>
      </Panel>
      <div className="template-grid">
        <Panel title="Imported tracks">
          <div className="simple-table">
            <div className="simple-table-head"><span>#</span><span>Name</span><span>Type</span></div>
            {tracks.map((track) => <div key={track.index}><span>{track.index}</span><span>{track.name}</span><span>{track.type}</span></div>)}
          </div>
          <pre className="inspect-output template-inspect">{inspect || "Load a template to inspect sticker, bubble and flower-text metadata."}</pre>
        </Panel>
        <div className="template-actions">
          <Panel title="Replace material" className="form-card">
            <Field label="Mode">
              <Select value={replace.mode} onChange={(event) => updateReplace("mode", event.target.value)}>
                <option value="name">By material name</option>
                <option value="segment">By segment</option>
              </Select>
            </Field>
            {replace.mode === "name" ? (
              <Field label="Material name"><Input value={replace.material_name} onChange={(event) => updateReplace("material_name", event.target.value)} /></Field>
            ) : (
              <>
                <Field label="Track kind"><Select value={replace.track_kind} onChange={(event) => updateReplace("track_kind", event.target.value)}>{["video", "audio"].map((item) => <option key={item}>{item}</option>)}</Select></Field>
                <Field label="Track index"><Input type="number" value={replace.track_index} onChange={(event) => updateReplace("track_index", Number(event.target.value))} /></Field>
                <Field label="Segment index"><Input type="number" value={replace.segment_index} onChange={(event) => updateReplace("segment_index", Number(event.target.value))} /></Field>
                <Field label="Source range"><div className="input-pair"><Input value={replace.source_start} onChange={(event) => updateReplace("source_start", event.target.value)} /><Input value={replace.source_duration} placeholder="duration" onChange={(event) => updateReplace("source_duration", event.target.value)} /></div></Field>
                <Field label="Shrink mode"><Select value={replace.shrink} onChange={(event) => updateReplace("shrink", event.target.value)}><option>cut_head</option><option>cut_tail</option><option>cut_tail_align</option><option>shrink</option></Select></Field>
                <Field label="Extend fallback"><Input value={replace.extend_modes} onChange={(event) => updateReplace("extend_modes", event.target.value)} /></Field>
              </>
            )}
            <Field label="New media path"><Input value={replace.path} onChange={(event) => updateReplace("path", event.target.value)} /></Field>
            <Field label="Material kind"><Select value={replace.kind} onChange={(event) => updateReplace("kind", event.target.value)}><option>video</option><option>image</option><option>audio</option></Select></Field>
            <label className="switch-row"><span>Replace crop</span><input type="checkbox" checked={replace.replace_crop} onChange={(event) => updateReplace("replace_crop", event.target.checked)} /></label>
            <Button tooltip={{ vi: "Thay material bằng API template hiện có.", en: "Replace material through the existing template API." }} variant="primary" onClick={() => void replaceMaterial()}>
              <FilePenLine size={15} /> Replace material
            </Button>
          </Panel>
          <Panel title="Replace text" className="form-card">
            <Field label="Track index"><Input type="number" value={text.track_index} onChange={(event) => setText((current) => ({ ...current, track_index: Number(event.target.value) }))} /></Field>
            <Field label="Segment index"><Input type="number" value={text.segment_index} onChange={(event) => setText((current) => ({ ...current, segment_index: Number(event.target.value) }))} /></Field>
            <Field label="Text"><textarea className="input" value={text.text} onChange={(event) => setText((current) => ({ ...current, text: event.target.value }))} /></Field>
            <label className="switch-row"><span>Recalculate style</span><input type="checkbox" checked={text.recalc_style} onChange={(event) => setText((current) => ({ ...current, recalc_style: event.target.checked }))} /></label>
            <Button tooltip={{ vi: "Thay nội dung text; phân tách nhiều giá trị bằng dòng ---.", en: "Replace text; separate multiple values with a --- line." }} onClick={() => void replaceText()}>
              <Import size={15} /> Replace text
            </Button>
          </Panel>
          <Panel title="Import track" className="form-card">
            <Field label="Source folder"><Input value={trackImport.source_folder} onChange={(event) => setTrackImport((current) => ({ ...current, source_folder: event.target.value }))} /></Field>
            <Field label="Source draft"><Input value={trackImport.source_name} onChange={(event) => setTrackImport((current) => ({ ...current, source_name: event.target.value }))} /></Field>
            <Field label="Track kind"><Select value={trackImport.track_kind} onChange={(event) => setTrackImport((current) => ({ ...current, track_kind: event.target.value }))}>{["video", "audio", "text", "sticker", "effect", "filter"].map((item) => <option key={item}>{item}</option>)}</Select></Field>
            <Field label="Track index"><Input type="number" value={trackImport.track_index} onChange={(event) => setTrackImport((current) => ({ ...current, track_index: Number(event.target.value) }))} /></Field>
            <Field label="Offset"><Input value={trackImport.offset} onChange={(event) => setTrackImport((current) => ({ ...current, offset: event.target.value }))} /></Field>
            <Field label="New name"><Input value={trackImport.new_name} onChange={(event) => setTrackImport((current) => ({ ...current, new_name: event.target.value }))} /></Field>
            <Field label="Relative index"><Input type="number" value={trackImport.relative_index} onChange={(event) => setTrackImport((current) => ({ ...current, relative_index: Number(event.target.value) }))} /></Field>
            <Button tooltip={{ vi: "Import rãnh từ một template khác vào target đang mở.", en: "Import a track from another template into the loaded target." }} onClick={() => void importTrack()}>
              <Import size={15} /> Import track
            </Button>
          </Panel>
        </div>
      </div>
    </div>
  );
}
