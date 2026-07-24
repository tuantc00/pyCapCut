import { createContext, useContext, type ReactNode } from "react";
import type { Language } from "./types";

const messages = {
  vi: {
    editor: "Biên tập",
    drafts: "Draft",
    batch: "Tạo hàng loạt",
    templates: "Template",
    export: "Xuất video",
    media: "Thư viện",
    timeline: "Timeline",
    properties: "Thuộc tính",
    importMedia: "Nhập media",
    createDraft: "Tạo Draft",
    validate: "Kiểm tra",
    undo: "Hoàn tác",
    redo: "Làm lại",
    jobs: "Tác vụ & Nhật ký",
    ready: "Sẵn sàng",
    search: "Tìm media...",
    sourcePreview: "Xem trước nguồn",
    noSelection: "Chọn track hoặc segment để chỉnh thuộc tính",
    project: "Dự án",
    settings: "Cài đặt",
    help: "Trợ giúp"
  },
  en: {
    editor: "Editor",
    drafts: "Drafts",
    batch: "Batch",
    templates: "Templates",
    export: "Export",
    media: "Media",
    timeline: "Timeline",
    properties: "Properties",
    importMedia: "Import media",
    createDraft: "Create Draft",
    validate: "Validate",
    undo: "Undo",
    redo: "Redo",
    jobs: "Jobs & Log",
    ready: "Ready",
    search: "Search media...",
    sourcePreview: "Source Preview",
    noSelection: "Select a track or segment to edit its properties",
    project: "Project",
    settings: "Settings",
    help: "Help"
  }
} as const;

type MessageKey = keyof (typeof messages)["vi"];
const I18nContext = createContext<{ language: Language; t: (key: MessageKey) => string }>({
  language: "vi",
  t: (key) => messages.vi[key]
});

export function I18nProvider({
  language,
  children
}: {
  language: Language;
  children: ReactNode;
}) {
  return (
    <I18nContext.Provider value={{ language, t: (key) => messages[language][key] }}>
      {children}
    </I18nContext.Provider>
  );
}

export const useI18n = () => useContext(I18nContext);
