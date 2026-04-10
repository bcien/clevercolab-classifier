"use client";

import { use } from "react";
import Link from "next/link";
import { buttonVariants } from "@/components/ui/button";
import {
  Card,
  CardContent,
  CardDescription,
  CardHeader,
  CardTitle,
} from "@/components/ui/card";
import { Separator } from "@/components/ui/separator";
import { ProgressTracker } from "@/components/processing/ProgressTracker";
import { ReportSummary } from "@/components/report/ReportSummary";
import { DocumentTable } from "@/components/report/DocumentTable";
import { AlertList } from "@/components/report/AlertList";
import { MissingDocs } from "@/components/report/MissingDocs";
import { DownloadButton } from "@/components/download/DownloadButton";
import { useJobProgress } from "@/hooks/useJobProgress";

export default function JobPage({
  params,
}: {
  params: Promise<{ id: string }>;
}) {
  const { id } = use(params);
  const { status, error } = useJobProgress(id);

  if (error) {
    return (
      <main className="flex flex-1 flex-col items-center justify-center px-4 py-12">
        <Card className="w-full max-w-lg">
          <CardContent className="pt-6 text-center space-y-4">
            <p className="text-destructive font-medium">Error: {error}</p>
            <Link href="/" className={buttonVariants({ variant: "outline" })}>
              Volver al inicio
            </Link>
          </CardContent>
        </Card>
      </main>
    );
  }

  if (!status) {
    return (
      <main className="flex flex-1 flex-col items-center justify-center px-4 py-12">
        <p className="text-muted-foreground">Cargando...</p>
      </main>
    );
  }

  const isProcessing =
    status.stage !== "complete" && status.stage !== "failed";

  return (
    <main className="flex flex-1 flex-col items-center px-4 py-12">
      <div className="w-full max-w-4xl space-y-6">
        <div className="flex items-center justify-between">
          <div>
            <h1 className="text-2xl font-bold tracking-tight">
              Resultado del procesamiento
            </h1>
            <p className="text-sm text-muted-foreground">Job: {id}</p>
          </div>
          <Link href="/" className={buttonVariants({ variant: "outline", size: "sm" })}>
            Nuevo lote
          </Link>
        </div>

        {/* Processing state */}
        {isProcessing && (
          <Card>
            <CardHeader>
              <CardTitle>Procesando documentos</CardTitle>
              <CardDescription>
                Esto puede tomar entre 10 y 30 segundos...
              </CardDescription>
            </CardHeader>
            <CardContent>
              <ProgressTracker
                currentStage={status.stage}
                detail={status.detail}
              />
            </CardContent>
          </Card>
        )}

        {/* Failed state */}
        {status.stage === "failed" && (
          <Card>
            <CardContent className="pt-6 space-y-4">
              <p className="text-destructive font-medium">
                El procesamiento fall&oacute;.
              </p>
              {status.error && (
                <pre className="text-xs bg-muted p-3 rounded-lg overflow-auto">
                  {status.error}
                </pre>
              )}
              <Link href="/" className={buttonVariants({ variant: "outline" })}>
                Intentar de nuevo
              </Link>
            </CardContent>
          </Card>
        )}

        {/* Complete state — show report */}
        {status.stage === "complete" && status.report && (
          <>
            <ReportSummary report={status.report} />

            <Card>
              <CardHeader>
                <CardTitle>Documentos clasificados</CardTitle>
              </CardHeader>
              <CardContent>
                <DocumentTable documents={status.report.documents_found} />
              </CardContent>
            </Card>

            {status.report.alerts.length > 0 && (
              <Card>
                <CardHeader>
                  <CardTitle>Alertas de consistencia</CardTitle>
                </CardHeader>
                <CardContent>
                  <AlertList alerts={status.report.alerts} />
                </CardContent>
              </Card>
            )}

            {status.report.missing_types.length > 0 && (
              <Card>
                <CardHeader>
                  <CardTitle>Documentos faltantes</CardTitle>
                </CardHeader>
                <CardContent>
                  <MissingDocs missingTypes={status.report.missing_types} />
                </CardContent>
              </Card>
            )}

            <Separator />

            <DownloadButton jobId={id} />
          </>
        )}
      </div>
    </main>
  );
}
