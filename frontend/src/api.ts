import type { ApiError, Job, MaterialDTO, ProjectDTO } from "./types";

export class StudioApiError extends Error {
  payload: ApiError;

  constructor(payload: ApiError) {
    super(payload.message_vi || payload.message_en || payload.error_code);
    this.payload = payload;
  }
}

async function request<T>(path: string, init?: RequestInit): Promise<T> {
  const response = await fetch(`/api/v1${path}`, {
    credentials: "same-origin",
    headers:
      init?.body instanceof FormData
        ? init.headers
        : { "Content-Type": "application/json", ...init?.headers },
    ...init
  });
  if (!response.ok) {
    let payload: ApiError;
    try {
      payload = (await response.json()) as ApiError;
    } catch {
      payload = {
        error_code: `http_${response.status}`,
        message_vi: response.statusText,
        message_en: response.statusText
      };
    }
    throw new StudioApiError(payload);
  }
  return (await response.json()) as T;
}

export const api = {
  get: <T>(path: string) => request<T>(path),
  post: <T>(path: string, body?: unknown) =>
    request<T>(path, {
      method: "POST",
      body: body === undefined ? undefined : JSON.stringify(body)
    }),
  put: <T>(path: string, body: unknown) =>
    request<T>(path, { method: "PUT", body: JSON.stringify(body) }),
  delete: <T>(path: string) => request<T>(path, { method: "DELETE" }),
  project: () => request<ProjectDTO>("/project"),
  saveProject: (project: ProjectDTO, dirty = true) =>
    request<ProjectDTO>(`/project?dirty=${dirty}`, {
      method: "PUT",
      body: JSON.stringify(project)
    }),
  validate: (project: ProjectDTO) =>
    request<{ valid: boolean; errors: ApiError[] }>("/project/validate", {
      method: "POST",
      body: JSON.stringify(project)
    }),
  createDraft: (project: ProjectDTO) =>
    request<{ path: string }>("/project/create", {
      method: "POST",
      body: JSON.stringify(project)
    }),
  registerMedia: (path: string, kind: string) =>
    request<MaterialDTO>("/media/register", {
      method: "POST",
      body: JSON.stringify({ path, kind })
    }),
  uploadMedia: async (file: File, kind: string) => {
    const data = new FormData();
    data.append("file", file);
    return request<MaterialDTO>(`/media/upload?kind=${kind}`, {
      method: "POST",
      body: data
    });
  },
  jobs: () => request<{ items: Job[] }>("/jobs")
};
