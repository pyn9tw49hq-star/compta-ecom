"use client";

import { memo, useMemo } from "react";
import { ChevronDown, ChevronRight, CircleAlert } from "lucide-react";
import { Badge } from "@/components/ui/badge";
import {
  Collapsible,
  CollapsibleTrigger,
  CollapsibleContent,
} from "@/components/ui/collapsible";
import FileSlot from "@/components/FileSlot";
import type { ChannelMeta } from "@/lib/channels";
import type { FileGroupConfig, FileSlotConfig, UploadedFile } from "@/lib/types";

interface ChannelCardProps {
  channelKey: string;
  meta: ChannelMeta;
  expectedFiles: FileSlotConfig[];
  fileGroups?: FileGroupConfig[];
  uploadedFiles: UploadedFile[];
  isExpanded: boolean;
  onToggle: () => void;
  onRemoveFile: (index: number) => void;
}

/**
 * Displays a single channel as a collapsible card with file slots,
 * completion badge, and inline help for missing files.
 */
const ChannelCard = memo(function ChannelCard({
  meta,
  expectedFiles,
  fileGroups,
  uploadedFiles,
  isExpanded,
  onToggle,
  onRemoveFile,
}: ChannelCardProps) {
  const Icon = meta.icon;

  const { requiredSlots, optionalSlots, slotMatches, uploadedRequiredCount, isComplete, isActive, hasPartialFiles, groupStatuses } =
    useMemo(() => {
      const required = expectedFiles.filter((f) => f.required);
      const optional = expectedFiles.filter((f) => !f.required);

      // Match each slot to an uploaded file
      const matches = new Map<string, { file: UploadedFile } | null>();
      for (const slot of expectedFiles) {
        matches.set(slot.key, null);
      }
      for (const uploaded of uploadedFiles) {
        for (const slot of expectedFiles) {
          if (slot.regex === null) continue;
          if (slot.regex.test(uploaded.file.name) && !matches.get(slot.key)) {
            matches.set(slot.key, { file: uploaded });
            break;
          }
        }
      }

      const reqCount = required.filter((s) => matches.get(s.key) !== null).length;
      const active = uploadedFiles.length > 0;

      // Compute group statuses when fileGroups is defined
      let gStatuses: { label: string; complete: boolean; filledCount: number; totalCount: number }[] | undefined;
      let complete: boolean;

      if (fileGroups) {
        gStatuses = fileGroups.map((g) => {
          const filled = g.slots.filter((s) => matches.get(s) !== null).length;
          return { label: g.label, complete: filled === g.slots.length, filledCount: filled, totalCount: g.slots.length };
        });
        complete = gStatuses.some((g) => g.complete);
      } else {
        complete = reqCount === required.length;
      }

      return {
        requiredSlots: required,
        optionalSlots: optional,
        slotMatches: matches,
        uploadedRequiredCount: reqCount,
        isComplete: complete,
        isActive: active,
        hasPartialFiles: active && !complete,
        groupStatuses: gStatuses,
      };
    }, [expectedFiles, fileGroups, uploadedFiles]);

  // Find the global index of a file in the parent's files array
  const findGlobalIndex = (file: UploadedFile): number => {
    // We need to find the file by reference in uploadedFiles
    return uploadedFiles.indexOf(file);
  };

  const missingRequiredPatterns = requiredSlots
    .filter((s) => slotMatches.get(s.key) === null)
    .map((s) => s.patternHuman);

  return (
    <Collapsible open={isExpanded} onOpenChange={onToggle}>
      <CollapsibleTrigger
        className="flex w-full items-center gap-3 rounded-md px-3 py-2 hover:bg-muted/50 transition-colors"
        aria-expanded={isExpanded}
      >
        <Icon className={`h-5 w-5 ${meta.iconClass} shrink-0`} aria-hidden="true" />
        <span className="font-semibold">{meta.label}</span>
        <span className="text-sm text-muted-foreground">
          {groupStatuses
            ? groupStatuses.map((g) => g.label).join(" / ")
            : isActive
              ? `${uploadedRequiredCount} / ${requiredSlots.length} obligatoires`
              : `${requiredSlots.length} obligatoires${optionalSlots.length > 0 ? ` + ${optionalSlots.length} optionnel` : ""}`}
        </span>
        {isComplete && isActive && groupStatuses && (
          <Badge variant="outline" className="bg-green-50 text-green-700 border-green-300 dark:bg-green-950 dark:text-green-200 dark:border-green-700">
            {groupStatuses.filter((g) => g.complete).map((g) => g.label).join(" + ")}
          </Badge>
        )}
        {isComplete && isActive && !groupStatuses && (
          <Badge variant="outline" className="bg-green-50 text-green-700 border-green-300 dark:bg-green-950 dark:text-green-200 dark:border-green-700">
            Complet
          </Badge>
        )}
        {!isComplete && isActive && (
          <Badge variant="outline" className="bg-amber-100 text-amber-800 border-amber-300 dark:bg-amber-900 dark:text-amber-200 dark:border-amber-700">
            Incomplet
          </Badge>
        )}
        <span className="ml-auto shrink-0">
          {isExpanded ? (
            <ChevronDown className="h-4 w-4" aria-hidden="true" />
          ) : (
            <ChevronRight className="h-4 w-4" aria-hidden="true" />
          )}
        </span>
      </CollapsibleTrigger>

      <CollapsibleContent className="px-3 pb-2">
        {groupStatuses ? (
          <>
            {groupStatuses.map((group) => {
              const groupSlots = fileGroups!.find((g) => g.label === group.label)!.slots;
              return (
                <div key={group.label} className="mb-2">
                  <div className="flex items-center gap-2 py-1">
                    <span className="text-xs font-medium text-muted-foreground uppercase tracking-wide">
                      {group.label}
                    </span>
                    {group.complete ? (
                      <Badge variant="outline" className="text-[10px] px-1.5 py-0 bg-green-50 text-green-700 border-green-300 dark:bg-green-950 dark:text-green-200 dark:border-green-700">
                        OK
                      </Badge>
                    ) : isActive && group.filledCount > 0 ? (
                      <Badge variant="outline" className="text-[10px] px-1.5 py-0 bg-amber-100 text-amber-800 border-amber-300 dark:bg-amber-900 dark:text-amber-200 dark:border-amber-700">
                        {group.filledCount}/{group.totalCount}
                      </Badge>
                    ) : null}
                  </div>
                  {groupSlots.map((slotKey) => {
                    const slot = expectedFiles.find((f) => f.key === slotKey);
                    if (!slot) return null;
                    const match = slotMatches.get(slot.key);
                    return (
                      <FileSlot
                        key={slot.key}
                        slotKey={slot.key}
                        pattern={slot.pattern}
                        patternHuman={slot.patternHuman}
                        isRequired
                        matchedFile={match?.file ?? null}
                        showMissingWarning={isActive && !isComplete && group.filledCount > 0 && !group.complete}
                        onRemoveFile={
                          match?.file
                            ? () => onRemoveFile(findGlobalIndex(match.file))
                            : undefined
                        }
                      />
                    );
                  })}
                </div>
              );
            })}
            {/* Show remaining optional slots not in any group */}
            {(() => {
              const groupSlotKeys = new Set(fileGroups!.flatMap((g) => g.slots));
              const extraSlots = expectedFiles.filter((f) => !groupSlotKeys.has(f.key));
              if (extraSlots.length === 0) return null;
              return (
                <>
                  <hr className="border-dashed border-muted-foreground/20 my-1" />
                  {extraSlots.map((slot) => {
                    const match = slotMatches.get(slot.key);
                    return (
                      <FileSlot
                        key={slot.key}
                        slotKey={slot.key}
                        pattern={slot.pattern}
                        patternHuman={slot.patternHuman}
                        isRequired={false}
                        matchedFile={match?.file ?? null}
                        showMissingWarning={false}
                        onRemoveFile={
                          match?.file
                            ? () => onRemoveFile(findGlobalIndex(match.file))
                            : undefined
                        }
                      />
                    );
                  })}
                </>
              );
            })()}
          </>
        ) : (
          <>
            {requiredSlots.map((slot) => {
              const match = slotMatches.get(slot.key);
              return (
                <FileSlot
                  key={slot.key}
                  slotKey={slot.key}
                  pattern={slot.pattern}
                  patternHuman={slot.patternHuman}
                  isRequired
                  matchedFile={match?.file ?? null}
                  showMissingWarning={hasPartialFiles}
                  onRemoveFile={
                    match?.file
                      ? () => onRemoveFile(findGlobalIndex(match.file))
                      : undefined
                  }
                />
              );
            })}

            {optionalSlots.length > 0 && (
              <>
                <hr className="border-dashed border-muted-foreground/20 my-1" />
                {optionalSlots.map((slot) => {
                  const match = slotMatches.get(slot.key);
                  return (
                    <FileSlot
                      key={slot.key}
                      slotKey={slot.key}
                      pattern={slot.pattern}
                      patternHuman={slot.patternHuman}
                      isRequired={false}
                      matchedFile={match?.file ?? null}
                      showMissingWarning={false}
                      onRemoveFile={
                        match?.file
                          ? () => onRemoveFile(findGlobalIndex(match.file))
                          : undefined
                      }
                    />
                  );
                })}
              </>
            )}

            {hasPartialFiles && (
              <div className="rounded-md border border-amber-300 bg-amber-50 dark:border-amber-700 dark:bg-amber-950 p-3 mt-2">
                <div className="flex items-start gap-2">
                  <CircleAlert className="h-4 w-4 text-amber-600 dark:text-amber-400 shrink-0 mt-0.5" aria-hidden="true" />
                  <p className="text-sm text-amber-800 dark:text-amber-200">
                    {missingRequiredPatterns.length === 1
                      ? `Il manque 1 fichier obligatoire pour traiter ${meta.label}. Ajoutez un fichier nommé ${missingRequiredPatterns[0]}.`
                      : `Il manque ${missingRequiredPatterns.length} fichiers obligatoires pour traiter ${meta.label}. Ajoutez des fichiers nommés ${missingRequiredPatterns.join(", ")}.`}
                  </p>
                </div>
              </div>
            )}
          </>
        )}
      </CollapsibleContent>
    </Collapsible>
  );
});

export default ChannelCard;
export type { ChannelCardProps };
