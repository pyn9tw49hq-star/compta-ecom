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
 */
const CHANNEL_PATTERNS: Record<string, RegExp[]> = {
  shopify: [
    /^Ventes Shopify.*\.csv$/i,
    /^Transactions Shopify.*\.csv$/i,
    /^D[ée]tails\s+versements.*\.csv$/i,
    /^Total des retours.*\.csv$/i,
    /^Detail transactions par versements.*\.csv$/i,
  ],
  manomano: [
    /^CA Manomano.*\.csv$/i,
    /^Detail versement Manomano.*\.csv$/i,
    /^Detail commandes manomano.*\.csv$/i,
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
    iconClass: "text-[#95BF47] dark:text-[#A8D45A]",
    badgeClass:
      "bg-[#95BF47]/15 text-[#6B8A30] border-[#95BF47]/30 hover:bg-[#95BF47]/20 dark:bg-[#95BF47]/20 dark:text-[#A8D45A] dark:border-[#95BF47]/30 dark:hover:bg-[#95BF47]/25",
  },
  manomano: {
    label: "ManoMano",
    icon: Wrench,
    iconClass: "text-[#00B2A9] dark:text-[#33C5BD]",
    badgeClass:
      "bg-[#00B2A9]/15 text-[#008A83] border-[#00B2A9]/30 hover:bg-[#00B2A9]/20 dark:bg-[#00B2A9]/20 dark:text-[#33C5BD] dark:border-[#00B2A9]/30 dark:hover:bg-[#00B2A9]/25",
  },
  decathlon: {
    label: "Décathlon",
    icon: Mountain,
    iconClass: "text-[#0055A0] dark:text-[#3380BF]",
    badgeClass:
      "bg-[#0055A0]/15 text-[#004080] border-[#0055A0]/30 hover:bg-[#0055A0]/20 dark:bg-[#0055A0]/20 dark:text-[#3380BF] dark:border-[#0055A0]/30 dark:hover:bg-[#0055A0]/25",
  },
  leroy_merlin: {
    label: "Leroy Merlin",
    icon: Home,
    iconClass: "text-[#2D8C3C] dark:text-[#4AA85A]",
    badgeClass:
      "bg-[#2D8C3C]/15 text-[#1F6B2B] border-[#2D8C3C]/30 hover:bg-[#2D8C3C]/20 dark:bg-[#2D8C3C]/20 dark:text-[#4AA85A] dark:border-[#2D8C3C]/30 dark:hover:bg-[#2D8C3C]/25",
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
  const basename = (filename.split("/").pop() ?? filename).normalize("NFC");
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
        regex: /^D[ée]tails\s+versements.*\.csv$/i,
      },
      {
        key: "payout_details",
        pattern: "Detail transactions par versements*.csv",
        patternHuman: '"Detail transactions par versements [...].csv"',
        required: false,
        regex: /^Detail transactions par versements.*\.csv$/i,
        multi: true,
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
      { label: "Mode complet", slots: ["sales", "transactions", "payouts", "payout_details"] },
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
      {
        key: "order_details",
        pattern: "Detail commandes manomano*.csv",
        patternHuman: '"Detail commandes manomano [...].csv"',
        required: true,
        regex: /^Detail commandes manomano.*\.csv$/i,
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
 */
export function matchFileToSlot(
  filename: string,
  configs: ChannelConfig[],
): { channel: string; slotKey: string } | null {
  const basename = (filename.split("/").pop() ?? filename).normalize("NFC");
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
  const lower = filename.normalize("NFC").toLowerCase();
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
