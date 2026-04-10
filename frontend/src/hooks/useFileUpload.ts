"use client";

/**
 * Wraps the upload API call with loading and error state.
 * Returns the job ID on success, or null on failure.
 */

import { useCallback, useState } from "react";
import { uploadFiles } from "@/lib/api";

export function useFileUpload() {
  const [isUploading, setIsUploading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const upload = useCallback(async (files: File[]): Promise<string | null> => {
    setIsUploading(true);
    setError(null);
    try {
      const { job_id } = await uploadFiles(files);
      return job_id;
    } catch (err) {
      setError(err instanceof Error ? err.message : "Error al subir archivos");
      return null;
    } finally {
      setIsUploading(false);
    }
  }, []);

  return { upload, isUploading, error };
}
