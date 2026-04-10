"use client";

import { cn } from "@/lib/utils";
import { PIPELINE_STAGES, type JobStage } from "@/lib/types";

interface ProgressTrackerProps {
  currentStage: JobStage;
  detail: string;
}

export function ProgressTracker({ currentStage, detail }: ProgressTrackerProps) {
  const currentIndex = PIPELINE_STAGES.findIndex(
    (s) => s.key === currentStage
  );

  return (
    <div className="space-y-6">
      <div className="space-y-2">
        {PIPELINE_STAGES.map((stage, i) => {
          const isActive = stage.key === currentStage;
          const isDone = currentIndex > i;

          return (
            <div key={stage.key} className="flex items-center gap-3">
              <div
                className={cn(
                  "flex h-7 w-7 shrink-0 items-center justify-center rounded-full text-xs font-medium",
                  isDone && "bg-primary text-primary-foreground",
                  isActive && "bg-primary/20 text-primary ring-2 ring-primary",
                  !isDone && !isActive && "bg-muted text-muted-foreground"
                )}
              >
                {isDone ? (
                  <svg
                    width="14"
                    height="14"
                    viewBox="0 0 24 24"
                    fill="none"
                    stroke="currentColor"
                    strokeWidth="3"
                    strokeLinecap="round"
                    strokeLinejoin="round"
                  >
                    <polyline points="20 6 9 17 4 12" />
                  </svg>
                ) : (
                  i + 1
                )}
              </div>
              <span
                className={cn(
                  "text-sm",
                  isActive && "font-medium",
                  !isDone && !isActive && "text-muted-foreground"
                )}
              >
                {stage.label}
              </span>
              {isActive && (
                <span className="ml-auto text-xs text-muted-foreground animate-pulse">
                  En progreso...
                </span>
              )}
            </div>
          );
        })}
      </div>

      {detail && (
        <p className="text-sm text-muted-foreground text-center">{detail}</p>
      )}
    </div>
  );
}
