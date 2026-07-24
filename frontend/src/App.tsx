import * as TooltipPrimitive from "@radix-ui/react-tooltip";
import {
  Boxes,
  Captions,
  ChevronDown,
  Clapperboard,
  FileStack,
  FolderKanban,
  Languages,
  Redo2,
  ShieldCheck,
  Undo2,
  Upload,
  Video
} from "lucide-react";
import { lazy, Suspense, useEffect } from "react";
import { api } from "./api";
import { Button, Input, Notice } from "./components/ui";
import { I18nProvider, useI18n } from "./i18n";
import { useStudio } from "./store";
import type { Job, Workspace } from "./types";

const Editor = lazy(() => import("./workspaces/Editor"));
const DraftManager = lazy(() => import("./workspaces/DraftManager"));
const BatchCreator = lazy(() => import("./workspaces/BatchCreator"));
const TemplateMode = lazy(() => import("./workspaces/TemplateMode"));
const ExportQueue = lazy(() => import("./workspaces/ExportQueue"));

const icons = {
  editor: Clapperboard,
  drafts: FolderKanban,
  batch: Boxes,
  templates: FileStack,
  export: Upload
};

function Shell() {
  const { t } = useI18n();
  const workspace = useStudio((state) => state.workspace);
  const setWorkspace = useStudio((state) => state.setWorkspace);
  const project = useStudio((state) => state.project);
  const mutate = useStudio((state) => state.mutate);
  const undo = useStudio((state) => state.undo);
  const redo = useStudio((state) => state.redo);
  const history = useStudio((state) => state.history);
  const validate = useStudio((state) => state.validate);
  const createDraft = useStudio((state) => state.createDraft);
  const language = useStudio((state) => state.language);
  const setLanguage = useStudio((state) => state.setLanguage);
  const load = useStudio((state) => state.load);
  const setJobs = useStudio((state) => state.setJobs);
  const jobs = useStudio((state) => state.jobs);
  const logsOpen = useStudio((state) => state.logsOpen);
  const toggleLogs = useStudio((state) => state.toggleLogs);
  const busy = useStudio((state) => state.busy);

  useEffect(() => {
    void load();
    void api.jobs().then((result) => setJobs(result.items));
    const protocol = location.protocol === "https:" ? "wss" : "ws";
    let reconnect = 0;
    let socket: WebSocket;
    const connect = () => {
      socket = new WebSocket(`${protocol}://${location.host}/api/v1/jobs/ws`);
      socket.onmessage = (event) => {
        const data = JSON.parse(event.data) as {
          event: string;
          jobs?: Job[];
          job?: Job;
        };
        if (data.jobs) setJobs(data.jobs);
        if (data.job) {
          const current = useStudio.getState().jobs;
          setJobs([...current.filter((item) => item.id !== data.job!.id), data.job]);
        }
      };
      socket.onclose = () => {
        reconnect = window.setTimeout(connect, 1500);
      };
    };
    connect();
    return () => {
      window.clearTimeout(reconnect);
      socket?.close();
    };
  }, [load, setJobs]);

  const workspaces: Workspace[] = ["editor", "drafts", "batch", "templates", "export"];
  const latestJob = jobs.at(-1);

  return (
    <div className="app-shell">
      <aside className="sidebar">
        <div className="brand">
          <Video size={23} />
          <strong>pyCapCut</strong>
        </div>
        <nav>
          {workspaces.map((item) => {
            const Icon = icons[item];
            return (
              <button
                key={item}
                className={workspace === item ? "active" : ""}
                onClick={() => setWorkspace(item)}
                title={t(item)}
              >
                <Icon size={20} />
                <span>{t(item)}</span>
              </button>
            );
          })}
        </nav>
        <button
          className="language"
          onClick={() => setLanguage(language === "vi" ? "en" : "vi")}
          title="Đổi ngôn ngữ / Switch language"
        >
          <Languages size={18} />
          {language.toUpperCase()}
        </button>
      </aside>

      <main className="main">
        <header className="commandbar">
          <div className="project-name">
            <span>{t("project")}</span>
            <Input
              value={project.draft_name}
              onChange={(event) =>
                mutate((draft) => {
                  draft.draft_name = event.target.value;
                })
              }
              aria-label="Draft name"
            />
            <small>
              {project.width} × {project.height} · {project.fps} FPS
            </small>
          </div>
          <div className="command-actions">
            <Button
              tooltip={{ vi: "Hoàn tác thay đổi gần nhất (Ctrl+Z).", en: "Undo the latest change (Ctrl+Z)." }}
              variant="ghost"
              disabled={!history.past.length}
              onClick={undo}
            >
              <Undo2 size={17} /> {t("undo")}
            </Button>
            <Button
              tooltip={{ vi: "Làm lại thay đổi vừa hoàn tác (Ctrl+Y).", en: "Redo the last undone change (Ctrl+Y)." }}
              variant="ghost"
              disabled={!history.future.length}
              onClick={redo}
            >
              <Redo2 size={17} /> {t("redo")}
            </Button>
            <Button
              tooltip={{ vi: "Kiểm tra đường dẫn, thời lượng, overlap và tham số.", en: "Validate paths, ranges, overlap and parameters." }}
              onClick={() => void validate()}
              disabled={busy}
            >
              <ShieldCheck size={17} /> {t("validate")}
            </Button>
            <Button
              tooltip={{ vi: "Tạo thư mục draft CapCut. Không render MP4.", en: "Create a CapCut draft folder. This does not render MP4." }}
              variant="primary"
              onClick={() => void createDraft()}
              disabled={busy}
            >
              <Captions size={17} /> {t("createDraft")}
            </Button>
          </div>
        </header>

        <Notice />
        <div className="workspace">
          <Suspense fallback={<div className="loading">Loading workspace…</div>}>
            {workspace === "editor" && <Editor />}
            {workspace === "drafts" && <DraftManager />}
            {workspace === "batch" && <BatchCreator />}
            {workspace === "templates" && <TemplateMode />}
            {workspace === "export" && <ExportQueue />}
          </Suspense>
        </div>

        <section className={`job-drawer ${logsOpen ? "open" : ""}`}>
          <button className="job-summary" onClick={toggleLogs}>
            <ChevronDown size={16} />
            <strong>{t("jobs")}</strong>
            <span className={`status-dot ${latestJob?.status ?? "ready"}`} />
            <span>{latestJob ? `${latestJob.kind}: ${latestJob.status}` : t("ready")}</span>
            {latestJob?.total ? (
              <span className="job-progress">
                {latestJob.current}/{latestJob.total}
              </span>
            ) : null}
          </button>
          {logsOpen && (
            <div className="job-logs">
              {jobs.flatMap((job) =>
                job.logs.map((log, index) => (
                  <div key={`${job.id}-${index}`} className={`log-${log.level}`}>
                    <time>{new Date(log.time).toLocaleTimeString()}</time>
                    <span>{log.message}</span>
                  </div>
                ))
              )}
              {!jobs.some((job) => job.logs.length) && <p>No logs</p>}
            </div>
          )}
        </section>
      </main>
    </div>
  );
}

export function App() {
  const language = useStudio((state) => state.language);
  return (
    <TooltipPrimitive.Provider>
      <I18nProvider language={language}>
        <Shell />
      </I18nProvider>
    </TooltipPrimitive.Provider>
  );
}
