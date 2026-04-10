"use client";

import { useCallback, useState } from "react";
import { useRouter } from "next/navigation";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { DropZone } from "@/components/upload/DropZone";
import { FileList } from "@/components/upload/FileList";
import { useFileUpload } from "@/hooks/useFileUpload";

export default function UploadPage() {
  const router = useRouter();
  const [files, setFiles] = useState<File[]>([]);
  const { upload, isUploading, error } = useFileUpload();

  const addFiles = useCallback((newFiles: File[]) => {
    setFiles((prev) => [...prev, ...newFiles]);
  }, []);

  const removeFile = useCallback((index: number) => {
    setFiles((prev) => prev.filter((_, i) => i !== index));
  }, []);

  const handleSubmit = async () => {
    if (files.length === 0) return;
    const jobId = await upload(files);
    if (jobId) {
      router.push(`/jobs/${jobId}`);
    }
  };

  return (
    <main className="flex flex-1 flex-col items-center justify-center px-4 py-12">
      <div className="w-full max-w-2xl space-y-6">
        <div className="text-center space-y-2">
          <h1 className="text-3xl font-bold tracking-tight">
            Clevercolab Classifier
          </h1>
          <p className="text-muted-foreground">
            Sube documentos de comercio exterior para clasificar, validar y
            empaquetar autom&aacute;ticamente.
          </p>
        </div>

        <Card>
          <CardHeader>
            <CardTitle>Subir documentos</CardTitle>
          </CardHeader>
          <CardContent className="space-y-4">
            <DropZone onFilesAdded={addFiles} disabled={isUploading} />
            <FileList files={files} onRemove={removeFile} />

            {error && (
              <p className="text-sm text-destructive">{error}</p>
            )}

            <Button
              onClick={handleSubmit}
              disabled={files.length === 0 || isUploading}
              className="w-full"
              size="lg"
            >
              {isUploading ? "Subiendo..." : "Procesar documentos"}
            </Button>
          </CardContent>
        </Card>

        <p className="text-center text-xs text-muted-foreground">
          Solo archivos PDF. Los documentos se procesan localmente y no se
          almacenan en la nube.
        </p>
      </div>
    </main>
  );
}
