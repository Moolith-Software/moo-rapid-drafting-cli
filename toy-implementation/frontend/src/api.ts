// Tiny typed wrapper around the FastAPI backend.

const BASE = "http://localhost:8000";

export type Change = { path: string; kind: "created" | "edited" | "deleted" };

export type Refinement = {
  refinement_id: number;
  user_request: string;
  file_changes: Change[];
  summary: string;
};

export type Feature = {
  id: number;
  parent_id: number | null;
  code_folder_name: string;
  feature: string;
  file_changes: Change[];
  summary: string;
  refinements: Refinement[];
  status: string;
  progress: string;
  created_at: number;
};

async function post<T>(path: string, body: unknown): Promise<T> {
  const res = await fetch(BASE + path, {
    method: "POST",
    headers: { "content-type": "application/json" },
    body: JSON.stringify(body),
  });
  if (!res.ok) throw new Error(`${res.status}: ${await res.text()}`);
  return res.json();
}

async function get<T>(path: string): Promise<T> {
  const res = await fetch(BASE + path);
  if (!res.ok) throw new Error(`${res.status}: ${await res.text()}`);
  return res.json();
}

export const api = {
  listFeatures: () => get<Feature[]>("/features"),
  getFeature: (id: number) => get<Feature>(`/features/${id}`),
  getStatus: (id: number) =>
    get<{ id: number; status: string; progress: string }>(`/features/${id}/status`),
  initialize: (feature: string, parent_id: number | null = null) =>
    post<Feature>("/features/initialize", { feature, parent_id }),
  add: (id: number) => post<{ id: number; status: string }>("/features/add", { id }),
  refine: (id: number, user_request: string) =>
    post<{ id: number; status: string }>("/features/refine", { id, user_request }),
  previewBase: () => post<{ url: string; port: number }>("/preview/base", {}),
  previewFeature: (id: number) =>
    post<{ url: string; port: number }>(`/features/${id}/preview`, {}),
};
