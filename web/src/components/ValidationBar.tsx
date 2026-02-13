"use client";

import { Loader2 } from "lucide-react";
import { Button } from "@/components/ui/button";
import type { ChannelStatus } from "@/lib/types";

interface ValidationBarProps {
  channelStatuses: ChannelStatus[];
  hasFiles: boolean;
  isLoading: boolean;
  onGenerate: () => void;
  disabled?: boolean;
}

type ValidationState = "no-files" | "all-complete" | "partial" | "none-complete";

export default function ValidationBar({
  channelStatuses,
  hasFiles,
  isLoading,
  onGenerate,
  disabled = false,
}: ValidationBarProps) {
  const activeChannels = channelStatuses.filter(
    (s) => s.uploadedRequiredCount > 0 || s.isComplete,
  );
  const completeChannels = activeChannels.filter((s) => s.isComplete);
  const incompleteChannels = activeChannels.filter((s) => !s.isComplete);
  const hasCompleteChannel = completeChannels.length > 0;

  const state: ValidationState = !hasFiles
    ? "no-files"
    : activeChannels.length === 0
      ? "none-complete"
      : completeChannels.length === activeChannels.length
        ? "all-complete"
        : hasCompleteChannel
          ? "partial"
          : "none-complete";

  const isDisabled = !hasFiles || isLoading || !hasCompleteChannel || disabled;

  return (
    <div className="rounded-lg border p-4 space-y-3">
      <Button onClick={onGenerate} disabled={isDisabled} className="w-full">
        {isLoading ? (
          <>
            <Loader2 className="mr-2 h-4 w-4 animate-spin" />
            Traitement en cours...
          </>
        ) : (
          "Générer les écritures"
        )}
      </Button>

      <div className="space-y-1 mt-2" aria-live="polite">
        {state === "all-complete" &&
          completeChannels.map((channel) => (
            <div
              key={channel.channelKey}
              className="flex items-center gap-1.5 text-sm text-green-700 dark:text-green-300"
            >
              ✅ {channel.label} sera traité{channel.activeMode ? ` (${channel.activeMode.toLowerCase()})` : ""}
            </div>
          ))}

        {state === "partial" && (
          <>
            {completeChannels.map((channel) => (
              <div
                key={channel.channelKey}
                className="flex items-center gap-1.5 text-sm text-green-700 dark:text-green-300"
              >
                ✅ {channel.label} sera traité{channel.activeMode ? ` (${channel.activeMode.toLowerCase()})` : ""}
              </div>
            ))}
            {incompleteChannels.map((channel) => {
              const missingCount =
                channel.requiredCount - channel.uploadedRequiredCount;
              const missingText =
                missingCount === 1
                  ? "1 fichier manquant"
                  : `${missingCount} fichiers manquants`;
              return (
                <div
                  key={channel.channelKey}
                  className="flex items-center gap-1.5 text-sm text-amber-700 dark:text-amber-300"
                >
                  ⚠ {channel.label} sera ignoré ({missingText})
                </div>
              );
            })}
          </>
        )}

        {state === "none-complete" && (
          <p className="text-sm text-muted-foreground">
            Aucun canal n&apos;est complet. Ajoutez les fichiers manquants pour
            pouvoir lancer le traitement.
          </p>
        )}
      </div>
    </div>
  );
}
