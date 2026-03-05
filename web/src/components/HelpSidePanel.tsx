"use client";

import { Lightbulb, X } from "lucide-react";
import { CHANNEL_CONFIGS } from "@/lib/channels";

const CHANNEL_DOT_COLORS: Record<string, string> = {
  shopify: "#96BF48",
  manomano: "#00B2A9",
  decathlon: "#0082C3",
  leroy_merlin: "#78BE20",
};

const VALID_EXAMPLES = [
  "Ventes Shopify Janv 2026.csv",
  "Transactions Shopify Février 2026.csv",
  "Détails versements Janvier 2026.csv",
  "CA Manomano 01-2026.csv",
  "Decathlon Mars.csv",
  "Leroy Merlin Q1 2026.csv",
];

interface HelpSidePanelProps {
  isOpen: boolean;
  onClose: () => void;
}

export default function HelpSidePanel({ isOpen, onClose }: HelpSidePanelProps) {
  if (!isOpen) return null;

  return (
    <div className="w-[560px] shrink-0 bg-white dark:bg-gray-900 border-l border-gray-200 dark:border-gray-700 flex flex-col h-screen overflow-hidden">
      {/* Header */}
      <div className="py-6 px-7 flex justify-between items-center shrink-0">
        <div className="flex items-center gap-3">
          <Lightbulb className="h-5 w-5 text-[#0D6E6E] shrink-0" />
          <h2 className="text-lg font-bold text-gray-900 dark:text-gray-100" style={{ fontFamily: "Inter, sans-serif" }}>
            Comment nommer vos fichiers ?
          </h2>
        </div>
        <button
          onClick={onClose}
          className="w-8 h-8 flex items-center justify-center bg-gray-100 dark:bg-gray-800 rounded-lg hover:bg-gray-200 dark:hover:bg-gray-700 transition-colors"
        >
          <X className="h-4 w-4 text-gray-500" />
        </button>
      </div>

      {/* Divider */}
      <div className="border-b border-gray-200 dark:border-gray-700" />

      {/* Scroll content */}
      <div className="p-6 px-7 flex flex-col gap-6 overflow-y-auto flex-1">
        {/* Intro */}
        <div className="space-y-1">
          <p className="text-[13px] text-gray-500 dark:text-gray-400 leading-relaxed">
            Chaque fichier CSV doit commencer par un préfixe spécifique pour être reconnu.
          </p>
          <p className="text-[13px] text-gray-500 dark:text-gray-400 italic leading-relaxed">
            [...] = texte optionnel (ex : une date, un mois...)
          </p>
        </div>

        {/* Channel sections */}
        {CHANNEL_CONFIGS.map((config) => {
          const dotColor = CHANNEL_DOT_COLORS[config.key] ?? "#999";
          const totalFiles = config.files.filter((f) => f.regex !== null).length;
          const hasFileGroups = !!config.fileGroups;

          return (
            <div key={config.key}>
              {/* Channel header */}
              <div className="flex items-center gap-2 mb-2">
                <span
                  className="w-2.5 h-2.5 rounded-full shrink-0"
                  style={{ backgroundColor: dotColor }}
                />
                <span className="text-[13px] font-bold tracking-wider text-gray-900 dark:text-gray-100 uppercase">
                  {config.meta.label}
                </span>
                <span className="text-[13px] text-gray-400 dark:text-gray-500">
                  ({totalFiles} fichier{totalFiles > 1 ? "s" : ""}{hasFileGroups ? "/modes" : ""})
                </span>
              </div>

              {/* File list */}
              <div className="pl-[18px]">
                {hasFileGroups ? (
                  <>
                    <p className="text-[13px] text-gray-500 dark:text-gray-400 mb-2">
                      Choisissez l&apos;un des modes suivants :
                    </p>
                    {config.fileGroups!.map((group) => (
                      <div key={group.label} className="mb-3">
                        <p className="text-[13px] font-semibold text-gray-700 dark:text-gray-300 mb-1">
                          {group.label}
                        </p>
                        <ul className="space-y-0.5">
                          {group.slots.map((slotKey) => {
                            const file = config.files.find((f) => f.key === slotKey);
                            if (!file) return null;
                            return (
                              <li
                                key={file.key}
                                className={
                                  file.required
                                    ? "text-[13px] text-gray-900 dark:text-gray-100"
                                    : "text-[13px] text-gray-400 dark:text-gray-500 italic"
                                }
                              >
                                {file.patternHuman}
                                {!file.required && " (optionnel)"}
                              </li>
                            );
                          })}
                        </ul>
                      </div>
                    ))}
                    <p className="text-[12px] text-gray-400 dark:text-gray-500 italic">
                      Vous pouvez utiliser un seul mode à la fois.
                    </p>
                  </>
                ) : (
                  <ul className="space-y-0.5">
                    {config.files
                      .filter((f) => f.regex !== null)
                      .map((file) => (
                        <li
                          key={file.key}
                          className={
                            file.required
                              ? "text-[13px] text-gray-900 dark:text-gray-100"
                              : "text-[13px] text-gray-400 dark:text-gray-500 italic"
                          }
                        >
                          {file.patternHuman}
                          {!file.required && " (optionnel)"}
                        </li>
                      ))}
                  </ul>
                )}
              </div>
            </div>
          );
        })}

        {/* Valid name examples */}
        <div>
          <p className="text-sm font-bold text-gray-900 dark:text-gray-100 mb-2">
            Exemples de noms valides
          </p>
          <ul className="space-y-0.5">
            {VALID_EXAMPLES.map((ex) => (
              <li key={ex} className="text-[12px] text-gray-500 dark:text-gray-400">
                {ex}
              </li>
            ))}
          </ul>
        </div>

        {/* Tip card */}
        <div className="bg-[#F0FDF4] dark:bg-green-950 rounded-lg border border-[#BBF7D0] dark:border-green-800 p-[14px_18px]">
          <p className="text-[13px] font-bold text-[#166534] dark:text-green-300 mb-1">
            Astuce
          </p>
          <p className="text-[12px] text-[#166534] dark:text-green-300 leading-relaxed">
            Déposez uniquement les fichiers des canaux que vous souhaitez traiter.
          </p>
        </div>
      </div>
    </div>
  );
}
