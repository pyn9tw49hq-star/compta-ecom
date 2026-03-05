"use client";

import { useState, useMemo } from "react";
import { Settings, RotateCcw, AlertTriangle, Users, Receipt, BookOpen, SlidersHorizontal } from "lucide-react";
import { useNewDesign } from "@/hooks/useNewDesign";
import {
  Collapsible,
  CollapsibleContent,
  CollapsibleTrigger,
} from "@/components/ui/collapsible";
import { Button } from "@/components/ui/button";
import type { UseAccountOverridesReturn } from "@/hooks/useAccountOverrides";
import type { AccountDefaults } from "@/lib/types";

// --- Validation regex (mirrors backend) ---
const RE_COMPTE_TIERS = /^[A-Z0-9]{3,15}$/;
const RE_COMPTE_CHARGE = /^[0-9]{8}$/;
const RE_CODE_JOURNAL = /^[A-Z]{2,3}$/;

type ValidationRegex = RegExp;

interface FieldDef {
  label: string;
  path: string;
}

interface GroupDef {
  title: string;
  regex: ValidationRegex;
  sections: {
    subtitle: string;
    fields: FieldDef[];
  }[];
}

const GROUPS: GroupDef[] = [
  {
    title: "Comptes de tiers",
    regex: RE_COMPTE_TIERS,
    sections: [
      {
        subtitle: "CLIENTS",
        fields: [
          { label: "Shopify", path: "clients.shopify" },
          { label: "ManoMano", path: "clients.manomano" },
          { label: "Decathlon", path: "clients.decathlon" },
          { label: "Leroy Merlin", path: "clients.leroy_merlin" },
        ],
      },
      {
        subtitle: "FOURNISSEURS",
        fields: [
          { label: "ManoMano", path: "fournisseurs.manomano" },
          { label: "Decathlon", path: "fournisseurs.decathlon" },
          { label: "Leroy Merlin", path: "fournisseurs.leroy_merlin" },
        ],
      },
    ],
  },
  {
    title: "Comptes de charges",
    regex: RE_COMPTE_CHARGE,
    sections: [
      {
        subtitle: "COMMISSIONS",
        fields: [
          { label: "Decathlon", path: "charges.commissions.decathlon" },
          { label: "Leroy Merlin", path: "charges.commissions.leroy_merlin" },
        ],
      },
      {
        subtitle: "COMMISSIONS PSP",
        fields: [
          { label: "Card (Shopify)", path: "psp_commissions.card" },
          { label: "PayPal", path: "psp_commissions.paypal" },
          { label: "Klarna", path: "psp_commissions.klarna" },
        ],
      },
      {
        subtitle: "ABONNEMENTS",
        fields: [
          { label: "Decathlon", path: "charges.abonnements.decathlon" },
          { label: "Leroy Merlin", path: "charges.abonnements.leroy_merlin" },
        ],
      },
    ],
  },
  {
    title: "TVA & Journaux",
    regex: RE_CODE_JOURNAL, // Default for journals; TVA uses RE_COMPTE_CHARGE
    sections: [
      {
        subtitle: "TVA DÉDUCTIBLE",
        fields: [{ label: "TVA déductible", path: "tva_deductible" }],
      },
      {
        subtitle: "CODES JOURNAUX",
        fields: [
          { label: "Ventes Shopify", path: "journaux.ventes.shopify" },
          { label: "Ventes ManoMano", path: "journaux.ventes.manomano" },
          { label: "Ventes Decathlon", path: "journaux.ventes.decathlon" },
          { label: "Ventes Leroy Merlin", path: "journaux.ventes.leroy_merlin" },
          { label: "Achats", path: "journaux.achats" },
          { label: "Règlement", path: "journaux.reglement" },
        ],
      },
    ],
  },
];

function getRegexForPath(path: string, groupRegex: ValidationRegex): ValidationRegex {
  if (path === "tva_deductible") return RE_COMPTE_CHARGE;
  if (path.startsWith("charges.")) return RE_COMPTE_CHARGE;
  if (path.startsWith("psp_commissions.")) return RE_COMPTE_CHARGE;
  return groupRegex;
}

// --- AccountField ---
interface AccountFieldProps {
  label: string;
  path: string;
  regex: ValidationRegex;
  account: UseAccountOverridesReturn;
}

function AccountField({ label, path, regex, account }: AccountFieldProps) {
  const value = account.getValue(path);
  const modified = account.isModified(path);
  const defaultValue = account.defaults
    ? getNestedDefault(account.defaults, path)
    : "";
  const isValid = value === "" || regex.test(value);

  return (
    <div className="flex flex-col gap-0.5">
      <div className="flex items-center gap-2">
        <label className="text-xs text-muted-foreground w-32 shrink-0">
          {label}
        </label>
        <div className="relative flex-1">
          <input
            type="text"
            value={value}
            onChange={(e) => {
              const v = e.target.value.toUpperCase();
              if (v === defaultValue) {
                account.resetField(path);
              } else {
                account.setField(path, v);
              }
            }}
            className={`
              w-full rounded-md border px-2 py-1 text-sm font-mono
              bg-background
              ${modified ? "border-primary" : "border-input"}
              ${!isValid ? "border-red-500 dark:border-red-400" : ""}
              focus:outline-none focus:ring-1 focus:ring-ring
            `}
            aria-label={`${label} - compte`}
            aria-invalid={!isValid}
          />
          {modified && (
            <button
              type="button"
              onClick={() => account.resetField(path)}
              className="absolute right-1.5 top-1/2 -translate-y-1/2 text-primary hover:text-primary/80 text-sm"
              aria-label={`Réinitialiser ${label}`}
              title={`Réinitialiser à ${defaultValue}`}
            >
              ●
            </button>
          )}
        </div>
      </div>
      {modified && (
        <span className="text-[10px] text-muted-foreground ml-[8.5rem]">
          défaut : {defaultValue}
        </span>
      )}
      {!isValid && value !== "" && (
        <span className="text-[10px] text-red-500 dark:text-red-400 ml-[8.5rem]">
          Format invalide
        </span>
      )}
    </div>
  );
}

function getNestedDefault(defaults: AccountDefaults, path: string): string {
  const keys = path.split(".");
  // eslint-disable-next-line @typescript-eslint/no-explicit-any
  let current: any = defaults;
  for (const key of keys) {
    if (current === null || current === undefined || typeof current !== "object") {
      return "";
    }
    current = current[key];
  }
  if (typeof current === "number") return String(current);
  return typeof current === "string" ? current : "";
}

// --- ToleranceField ---
interface ToleranceFieldProps {
  account: UseAccountOverridesReturn;
}

function ToleranceField({ account }: ToleranceFieldProps) {
  const path = "matching_tolerance";
  const rawValue = account.getValue(path);
  const modified = account.isModified(path);
  const defaultValue = account.defaults
    ? getNestedDefault(account.defaults, path)
    : "0.01";
  const numValue = rawValue !== "" ? parseFloat(rawValue) : NaN;
  const isValid = rawValue === "" || (!isNaN(numValue) && numValue >= 0.001 && numValue <= 1.0);

  return (
    <div className="flex flex-col gap-0.5">
      <div className="flex items-center gap-2">
        <label className="text-xs text-muted-foreground w-32 shrink-0">
          Seuil de tolérance
        </label>
        <div className="relative flex-1">
          <input
            type="number"
            step="0.01"
            min="0.001"
            max="1.0"
            value={rawValue}
            onChange={(e) => {
              const v = e.target.value;
              if (v === defaultValue) {
                account.resetField(path);
              } else {
                account.setField(path, v);
              }
            }}
            className={`
              w-full rounded-md border px-2 py-1 text-sm font-mono
              bg-background
              ${modified ? "border-primary" : "border-input"}
              ${!isValid ? "border-red-500 dark:border-red-400" : ""}
              focus:outline-none focus:ring-1 focus:ring-ring
            `}
            aria-label="Seuil de tolérance"
            aria-invalid={!isValid}
          />
          {modified && (
            <button
              type="button"
              onClick={() => account.resetField(path)}
              className="absolute right-1.5 top-1/2 -translate-y-1/2 text-primary hover:text-primary/80 text-sm"
              aria-label="Réinitialiser Seuil de tolérance"
              title={`Réinitialiser à ${defaultValue}`}
            >
              ●
            </button>
          )}
        </div>
      </div>
      {modified && (
        <span className="text-[10px] text-muted-foreground ml-[8.5rem]">
          défaut : {defaultValue}
        </span>
      )}
      {!isValid && rawValue !== "" && (
        <span className="text-[10px] text-red-500 dark:text-red-400 ml-[8.5rem]">
          Valeur entre 0,001 et 1,0
        </span>
      )}
    </div>
  );
}

// --- V2 field components ---

function AccountFieldV2({ label, path, regex, account }: AccountFieldProps) {
  const value = account.getValue(path);
  const modified = account.isModified(path);
  const defaultValue = account.defaults
    ? getNestedDefault(account.defaults, path)
    : "";
  const isValid = value === "" || regex.test(value);

  return (
    <div className="flex flex-col gap-0.5">
      <div className="flex items-center gap-4">
        <label className="text-sm text-muted-foreground w-40 shrink-0">
          {label}
        </label>
        <div className="relative flex-1">
          <input
            type="text"
            value={value}
            onChange={(e) => {
              const v = e.target.value.toUpperCase();
              if (v === defaultValue) {
                account.resetField(path);
              } else {
                account.setField(path, v);
              }
            }}
            className={`
              w-full rounded-lg border px-3 py-2 text-sm font-mono
              ${modified ? "bg-primary/5 border-primary" : "bg-muted/50 border-border"}
              ${!isValid ? "border-red-500 dark:border-red-400" : ""}
              focus:outline-none focus:border-primary focus:ring-1 focus:ring-primary
            `}
            aria-label={`${label} - compte`}
            aria-invalid={!isValid}
          />
          {modified && (
            <button
              type="button"
              onClick={() => account.resetField(path)}
              className="absolute right-2 top-1/2 -translate-y-1/2 text-primary hover:text-primary/80 text-sm"
              aria-label={`Réinitialiser ${label}`}
              title={`Réinitialiser à ${defaultValue}`}
            >
              <RotateCcw className="h-3 w-3" />
            </button>
          )}
        </div>
      </div>
      {modified && (
        <span className="text-[10px] text-muted-foreground ml-44">
          défaut : {defaultValue}
        </span>
      )}
      {!isValid && value !== "" && (
        <span className="text-[10px] text-red-500 dark:text-red-400 ml-44">
          Format invalide
        </span>
      )}
    </div>
  );
}

function ToleranceFieldV2({ account }: ToleranceFieldProps) {
  const path = "matching_tolerance";
  const rawValue = account.getValue(path);
  const modified = account.isModified(path);
  const defaultValue = account.defaults
    ? getNestedDefault(account.defaults, path)
    : "0.01";
  const numValue = rawValue !== "" ? parseFloat(rawValue) : NaN;
  const isValid = rawValue === "" || (!isNaN(numValue) && numValue >= 0.001 && numValue <= 1.0);

  return (
    <div className="flex flex-col gap-0.5">
      <div className="flex items-center gap-4">
        <label className="text-sm text-muted-foreground w-40 shrink-0">
          Seuil de tolérance
        </label>
        <div className="relative flex-1">
          <input
            type="number"
            step="0.01"
            min="0.001"
            max="1.0"
            value={rawValue}
            onChange={(e) => {
              const v = e.target.value;
              if (v === defaultValue) {
                account.resetField(path);
              } else {
                account.setField(path, v);
              }
            }}
            className={`
              w-full rounded-lg border px-3 py-2 text-sm font-mono
              ${modified ? "bg-primary/5 border-primary" : "bg-muted/50 border-border"}
              ${!isValid ? "border-red-500 dark:border-red-400" : ""}
              focus:outline-none focus:border-primary focus:ring-1 focus:ring-primary
            `}
            aria-label="Seuil de tolérance"
            aria-invalid={!isValid}
          />
          {modified && (
            <button
              type="button"
              onClick={() => account.resetField(path)}
              className="absolute right-2 top-1/2 -translate-y-1/2 text-primary hover:text-primary/80 text-sm"
              aria-label="Réinitialiser Seuil de tolérance"
              title={`Réinitialiser à ${defaultValue}`}
            >
              <RotateCcw className="h-3 w-3" />
            </button>
          )}
        </div>
      </div>
      {modified && (
        <span className="text-[10px] text-muted-foreground ml-44">
          défaut : {defaultValue}
        </span>
      )}
      {!isValid && rawValue !== "" && (
        <span className="text-[10px] text-red-500 dark:text-red-400 ml-44">
          Valeur entre 0,001 et 1,0
        </span>
      )}
    </div>
  );
}

// --- V2 Section wrapper ---
interface V2SectionProps {
  icon: React.ReactNode;
  title: string;
  children: React.ReactNode;
}

function V2Section({ icon, title, children }: V2SectionProps) {
  return (
    <div className="bg-card rounded-xl border border-border p-6">
      <h3 className="text-sm font-semibold text-foreground mb-4 flex items-center gap-2">
        {icon}
        {title}
      </h3>
      <div className="border-t border-border pt-4 space-y-3">
        {children}
      </div>
    </div>
  );
}

function V2SubSection({ subtitle, children }: { subtitle: string; children: React.ReactNode }) {
  return (
    <div className="space-y-2">
      <h4 className="text-[11px] font-medium text-muted-foreground/70 uppercase tracking-wide">
        {subtitle}
      </h4>
      <div className="space-y-2">
        {children}
      </div>
    </div>
  );
}

// --- Main panel ---
interface AccountSettingsPanelProps {
  account: UseAccountOverridesReturn;
}

export default function AccountSettingsPanel({
  account,
}: AccountSettingsPanelProps) {
  const isV2 = useNewDesign();
  const [isOpen, setIsOpen] = useState(false);
  const [showResetConfirm, setShowResetConfirm] = useState(false);

  const hasValidationErrors = useMemo(() => {
    return hasAccountValidationErrors(account);
  }, [account]);

  if (!account.defaults) return null;

  // --- V2 layout ---
  if (isV2) {
    // Extract groups by title for explicit placement
    const tiersGroup = GROUPS.find((g) => g.title === "Comptes de tiers")!;
    const chargesGroup = GROUPS.find((g) => g.title === "Comptes de charges")!;
    const tvaGroup = GROUPS.find((g) => g.title === "TVA & Journaux")!;

    return (
      <div className="space-y-6">
        {/* Warning banner */}
        <div className="flex items-start gap-3 rounded-lg border-l-4 border-yellow-400 bg-yellow-50 dark:bg-yellow-950/30 p-4">
          <AlertTriangle className="h-5 w-5 text-yellow-500 shrink-0 mt-0.5" />
          <p className="text-sm text-yellow-800 dark:text-yellow-200">
            Les modifications du plan comptable sont temporaires et ne sont pas
            sauvegardées entre les sessions. Elles s&apos;appliquent uniquement au
            traitement en cours.
          </p>
        </div>

        {/* 2-column grid */}
        <div className="grid grid-cols-1 lg:grid-cols-2 gap-8">
          {/* Left column: Comptes de tiers */}
          <V2Section
            icon={<Users className="h-4 w-4 text-primary" />}
            title="Comptes de tiers"
          >
            {tiersGroup.sections.map((section) => (
              <V2SubSection key={section.subtitle} subtitle={section.subtitle}>
                {section.fields.map((field) => (
                  <AccountFieldV2
                    key={field.path}
                    label={field.label}
                    path={field.path}
                    regex={getRegexForPath(field.path, tiersGroup.regex)}
                    account={account}
                  />
                ))}
              </V2SubSection>
            ))}
          </V2Section>

          {/* Right column: Comptes de charges */}
          <V2Section
            icon={<Receipt className="h-4 w-4 text-primary" />}
            title="Comptes de charges"
          >
            {chargesGroup.sections.map((section) => (
              <V2SubSection key={section.subtitle} subtitle={section.subtitle}>
                {section.fields.map((field) => (
                  <AccountFieldV2
                    key={field.path}
                    label={field.label}
                    path={field.path}
                    regex={getRegexForPath(field.path, chargesGroup.regex)}
                    account={account}
                  />
                ))}
              </V2SubSection>
            ))}
          </V2Section>
        </div>

        {/* TVA & Journaux - full width */}
        <V2Section
          icon={<BookOpen className="h-4 w-4 text-primary" />}
          title="TVA &amp; Journaux"
        >
          {tvaGroup.sections.map((section) => (
            <V2SubSection key={section.subtitle} subtitle={section.subtitle}>
              {section.fields.map((field) => (
                <AccountFieldV2
                  key={field.path}
                  label={field.label}
                  path={field.path}
                  regex={getRegexForPath(field.path, tvaGroup.regex)}
                  account={account}
                />
              ))}
            </V2SubSection>
          ))}
        </V2Section>

        {/* Paramètres de contrôle - full width */}
        <V2Section
          icon={<SlidersHorizontal className="h-4 w-4 text-primary" />}
          title="Paramètres de contrôle"
        >
          <ToleranceFieldV2 account={account} />
        </V2Section>

        {/* Validation error */}
        {hasValidationErrors && (
          <p
            role="alert"
            className="text-xs text-red-500 dark:text-red-400"
          >
            Certains champs ont un format invalide. Corrigez-les avant de
            générer.
          </p>
        )}

        {/* Footer buttons */}
        <div className="flex items-center justify-end gap-3 pt-2 border-t border-border">
          {account.modifiedCount > 0 && (
            <>
              {showResetConfirm ? (
                <div className="flex items-center gap-2 mr-auto">
                  <span className="text-sm text-muted-foreground">
                    Réinitialiser toutes les valeurs ?
                  </span>
                  <Button
                    variant="destructive"
                    size="sm"
                    onClick={() => {
                      account.resetAll();
                      setShowResetConfirm(false);
                    }}
                  >
                    Confirmer
                  </Button>
                  <Button
                    variant="outline"
                    size="sm"
                    onClick={() => setShowResetConfirm(false)}
                  >
                    Annuler
                  </Button>
                </div>
              ) : (
                <Button
                  variant="outline"
                  size="sm"
                  onClick={() => setShowResetConfirm(true)}
                  className="gap-1.5 mr-auto"
                >
                  <RotateCcw className="h-3 w-3" />
                  Réinitialiser
                </Button>
              )}
            </>
          )}
        </div>
      </div>
    );
  }

  // --- V1 layout (unchanged) ---
  const subtitle =
    account.modifiedCount === 0
      ? "Valeurs par défaut actives"
      : `${account.modifiedCount} valeur${account.modifiedCount > 1 ? "s" : ""} personnalisée${account.modifiedCount > 1 ? "s" : ""}`;

  return (
    <Collapsible open={isOpen} onOpenChange={setIsOpen}>
      <CollapsibleTrigger asChild>
        <button
          type="button"
          className="flex w-full items-center justify-between rounded-lg border p-3 text-left hover:bg-accent/50 transition-colors"
        >
          <div className="flex items-center gap-2">
            <Settings className="h-4 w-4 text-muted-foreground" />
            <span className="text-sm font-medium">
              Personnaliser le plan comptable
            </span>
            {account.modifiedCount > 0 && (
              <span className="inline-flex items-center rounded-full bg-primary/10 px-2 py-0.5 text-xs font-medium text-primary">
                {account.modifiedCount}
              </span>
            )}
          </div>
          <div className="flex items-center gap-2">
            <span className="text-xs text-muted-foreground">{subtitle}</span>
            <span
              className={`text-muted-foreground transition-transform ${isOpen ? "rotate-90" : ""}`}
            >
              ▸
            </span>
          </div>
        </button>
      </CollapsibleTrigger>

      <CollapsibleContent>
        <div className="mt-2 space-y-4 rounded-lg border p-4">
          {GROUPS.map((group) => (
            <div key={group.title} className="space-y-3">
              <h3 className="text-xs font-semibold uppercase tracking-wider text-muted-foreground border-b pb-1">
                {group.title}
              </h3>
              {group.sections.map((section) => (
                <div key={section.subtitle} className="space-y-1.5">
                  <h4 className="text-[11px] font-medium text-muted-foreground/70 uppercase tracking-wide">
                    {section.subtitle}
                  </h4>
                  {section.fields.map((field) => (
                    <AccountField
                      key={field.path}
                      label={field.label}
                      path={field.path}
                      regex={getRegexForPath(field.path, group.regex)}
                      account={account}
                    />
                  ))}
                </div>
              ))}
            </div>
          ))}

          {/* Paramètres de contrôle */}
          <div className="space-y-3">
            <h3 className="text-xs font-semibold uppercase tracking-wider text-muted-foreground border-b pb-1">
              Paramètres de contrôle
            </h3>
            <ToleranceField account={account} />
          </div>

          {account.modifiedCount > 0 && (
            <div className="pt-2 border-t">
              {showResetConfirm ? (
                <div className="flex items-center gap-2">
                  <span className="text-sm text-muted-foreground">
                    Réinitialiser toutes les valeurs ?
                  </span>
                  <Button
                    variant="destructive"
                    size="sm"
                    onClick={() => {
                      account.resetAll();
                      setShowResetConfirm(false);
                    }}
                  >
                    Confirmer
                  </Button>
                  <Button
                    variant="outline"
                    size="sm"
                    onClick={() => setShowResetConfirm(false)}
                  >
                    Annuler
                  </Button>
                </div>
              ) : (
                <Button
                  variant="outline"
                  size="sm"
                  onClick={() => setShowResetConfirm(true)}
                  className="gap-1.5"
                >
                  <RotateCcw className="h-3 w-3" />
                  Réinitialiser les valeurs par défaut
                </Button>
              )}
            </div>
          )}

          {hasValidationErrors && (
            <p
              role="alert"
              className="text-xs text-red-500 dark:text-red-400"
            >
              Certains champs ont un format invalide. Corrigez-les avant de
              générer.
            </p>
          )}
        </div>
      </CollapsibleContent>
    </Collapsible>
  );
}

/**
 * Check if any override field has a validation error.
 * Exported for use in page.tsx.
 */
export function hasAccountValidationErrors(
  account: UseAccountOverridesReturn,
): boolean {
  if (!account.defaults) return false;
  for (const group of GROUPS) {
    for (const section of group.sections) {
      for (const field of section.fields) {
        const regex = getRegexForPath(field.path, group.regex);
        const value = account.getValue(field.path);
        if (value !== "" && !regex.test(value)) return true;
      }
    }
  }
  // Check tolerance field
  const tolValue = account.getValue("matching_tolerance");
  if (tolValue !== "") {
    const num = parseFloat(tolValue);
    if (isNaN(num) || num < 0.001 || num > 1.0) return true;
  }
  return false;
}
