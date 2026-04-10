import { Alert, AlertDescription } from "@/components/ui/alert";
import type { Alert as AlertType } from "@/lib/types";

interface AlertListProps {
  alerts: AlertType[];
}

export function AlertList({ alerts }: AlertListProps) {
  const warnings = alerts.filter((a) => a.severity === "warning");
  const infos = alerts.filter((a) => a.severity === "info");

  if (alerts.length === 0) {
    return (
      <p className="text-sm text-muted-foreground">
        Sin alertas de consistencia.
      </p>
    );
  }

  return (
    <div className="space-y-2">
      {warnings.map((alert, i) => (
        <Alert key={`w-${i}`} variant="destructive">
          <AlertDescription>
            {alert.document && (
              <span className="font-medium">{alert.document}: </span>
            )}
            {alert.message}
          </AlertDescription>
        </Alert>
      ))}
      {infos.map((alert, i) => (
        <Alert key={`i-${i}`}>
          <AlertDescription>{alert.message}</AlertDescription>
        </Alert>
      ))}
    </div>
  );
}
