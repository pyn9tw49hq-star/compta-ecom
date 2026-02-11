"use client";

import { useState, useCallback, useMemo, useEffect } from "react";
import type { AccountDefaults, AccountOverrides } from "@/lib/types";

const STORAGE_KEY = "mapp-ecom:account-overrides";

/**
 * Deeply set a value in a nested object by dot-path.
 * e.g. setNestedValue({}, "journaux.ventes.shopify", "XX") →
 *   { journaux: { ventes: { shopify: "XX" } } }
 */
function setNestedValue(
  obj: Record<string, unknown>,
  path: string,
  value: string,
): Record<string, unknown> {
  const keys = path.split(".");
  const result = structuredClone(obj) as Record<string, unknown>;
  let current = result;
  for (let i = 0; i < keys.length - 1; i++) {
    const key = keys[i];
    if (!(key in current) || typeof current[key] !== "object" || current[key] === null) {
      current[key] = {};
    }
    current = current[key] as Record<string, unknown>;
  }
  current[keys[keys.length - 1]] = value;
  return result;
}

/**
 * Remove a value from a nested object by dot-path, cleaning up empty parents.
 */
function removeNestedValue(
  obj: Record<string, unknown>,
  path: string,
): Record<string, unknown> {
  const keys = path.split(".");
  const result = structuredClone(obj) as Record<string, unknown>;

  function recurse(current: Record<string, unknown>, depth: number): boolean {
    const key = keys[depth];
    if (depth === keys.length - 1) {
      delete current[key];
      return Object.keys(current).length === 0;
    }
    if (!(key in current) || typeof current[key] !== "object" || current[key] === null) {
      return Object.keys(current).length === 0;
    }
    const isEmpty = recurse(current[key] as Record<string, unknown>, depth + 1);
    if (isEmpty) {
      delete current[key];
    }
    return Object.keys(current).length === 0;
  }

  recurse(result, 0);
  return result;
}

/**
 * Get a value from a nested object by dot-path.
 */
function getNestedValue(obj: Record<string, unknown>, path: string): string | undefined {
  const keys = path.split(".");
  let current: unknown = obj;
  for (const key of keys) {
    if (current === null || current === undefined || typeof current !== "object") {
      return undefined;
    }
    current = (current as Record<string, unknown>)[key];
  }
  return typeof current === "string" ? current : undefined;
}

/**
 * Count the number of leaf string values in a nested object.
 */
function countLeaves(obj: Record<string, unknown>): number {
  let count = 0;
  for (const value of Object.values(obj)) {
    if (typeof value === "string") {
      count++;
    } else if (typeof value === "object" && value !== null) {
      count += countLeaves(value as Record<string, unknown>);
    }
  }
  return count;
}

function loadFromStorage(): AccountOverrides {
  if (typeof window === "undefined") return {};
  try {
    const raw = localStorage.getItem(STORAGE_KEY);
    return raw ? (JSON.parse(raw) as AccountOverrides) : {};
  } catch {
    return {};
  }
}

function saveToStorage(overrides: AccountOverrides) {
  if (typeof window === "undefined") return;
  if (Object.keys(overrides).length === 0) {
    localStorage.removeItem(STORAGE_KEY);
  } else {
    localStorage.setItem(STORAGE_KEY, JSON.stringify(overrides));
  }
}

export interface UseAccountOverridesReturn {
  overrides: AccountOverrides;
  defaults: AccountDefaults | null;
  setDefaults: (defaults: AccountDefaults) => void;
  getValue: (path: string) => string;
  isModified: (path: string) => boolean;
  setField: (path: string, value: string) => void;
  resetField: (path: string) => void;
  resetAll: () => void;
  modifiedCount: number;
}

/**
 * Get the default value for a field path from the AccountDefaults object.
 */
function getDefaultValue(defaults: AccountDefaults | null, path: string): string {
  if (!defaults) return "";
  return getNestedValue(defaults as unknown as Record<string, unknown>, path) ?? "";
}

export function useAccountOverrides(): UseAccountOverridesReturn {
  const [overrides, setOverrides] = useState<AccountOverrides>(loadFromStorage);
  const [defaults, setDefaults] = useState<AccountDefaults | null>(null);

  // Sync to localStorage on every change
  useEffect(() => {
    saveToStorage(overrides);
  }, [overrides]);

  const modifiedCount = useMemo(
    () => countLeaves(overrides as unknown as Record<string, unknown>),
    [overrides],
  );

  const getValue = useCallback(
    (path: string): string => {
      const override = getNestedValue(
        overrides as unknown as Record<string, unknown>,
        path,
      );
      if (override !== undefined) return override;
      return getDefaultValue(defaults, path);
    },
    [overrides, defaults],
  );

  const isModified = useCallback(
    (path: string): boolean => {
      return (
        getNestedValue(overrides as unknown as Record<string, unknown>, path) !== undefined
      );
    },
    [overrides],
  );

  const setField = useCallback((path: string, value: string) => {
    setOverrides((prev) =>
      setNestedValue(prev as unknown as Record<string, unknown>, path, value) as AccountOverrides,
    );
  }, []);

  const resetField = useCallback((path: string) => {
    setOverrides((prev) =>
      removeNestedValue(prev as unknown as Record<string, unknown>, path) as AccountOverrides,
    );
  }, []);

  const resetAll = useCallback(() => {
    setOverrides({});
  }, []);

  return {
    overrides,
    defaults,
    setDefaults,
    getValue,
    isModified,
    setField,
    resetField,
    resetAll,
    modifiedCount,
  };
}
