import { Badge } from "@/components/ui/badge";
import { DOC_TYPE_LABELS } from "@/lib/types";

interface MissingDocsProps {
  missingTypes: string[];
}

export function MissingDocs({ missingTypes }: MissingDocsProps) {
  if (missingTypes.length === 0) {
    return (
      <p className="text-sm text-muted-foreground">
        Todos los documentos requeridos est&aacute;n presentes.
      </p>
    );
  }

  return (
    <div className="space-y-2">
      <p className="text-sm text-muted-foreground">
        Documentos no encontrados en el lote:
      </p>
      <div className="flex flex-wrap gap-2">
        {missingTypes.map((type) => (
          <Badge key={type} variant="outline" className="text-amber-700 border-amber-300">
            {DOC_TYPE_LABELS[type] || type}
          </Badge>
        ))}
      </div>
    </div>
  );
}
