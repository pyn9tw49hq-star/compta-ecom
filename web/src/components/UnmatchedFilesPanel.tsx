"use client";

import { FileQuestion, CircleAlert, X } from "lucide-react";
import { Card } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { suggestRename, CHANNEL_KEYWORDS } from "@/lib/channels";
import type { UploadedFile, ChannelConfig, FileSlotConfig } from "@/lib/types";

interface UnmatchedFilesPanelProps {
  unmatchedFiles: UploadedFile[];
  channelConfig: ChannelConfig[];
  missingSlots: { channel: string; slot: FileSlotConfig }[];
  onRemoveFile: (index: number) => void;
  onOpenHelp: () => void;
}

function getSuggestionInfo(
  filename: string,
  missingSlots: { channel: string; slot: FileSlotConfig }[],
  channelConfig: ChannelConfig[],
): { suggestion: string; channelLabel: string } | null {
  const suggestion = suggestRename(filename, missingSlots);
  if (!suggestion) return null;
  const lower = filename.toLowerCase();
  for (const [channelKey, keywords] of Object.entries(CHANNEL_KEYWORDS)) {
    if (keywords.some((kw) => lower.includes(kw))) {
      const config = channelConfig.find((c) => c.key === channelKey);
      if (config) {
        return { suggestion, channelLabel: config.meta.label };
      }
    }
  }
  return null;
}

export default function UnmatchedFilesPanel({
  unmatchedFiles,
  channelConfig,
  missingSlots,
  onRemoveFile,
  onOpenHelp,
}: UnmatchedFilesPanelProps) {
  if (unmatchedFiles.length === 0) return null;

  const headerText =
    unmatchedFiles.length === 1
      ? "1 fichier non reconnu"
      : `${unmatchedFiles.length} fichiers non reconnus`;

  return (
    <Card className="border-amber-300 bg-amber-50 text-amber-700 dark:border-amber-700 dark:bg-amber-950 dark:text-amber-200 p-4">
      <div className="flex items-center gap-2 font-semibold text-sm mb-3">
        <CircleAlert className="h-4 w-4 text-amber-600 dark:text-amber-400" aria-hidden="true" />
        {headerText}
      </div>

      {unmatchedFiles.map((file, index) => {
        const info = getSuggestionInfo(
          file.file.name,
          missingSlots,
          channelConfig,
        );

        return (
          <div key={`${file.file.name}-${index}`}>
            {index > 0 && <hr className="border-amber-200 dark:border-amber-800 my-1" />}
            <div className="flex items-start gap-3 py-2">
              <FileQuestion
                className="h-5 w-5 text-amber-600 dark:text-amber-400 mt-0.5 shrink-0"
                aria-hidden="true"
              />
              <div className="flex-1 min-w-0">
                <span className="font-medium text-sm break-all">
                  {file.file.name}
                </span>
                <div className="text-sm mt-1 ml-8">
                  {info ? (
                    <>
                      Suggestion : renommez-le en {info.suggestion} pour
                      qu&apos;il soit reconnu comme fichier {info.channelLabel}.
                    </>
                  ) : (
                    <>Ce fichier ne correspond à aucun format connu.</>
                  )}
                </div>
              </div>
              <Button
                variant="ghost"
                size="sm"
                onClick={() => onRemoveFile(index)}
                aria-label={`Retirer ${file.file.name}`}
                className="shrink-0 text-amber-700 hover:text-amber-900 hover:bg-amber-100 dark:text-amber-300 dark:hover:text-amber-100 dark:hover:bg-amber-900"
              >
                <X className="h-4 w-4 mr-1" />
                Retirer
              </Button>
            </div>
          </div>
        );
      })}

      <Button
        variant="link"
        onClick={onOpenHelp}
        className="text-amber-800 hover:text-amber-900 dark:text-amber-200 dark:hover:text-amber-100 underline p-0 h-auto text-sm mt-3"
      >
        Voir les formats de noms attendus
      </Button>
    </Card>
  );
}
