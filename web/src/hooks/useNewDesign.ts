"use client";

const flag = process.env.NEXT_PUBLIC_FEATURE_NEW_DESIGN === "true";

export function useNewDesign(): boolean {
  return flag;
}

export const IS_NEW_DESIGN = flag;
