"use client";

import { ArrowRight, CheckCircle2, Loader2, Settings } from "lucide-react";
import { Button } from "@/components/ui/button";
import { useNewDesign } from "@/hooks/useNewDesign";
import type { ChannelStatus } from "@/lib/types";

interface ValidationBarProps {
  channelStatuses: ChannelStatus[];
  hasFiles: boolean;
  isLoading: boolean;
  onGenerate: () => void;
  disabled?: boolean;
  onOpenSettings?: () => void;
}

type ValidationState = "no-files" | "all-complete" | "partial" | "none-complete";

export default function ValidationBar({
  channelStatuses,
  hasFiles,
  isLoading,
  onGenerate,
  disabled = false,
  onOpenSettings,
}: ValidationBarProps) {
  const isV2 = useNewDesign();
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

  if (isV2) {
    const readyCount = completeChannels.length;
    const readyLabel = readyCount <= 1
      ? `${readyCount} canal prêt`
      : `${readyCount} canaux prêts`;

    return (
      <div className="rounded-xl border bg-card p-4 flex items-center justify-between">
        {/* Status text */}
        <div className="flex items-center gap-2 text-sm font-semibold">
          {readyCount > 0 ? (
            <>
              <CheckCircle2 className="h-4 w-4 text-green-500" aria-hidden="true" />
              <span>{readyLabel}</span>
            </>
          ) : (
            <span className="text-muted-foreground">Aucun canal prêt</span>
          )}
        </div>

        {/* Action buttons */}
        <div className="flex items-center gap-2">
          {onOpenSettings && (
            <Button variant="outline" size="sm" onClick={onOpenSettings}>
              <Settings className="h-4 w-4 mr-1.5" aria-hidden="true" />
              Paramètres
            </Button>
          )}
          <Button onClick={onGenerate} disabled={isDisabled} size="sm">
            {isLoading ? (
              <>
                <Loader2 className="mr-2 h-4 w-4 animate-spin" />
                Traitement...
              </>
            ) : (
              <>
                Générer les écritures
                <ArrowRight className="ml-1.5 h-4 w-4" aria-hidden="true" />
              </>
            )}
          </Button>
        </div>
      </div>
    );
  }

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
