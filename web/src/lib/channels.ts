import {
  ShoppingBag,
  Wrench,
  Mountain,
  Home,
  FileQuestion,
  type LucideIcon,
} from "lucide-react";
import type { FileSlotConfig, ChannelConfig } from "./types";

/**
 * Channel detection patterns — mirror of channels.yaml (backend).
 * Note: "Detail transactions par versements/*.csv" is a path-based pattern
 * not matchable via browser file.name (SF-3) — intentionally excluded.
 */
const CHANNEL_PATTERNS: Record<string, RegExp[]> = {
  shopify: [
    /^Ventes Shopify.*\.csv$/i,
    /^Transactions Shopify.*\.csv$/i,
    /^D[ée]tails versements.*\.csv$/i,
    /^Total des retours.*\.csv$/i,
  ],
  manomano: [
    /^CA Manomano.*\.csv$/i,
    /^Detail versement Manomano.*\.csv$/i,
  ],
  decathlon: [/^Decathlon.*\.csv$/i],
  leroy_merlin: [/^Leroy Merlin.*\.csv$/i],
};

export interface ChannelMeta {
  label: string;
  icon: LucideIcon;
  iconClass: string;
  badgeClass: string;
}

export const CHANNEL_META: Record<string, ChannelMeta> = {
  shopify: {
    label: "Shopify",
    icon: ShoppingBag,
    iconClass: "text-green-600 dark:text-green-400",
    badgeClass:
      "bg-green-100 text-green-800 border-green-300 hover:bg-green-100 dark:bg-green-900 dark:text-green-200 dark:border-green-700 dark:hover:bg-green-900",
  },
  manomano: {
    label: "ManoMano",
    icon: Wrench,
    iconClass: "text-blue-600 dark:text-blue-400",
    badgeClass:
      "bg-blue-100 text-blue-800 border-blue-300 hover:bg-blue-100 dark:bg-blue-900 dark:text-blue-200 dark:border-blue-700 dark:hover:bg-blue-900",
  },
  decathlon: {
    label: "Décathlon",
    icon: Mountain,
    iconClass: "text-orange-600 dark:text-orange-400",
    badgeClass:
      "bg-orange-100 text-orange-800 border-orange-300 hover:bg-orange-100 dark:bg-orange-900 dark:text-orange-200 dark:border-orange-700 dark:hover:bg-orange-900",
  },
  leroy_merlin: {
    label: "Leroy Merlin",
    icon: Home,
    iconClass: "text-purple-600 dark:text-purple-400",
    badgeClass:
      "bg-purple-100 text-purple-800 border-purple-300 hover:bg-purple-100 dark:bg-purple-900 dark:text-purple-200 dark:border-purple-700 dark:hover:bg-purple-900",
  },
};

export const UNKNOWN_CHANNEL_META: ChannelMeta = {
  label: "Canal inconnu",
  icon: FileQuestion,
  iconClass: "text-gray-600 dark:text-gray-400",
  badgeClass:
    "bg-gray-100 text-gray-600 border-gray-300 hover:bg-gray-100 dark:bg-gray-800 dark:text-gray-300 dark:border-gray-600",
};

/**
 * Detect the channel from a filename using glob-like patterns.
 * Returns the channel key or null if no match.
 */
export function detectChannel(filename: string): string | null {
  const basename = filename.split("/").pop() ?? filename;
  for (const [channel, patterns] of Object.entries(CHANNEL_PATTERNS)) {
    if (patterns.some((re) => re.test(basename))) {
      return channel;
    }
  }
  return null;
}

/**
 * Get channel display metadata (label, icon, badgeClass).
 */
export function getChannelMeta(channel: string | null): ChannelMeta {
  if (channel && channel in CHANNEL_META) {
    return CHANNEL_META[channel];
  }
  return UNKNOWN_CHANNEL_META;
}

/**
 * Declarative configuration of expected files per channel.
 * Mirrors channels.yaml (backend source of truth).
 */
export const CHANNEL_CONFIGS: ChannelConfig[] = [
  {
    key: "shopify",
    meta: CHANNEL_META.shopify,
    files: [
      {
        key: "sales",
        pattern: "Ventes Shopify*.csv",
        patternHuman: '"Ventes Shopify [...].csv"',
        required: true,
        regex: /^Ventes Shopify.*\.csv$/i,
      },
      {
        key: "transactions",
        pattern: "Transactions Shopify*.csv",
        patternHuman: '"Transactions Shopify [...].csv"',
        required: true,
        regex: /^Transactions Shopify.*\.csv$/i,
      },
      {
        key: "payouts",
        pattern: "Détails versements*.csv",
        patternHuman: '"Détails versements [...].csv"',
        required: true,
        regex: /^D[ée]tails versements.*\.csv$/i,
      },
      {
        key: "payout_details",
        pattern: "Detail transactions par versements/*.csv",
        patternHuman: '"Detail transactions par versements/[...].csv"',
        required: false,
        regex: null,
      },
      {
        key: "returns",
        pattern: "Total des retours*.csv",
        patternHuman: '"Total des retours [...].csv"',
        required: false,
        regex: /^Total des retours.*\.csv$/i,
      },
    ],
    fileGroups: [
      { label: "Mode complet", slots: ["sales", "transactions", "payouts"] },
      { label: "Mode avoirs", slots: ["returns"] },
    ],
  },
  {
    key: "manomano",
    meta: CHANNEL_META.manomano,
    files: [
      {
        key: "ca",
        pattern: "CA Manomano*.csv",
        patternHuman: '"CA Manomano [...].csv"',
        required: true,
        regex: /^CA Manomano.*\.csv$/i,
      },
      {
        key: "payouts",
        pattern: "Detail versement Manomano*.csv",
        patternHuman: '"Detail versement Manomano [...].csv"',
        required: true,
        regex: /^Detail versement Manomano.*\.csv$/i,
      },
    ],
  },
  {
    key: "decathlon",
    meta: CHANNEL_META.decathlon,
    files: [
      {
        key: "data",
        pattern: "Decathlon*.csv",
        patternHuman: '"Decathlon [...].csv"',
        required: true,
        regex: /^Decathlon.*\.csv$/i,
      },
    ],
  },
  {
    key: "leroy_merlin",
    meta: CHANNEL_META.leroy_merlin,
    files: [
      {
        key: "data",
        pattern: "Leroy Merlin*.csv",
        patternHuman: '"Leroy Merlin [...].csv"',
        required: true,
        regex: /^Leroy Merlin.*\.csv$/i,
      },
    ],
  },
];

/**
 * Keywords used by suggestRename to identify a probable channel from a filename.
 */
export const CHANNEL_KEYWORDS: Record<string, string[]> = {
  shopify: ["shopify", "ventes shopify", "transactions shopify", "versements", "retours"],
  manomano: ["manomano", "mano"],
  decathlon: ["decathlon", "deca"],
  leroy_merlin: ["leroy", "merlin", "leroy merlin"],
};

/**
 * Match a filename to a specific channel and file slot.
 * Returns the channel key and slot key, or null if no match.
 * Slots with regex=null are skipped (e.g. payout_details — SF-3).
 */
export function matchFileToSlot(
  filename: string,
  configs: ChannelConfig[],
): { channel: string; slotKey: string } | null {
  const basename = filename.split("/").pop() ?? filename;
  for (const config of configs) {
    for (const slot of config.files) {
      if (slot.regex === null) continue;
      if (slot.regex.test(basename)) {
        return { channel: config.key, slotKey: slot.key };
      }
    }
  }
  return null;
}

/**
 * Suggest a rename for an unrecognized file based on channel keywords.
 * Returns the patternHuman of the first missing slot for the detected channel,
 * or null if no keyword match or no missing slot.
 */
export function suggestRename(
  filename: string,
  missingSlots: { channel: string; slot: FileSlotConfig }[],
): string | null {
  const lower = filename.toLowerCase();
  for (const [channel, keywords] of Object.entries(CHANNEL_KEYWORDS)) {
    if (keywords.some((kw) => lower.includes(kw))) {
      const match = missingSlots.find((ms) => ms.channel === channel);
      if (match) {
        return match.slot.patternHuman;
      }
      return null;
    }
  }
  return null;
}
