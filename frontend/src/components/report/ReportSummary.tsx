import { Card, CardContent } from "@/components/ui/card";
import type { Report } from "@/lib/types";

interface ReportSummaryProps {
  report: Report;
}

export function ReportSummary({ report }: ReportSummaryProps) {
  const warnings = report.alerts.filter((a) => a.severity === "warning").length;

  return (
    <div className="grid grid-cols-2 gap-4 sm:grid-cols-4">
      <StatCard
        label="Archivos ingresados"
        value={report.total_files_ingested}
      />
      <StatCard
        label="Documentos encontrados"
        value={report.documents_found.length}
      />
      <StatCard
        label="Alertas"
        value={warnings}
        variant={warnings > 0 ? "warning" : "default"}
      />
      <StatCard
        label="Docs. faltantes"
        value={report.missing_types.length}
        variant={report.missing_types.length > 0 ? "muted" : "default"}
      />
    </div>
  );
}

const VALUE_CLASSES: Record<string, string> = {
  default: "text-2xl font-bold",
  warning: "text-2xl font-bold text-amber-600",
  muted: "text-2xl font-bold text-muted-foreground",
};

function StatCard({
  label,
  value,
  variant = "default",
}: {
  label: string;
  value: number;
  variant?: "default" | "warning" | "muted";
}) {
  return (
    <Card>
      <CardContent className="pt-4 pb-4">
        <p className="text-xs text-muted-foreground">{label}</p>
        <p className={VALUE_CLASSES[variant]}>{value}</p>
      </CardContent>
    </Card>
  );
}
