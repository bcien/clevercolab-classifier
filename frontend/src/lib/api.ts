/**
 * API client for the Clevercolab Classifier backend.
 *
 * All functions target the FastAPI local dev server by default (localhost:8000).
 * Override with the NEXT_PUBLIC_API_URL env var for production.
 */

import type { JobStatus, OutputFile, UploadResponse } from "./types";

const BASE_URL = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000";

export async function uploadFiles(files: File[]): Promise<UploadResponse> {
  const form = new FormData();
  for (const file of files) {
    form.append("files", file);
  }
  const res = await fetch(`${BASE_URL}/api/upload`, {
    method: "POST",
    body: form,
  });
  if (!res.ok) {
    const body = await res.json().catch(() => ({}));
    throw new Error(body.error || `Upload failed (${res.status})`);
  }
  return res.json();
}

export async function getJobStatus(jobId: string): Promise<JobStatus> {
  const res = await fetch(`${BASE_URL}/api/jobs/${jobId}`);
  if (!res.ok) {
    throw new Error(`Job not found (${res.status})`);
  }
  return res.json();
}

export function getDownloadUrl(jobId: string): string {
  return `${BASE_URL}/api/jobs/${jobId}/download`;
}

export async function getOutputFiles(jobId: string): Promise<OutputFile[]> {
  const res = await fetch(`${BASE_URL}/api/jobs/${jobId}/files`);
  if (!res.ok) return [];
  const data = await res.json();
  return data.files || [];
}
