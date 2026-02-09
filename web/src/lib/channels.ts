import {
  ShoppingBag,
  Wrench,
  Mountain,
  Home,
  FileQuestion,
  type LucideIcon,
} from "lucide-react";

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
  color: string;
  badgeClass: string;
}

export const CHANNEL_META: Record<string, ChannelMeta> = {
  shopify: {
    label: "Shopify",
    icon: ShoppingBag,
    color: "green",
    badgeClass:
      "bg-green-100 text-green-800 border-green-300 hover:bg-green-100",
  },
  manomano: {
    label: "ManoMano",
    icon: Wrench,
    color: "blue",
    badgeClass: "bg-blue-100 text-blue-800 border-blue-300 hover:bg-blue-100",
  },
  decathlon: {
    label: "Décathlon",
    icon: Mountain,
    color: "orange",
    badgeClass:
      "bg-orange-100 text-orange-800 border-orange-300 hover:bg-orange-100",
  },
  leroy_merlin: {
    label: "Leroy Merlin",
    icon: Home,
    color: "purple",
    badgeClass:
      "bg-purple-100 text-purple-800 border-purple-300 hover:bg-purple-100",
  },
};

export const UNKNOWN_CHANNEL_META: ChannelMeta = {
  label: "Canal inconnu",
  icon: FileQuestion,
  color: "gray",
  badgeClass: "bg-gray-100 text-gray-600 border-gray-300 hover:bg-gray-100",
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
 * Get channel display metadata (label, icon, color).
 */
export function getChannelMeta(channel: string | null): ChannelMeta {
  if (channel && channel in CHANNEL_META) {
    return CHANNEL_META[channel];
  }
  return UNKNOWN_CHANNEL_META;
}
