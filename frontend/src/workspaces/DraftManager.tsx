import { Copy, FolderOpen, RefreshCw, Search, Trash2 } from "lucide-react";
import { useEffect, useState } from "react";
import { api } from "../api";
import { Button, Field, Input, Panel } from "../components/ui";
import { useStudio } from "../store";

const encoded = (value: string) => encodeURIComponent(value);

export default function DraftManager() {
  const projectFolder = useStudio((state) => state.project.draft_folder);
  const mutate = useStudio((state) => state.mutate);
  const language = useStudio((state) => state.language);
  const setNotice = useStudio((state) => state.setNotice);
  const [folder, setFolder] = useState(projectFolder);
  const [items, setItems] = useState<string[]>([]);
  const [selected, setSelected] = useState("");
  const [inspect, setInspect] = useState("");
  const [query, setQuery] = useState("");

  const refresh = async () => {
    if (!folder) return;
    try {
      const result = await api.get<{ items: string[] }>(`/drafts?folder=${encoded(folder)}`);
      setItems(result.items);
      mutate((project) => {
        project.draft_folder = folder;
      });
    } catch (error) {
      setNotice({ kind: "error", text: String(error) });
    }
  };
  useEffect(() => {
    if (folder) void refresh();
    // Refresh only when opening this workspace.
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  const browse = async () => {
    const path = await window.pywebview?.api.select_folder();
    if (path) setFolder(path);
  };
  const inspectSelected = async (name: string) => {
    setSelected(name);
    try {
      const result = await api.get<{ text: string }>(
        `/drafts/${encoded(name)}/inspect?folder=${encoded(folder)}`
      );
      setInspect(result.text);
    } catch (error) {
      setNotice({ kind: "error", text: String(error) });
    }
  };
  const duplicate = async () => {
    if (!selected) return;
    const target = window.prompt(
      language === "vi" ? "Tên draft mới" : "New draft name",
      `${selected}_copy`
    );
    if (!target) return;
    try {
      await api.post(`/drafts/${encoded(selected)}/duplicate`, {
        folder,
        target,
        overwrite: false
      });
      setNotice({ kind: "success", text: `${selected} → ${target}` });
      await refresh();
    } catch (error) {
      setNotice({ kind: "error", text: String(error) });
    }
  };
  const remove = async () => {
    if (!selected) return;
    const confirmName = window.prompt(
      language === "vi"
        ? `Nhập chính xác "${selected}" để xóa`
        : `Type "${selected}" exactly to delete`
    );
    if (confirmName !== selected) return;
    try {
      await api.delete(
        `/drafts/${encoded(selected)}?folder=${encoded(folder)}&confirm=${encoded(confirmName)}`
      );
      setSelected("");
      setInspect("");
      await refresh();
    } catch (error) {
      setNotice({ kind: "error", text: String(error) });
    }
  };

  return (
    <div className="workspace-page">
      <div className="page-heading">
        <div>
          <h1>Draft Manager</h1>
          <p>Quản lý các thư mục CapCut draft mà không chỉnh trực tiếp JSON.</p>
        </div>
        <Button
          tooltip={{ vi: "Mở thư mục draft trong Explorer.", en: "Open the draft folder in Explorer." }}
          onClick={() => void api.post("/system/open-path", { path: folder })}
        >
          <FolderOpen size={16} /> Show folder
        </Button>
      </div>
      <Panel className="page-toolbar">
        <Field label="Thư mục Draft / Folder">
          <div className="input-action">
            <Input value={folder} onChange={(event) => setFolder(event.target.value)} />
            <Button
              tooltip={{ vi: "Chọn thư mục CapCut Drafts.", en: "Select the CapCut Drafts folder." }}
              onClick={() => void browse()}
            >
              …
            </Button>
          </div>
        </Field>
        <Button
          tooltip={{ vi: "Đọc lại danh sách draft trong thư mục.", en: "Reload drafts from the folder." }}
          variant="primary"
          onClick={() => void refresh()}
        >
          <RefreshCw size={16} /> Refresh
        </Button>
      </Panel>
      <div className="split-page">
        <Panel
          title={`Drafts (${items.length})`}
          actions={
            <div className="table-actions">
              <Button tooltip={{ vi: "Nhân bản draft được chọn.", en: "Duplicate the selected draft." }} disabled={!selected} onClick={() => void duplicate()}>
                <Copy size={15} />
              </Button>
              <Button tooltip={{ vi: "Xóa draft sau khi xác nhận đúng tên.", en: "Delete after exact-name confirmation." }} variant="danger" disabled={!selected} onClick={() => void remove()}>
                <Trash2 size={15} />
              </Button>
            </div>
          }
        >
          <div className="filter-box">
            <Search size={15} />
            <Input value={query} onChange={(event) => setQuery(event.target.value)} placeholder="Search drafts…" />
          </div>
          <div className="draft-list">
            {items
              .filter((item) => item.toLowerCase().includes(query.toLowerCase()))
              .map((item) => (
                <button key={item} className={selected === item ? "selected" : ""} onClick={() => void inspectSelected(item)}>
                  <FolderOpen size={16} />
                  <span>{item}</span>
                </button>
              ))}
          </div>
        </Panel>
        <Panel title={selected ? `Metadata · ${selected}` : "Metadata"}>
          <pre className="inspect-output">{inspect || "Chọn một draft để xem metadata / Select a draft"}</pre>
        </Panel>
      </div>
    </div>
  );
}
