"use client";

import { buttonVariants } from "@/components/ui/button";
import { cn } from "@/lib/utils";
import { getDownloadUrl } from "@/lib/api";

interface DownloadButtonProps {
  jobId: string;
}

export function DownloadButton({ jobId }: DownloadButtonProps) {
  return (
    <a
      href={getDownloadUrl(jobId)}
      download
      className={cn(buttonVariants({ size: "lg" }), "w-full")}
    >
      Descargar ZIP
    </a>
  );
}
