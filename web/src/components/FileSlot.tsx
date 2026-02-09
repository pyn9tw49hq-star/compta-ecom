"use client";

import { memo } from "react";
import { CircleCheck, Circle, X } from "lucide-react";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import { formatSize } from "@/lib/utils";
import type { UploadedFile } from "@/lib/types";

interface FileSlotProps {
  slotKey: string;
  pattern: string;
  patternHuman: string;
  isRequired: boolean;
  matchedFile: UploadedFile | null;
  showMissingWarning: boolean;
  onRemoveFile?: () => void;
}

/**
 * Displays a single file slot in one of three variants:
 * filled, empty-required, or empty-optional.
 */
const FileSlot = memo(function FileSlot({
  patternHuman,
  isRequired,
  matchedFile,
  showMissingWarning,
  onRemoveFile,
}: FileSlotProps) {
  // Variant: filled
  if (matchedFile) {
    return (
      <div className="flex items-center gap-3 py-1.5">
        <CircleCheck className="h-4 w-4 text-green-600 shrink-0" aria-hidden="true" />
        <span className="text-sm font-medium truncate">{matchedFile.file.name}</span>
        <span className="text-xs text-muted-foreground shrink-0">
          {formatSize(matchedFile.file.size)}
        </span>
        {onRemoveFile && (
          <Button
            variant="ghost"
            size="icon"
            className="h-7 w-7 shrink-0 ml-auto"
            onClick={onRemoveFile}
            aria-label={`Retirer ${matchedFile.file.name}`}
          >
            <X className="h-4 w-4" />
          </Button>
        )}
      </div>
    );
  }

  // Variant: empty-required
  if (isRequired) {
    return (
      <div className="flex items-center gap-3 py-1.5">
        <Circle className="h-4 w-4 text-muted-foreground/40 shrink-0" aria-hidden="true" />
        <span className="text-sm text-muted-foreground">{patternHuman}</span>
        {showMissingWarning ? (
          <Badge variant="outline" className="bg-amber-50 text-amber-700 border-amber-300">
            MANQUANT
          </Badge>
        ) : (
          <Badge variant="outline">obligatoire</Badge>
        )}
      </div>
    );
  }

  // Variant: empty-optional
  return (
    <div className="flex items-center gap-3 py-1.5">
      <Circle className="h-4 w-4 text-muted-foreground/40 shrink-0" aria-hidden="true" />
      <span className="text-sm text-muted-foreground">{patternHuman}</span>
      <Badge variant="outline">optionnel</Badge>
    </div>
  );
});

export default FileSlot;
export type { FileSlotProps };
