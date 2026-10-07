export interface PageInfo {
  width_mm: number;
  height_mm: number;
  rotation: number;
}

export interface DocumentInfo {
  document_id: string;
  filename: string;
  page_count: number;
  pages: PageInfo[];
}

export interface ImposeOptions {
  paper: string;
  binding: "left" | "right";
  signature_pages: number;
  duplex: "long-edge" | "short-edge";
  margin_mm: number;
}

export interface SheetMeta {
  signature: number;
  front: (number | null)[];
  back: (number | null)[];
}

export interface ImposeResult {
  job_id: string;
  sheet_count: number;
  signature_count: number;
  blank_count: number;
  sheets: SheetMeta[];
}

export class ApiError extends Error {
  status: number;
  constructor(status: number, message: string) {
    super(message);
    this.status = status;
  }
}

async function parseError(res: Response): Promise<never> {
  let message = `请求失败（${res.status}）`;
  try {
    const body = await res.json();
    if (typeof body.detail === "string") message = body.detail;
  } catch {
    /* 保留默认信息 */
  }
  throw new ApiError(res.status, message);
}

export async function uploadDocument(file: File): Promise<DocumentInfo> {
  const form = new FormData();
  form.append("file", file);
  const res = await fetch("/api/documents", { method: "POST", body: form });
  if (!res.ok) await parseError(res);
  return res.json();
}

export async function impose(
  documentId: string,
  options: ImposeOptions,
): Promise<ImposeResult> {
  const res = await fetch(`/api/documents/${documentId}/impose`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(options),
  });
  if (!res.ok) await parseError(res);
  return res.json();
}

export function previewUrl(jobId: string, sheet: number, side: "front" | "back"): string {
  return `/api/jobs/${jobId}/previews/${sheet}/${side}`;
}

export function downloadUrl(jobId: string): string {
  return `/api/jobs/${jobId}/download`;
}
