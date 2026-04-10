"use client";

import { Button } from "@/components/ui/button";

interface FileListProps {
  files: File[];
  onRemove: (index: number) => void;
}

function formatSize(bytes: number): string {
  if (bytes < 1024) return `${bytes} B`;
  if (bytes < 1024 * 1024) return `${(bytes / 1024).toFixed(1)} KB`;
  return `${(bytes / (1024 * 1024)).toFixed(1)} MB`;
}

export function FileList({ files, onRemove }: FileListProps) {
  if (files.length === 0) return null;

  return (
    <ul className="space-y-2">
      {files.map((file, i) => (
        <li
          key={`${file.name}-${file.size}-${i}`}
          className="flex items-center justify-between rounded-lg border px-4 py-3"
        >
          <div className="flex items-center gap-3 min-w-0">
            <svg
              xmlns="http://www.w3.org/2000/svg"
              width="20"
              height="20"
              viewBox="0 0 24 24"
              fill="none"
              stroke="currentColor"
              strokeWidth="2"
              strokeLinecap="round"
              strokeLinejoin="round"
              className="shrink-0 text-red-500"
            >
              <path d="M14.5 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V7.5L14.5 2z" />
              <polyline points="14 2 14 8 20 8" />
            </svg>
            <span className="truncate text-sm font-medium">{file.name}</span>
            <span className="shrink-0 text-xs text-muted-foreground">
              {formatSize(file.size)}
            </span>
          </div>
          <Button
            variant="ghost"
            size="sm"
            onClick={() => onRemove(i)}
            className="shrink-0 text-muted-foreground hover:text-destructive"
          >
            Quitar
          </Button>
        </li>
      ))}
    </ul>
  );
}
