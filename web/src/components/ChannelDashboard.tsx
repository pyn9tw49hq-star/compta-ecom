"use client";

import { useCallback, useEffect, useMemo, useState } from "react";
import { ChevronsUpDown } from "lucide-react";
import { Button } from "@/components/ui/button";
import { Card } from "@/components/ui/card";
import ChannelCard from "@/components/ChannelCard";
import { useNewDesign } from "@/hooks/useNewDesign";
import { matchFileToSlot } from "@/lib/channels";
import type { ChannelConfig, UploadedFile } from "@/lib/types";

interface ChannelDashboardProps {
  files: UploadedFile[];
  channelConfig: ChannelConfig[];
  onRemoveFile: (index: number) => void;
}

/**
 * Orchestrates ChannelCards: active channels on top,
 * inactive channels in a "non utilisés" section below.
 */
export default function ChannelDashboard({
  files,
  channelConfig,
  onRemoveFile,
}: ChannelDashboardProps) {
  const isV2 = useNewDesign();
  // Group files by channel
  const filesByChannel = useMemo(() => {
    const grouped: Record<string, UploadedFile[]> = {};
    for (const config of channelConfig) {
      grouped[config.key] = [];
    }
    for (const uploaded of files) {
      const result = matchFileToSlot(uploaded.file.name, channelConfig);
      if (result) {
        grouped[result.channel]?.push(uploaded);
      }
    }
    return grouped;
  }, [files, channelConfig]);

  // Split active vs inactive channels (preserving channelConfig order)
  const { activeChannels, inactiveChannels } = useMemo(() => {
    const active: ChannelConfig[] = [];
    const inactive: ChannelConfig[] = [];
    for (const config of channelConfig) {
      if ((filesByChannel[config.key]?.length ?? 0) > 0) {
        active.push(config);
      } else {
        inactive.push(config);
      }
    }
    return { activeChannels: active, inactiveChannels: inactive };
  }, [channelConfig, filesByChannel]);

  // Expanded state — active channels open by default, inactive closed
  const [expandedChannels, setExpandedChannels] = useState<Record<string, boolean>>(() => {
    const state: Record<string, boolean> = {};
    for (const config of channelConfig) {
      state[config.key] = (filesByChannel[config.key]?.length ?? 0) > 0;
    }
    return state;
  });

  // Recalculate when files change (auto-expand newly active channels)
  useEffect(() => {
    setExpandedChannels((prev) => {
      const next = { ...prev };
      for (const config of channelConfig) {
        const hasFiles = (filesByChannel[config.key]?.length ?? 0) > 0;
        // Auto-expand channels that just became active
        if (hasFiles && prev[config.key] === false) {
          next[config.key] = true;
        }
        // Auto-collapse channels that just became inactive
        if (!hasFiles && prev[config.key] === true) {
          next[config.key] = false;
        }
      }
      return next;
    });
  }, [filesByChannel, channelConfig]);

  const toggle = useCallback((key: string) => {
    setExpandedChannels((prev) => ({ ...prev, [key]: !prev[key] }));
  }, []);

  // Toggle all: if all are expanded → collapse all, otherwise → expand all
  const allExpanded = channelConfig.every((c) => expandedChannels[c.key]);

  const toggleAll = useCallback(() => {
    setExpandedChannels((prev) => {
      const allOpen = channelConfig.every((c) => prev[c.key]);
      const next: Record<string, boolean> = {};
      for (const config of channelConfig) {
        next[config.key] = !allOpen;
      }
      return next;
    });
  }, [channelConfig]);

  // Find global index of a file from a channel's local uploadedFiles
  const handleRemoveFile = useCallback(
    (localIndex: number, channelKey: string) => {
      const channelFile = filesByChannel[channelKey]?.[localIndex];
      if (!channelFile) return;
      const globalIndex = files.indexOf(channelFile);
      if (globalIndex !== -1) {
        onRemoveFile(globalIndex);
      }
    },
    [files, filesByChannel, onRemoveFile],
  );

  if (isV2) {
    // Count complete channels for the header counter
    const completeCount = channelConfig.filter((config) => {
      const channelFiles = filesByChannel[config.key] ?? [];
      if (channelFiles.length === 0) return false;
      const required = config.files.filter((f) => f.required);
      if (config.fileGroups) {
        return config.fileGroups.some((g) => {
          return g.slots.every((slotKey) => {
            const slot = config.files.find((f) => f.key === slotKey);
            if (!slot || slot.regex === null) return false;
            return channelFiles.some((u) => slot.regex!.test(u.file.name.normalize("NFC")));
          });
        });
      }
      const filledRequired = required.filter((slot) => {
        if (slot.regex === null) return false;
        return channelFiles.some((u) => slot.regex!.test(u.file.name.normalize("NFC")));
      });
      return filledRequired.length === required.length;
    }).length;

    return (
      <div>
        <div className="flex items-center justify-between mb-3">
          <span className="text-[10px] font-semibold uppercase tracking-widest text-muted-foreground">
            Canaux détectés
          </span>
          <span className="text-xs text-muted-foreground">
            {completeCount}/{channelConfig.length} complets
          </span>
        </div>

        <div className="grid grid-cols-4 gap-4">
          {channelConfig.map((config) => (
            <ChannelCard
              key={config.key}
              channelKey={config.key}
              meta={config.meta}
              expectedFiles={config.files}
              fileGroups={config.fileGroups}
              uploadedFiles={filesByChannel[config.key] ?? []}
              isExpanded={true}
              onToggle={() => toggle(config.key)}
              onRemoveFile={(localIdx) => handleRemoveFile(localIdx, config.key)}
            />
          ))}
        </div>
      </div>
    );
  }

  return (
    <Card className="p-4">
      <div className="flex items-center justify-between mb-3">
        <span className="text-sm font-semibold">Canaux</span>
        <Button variant="ghost" size="sm" onClick={toggleAll}>
          <ChevronsUpDown className="h-4 w-4 mr-1" aria-hidden="true" />
          {allExpanded ? "Tout replier" : "Tout déplier"}
        </Button>
      </div>

      <div aria-live="polite">
        {activeChannels.map((config) => (
          <ChannelCard
            key={config.key}
            channelKey={config.key}
            meta={config.meta}
            expectedFiles={config.files}
            fileGroups={config.fileGroups}
            uploadedFiles={filesByChannel[config.key] ?? []}
            isExpanded={expandedChannels[config.key] ?? false}
            onToggle={() => toggle(config.key)}
            onRemoveFile={(localIdx) => handleRemoveFile(localIdx, config.key)}
          />
        ))}

        {activeChannels.length > 0 && inactiveChannels.length > 0 && (
          <div className="flex items-center gap-2 my-3 text-xs text-muted-foreground">
            <hr className="flex-1 border-muted-foreground/20" />
            <span>non utilisés</span>
            <hr className="flex-1 border-muted-foreground/20" />
          </div>
        )}

        {inactiveChannels.map((config) => (
          <ChannelCard
            key={config.key}
            channelKey={config.key}
            meta={config.meta}
            expectedFiles={config.files}
            fileGroups={config.fileGroups}
            uploadedFiles={[]}
            isExpanded={expandedChannels[config.key] ?? false}
            onToggle={() => toggle(config.key)}
            onRemoveFile={() => {}}
          />
        ))}
      </div>
    </Card>
  );
}

export type { ChannelDashboardProps };
