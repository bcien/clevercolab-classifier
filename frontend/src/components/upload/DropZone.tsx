"use client";

import { useCallback, useState } from "react";
import { cn } from "@/lib/utils";

interface DropZoneProps {
  onFilesAdded: (files: File[]) => void;
  disabled?: boolean;
}

export function DropZone({ onFilesAdded, disabled }: DropZoneProps) {
  const [isDragOver, setIsDragOver] = useState(false);

  const handleDrop = useCallback(
    (e: React.DragEvent) => {
      e.preventDefault();
      setIsDragOver(false);
      if (disabled) return;

      const files = Array.from(e.dataTransfer.files).filter(
        (f) => f.type === "application/pdf"
      );
      if (files.length > 0) onFilesAdded(files);
    },
    [onFilesAdded, disabled]
  );

  const handleFileInput = useCallback(
    (e: React.ChangeEvent<HTMLInputElement>) => {
      const files = Array.from(e.target.files || []);
      if (files.length > 0) onFilesAdded(files);
      e.target.value = "";
    },
    [onFilesAdded]
  );

  return (
    <div
      onDragOver={(e) => {
        e.preventDefault();
        if (!disabled) setIsDragOver(true);
      }}
      onDragLeave={() => setIsDragOver(false)}
      onDrop={handleDrop}
      className={cn(
        "relative flex flex-col items-center justify-center gap-3 rounded-xl border-2 border-dashed p-12 transition-colors",
        isDragOver
          ? "border-primary bg-primary/5"
          : "border-muted-foreground/25 hover:border-muted-foreground/50",
        disabled && "pointer-events-none opacity-50"
      )}
    >
      <svg
        xmlns="http://www.w3.org/2000/svg"
        width="48"
        height="48"
        viewBox="0 0 24 24"
        fill="none"
        stroke="currentColor"
        strokeWidth="1.5"
        strokeLinecap="round"
        strokeLinejoin="round"
        className="text-muted-foreground"
      >
        <path d="M14.5 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V7.5L14.5 2z" />
        <polyline points="14 2 14 8 20 8" />
        <path d="M12 18v-6" />
        <path d="m9 15 3-3 3 3" />
      </svg>

      <div className="text-center">
        <p className="text-lg font-medium">
          Arrastra archivos PDF aqu&iacute;
        </p>
        <p className="text-sm text-muted-foreground">
          o haz clic para seleccionar
        </p>
      </div>

      <input
        type="file"
        accept=".pdf,application/pdf"
        multiple
        onChange={handleFileInput}
        disabled={disabled}
        className="absolute inset-0 cursor-pointer opacity-0"
      />
    </div>
  );
}
