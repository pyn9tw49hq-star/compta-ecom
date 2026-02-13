import {
  Sheet,
  SheetContent,
  SheetHeader,
  SheetTitle,
  SheetDescription,
} from "@/components/ui/sheet";
import { CHANNEL_CONFIGS } from "@/lib/channels";

interface HelpDrawerProps {
  isOpen: boolean;
  onOpenChange: (open: boolean) => void;
}

/**
 * Non-modal side drawer listing file naming conventions per channel.
 * Content is static — derived from CHANNEL_CONFIGS, independent of upload state.
 */
export default function HelpDrawer({ isOpen, onOpenChange }: HelpDrawerProps) {
  return (
    <Sheet open={isOpen} onOpenChange={onOpenChange} modal={false}>
      <SheetContent
        side="right"
        className="w-full sm:w-[400px] sm:max-w-none overflow-y-auto"
        showOverlay={false}
      >
        <SheetHeader>
          <SheetTitle>Comment nommer vos fichiers</SheetTitle>
          <SheetDescription>
            Le nom de chaque fichier CSV doit commencer par un préfixe spécifique
            pour être reconnu automatiquement.
          </SheetDescription>
        </SheetHeader>

        <p className="text-sm text-muted-foreground mb-6">
          [...] = texte optionnel (ex&nbsp;: une date, un mois...).
        </p>

        {CHANNEL_CONFIGS.map((config) => {
          const Icon = config.meta.icon;
          const hasGroups = !!config.fileGroups;
          const fileCount = hasGroups
            ? config.fileGroups!.length
            : config.files.filter((f) => f.required).length;
          const fileWord = hasGroups
            ? (fileCount === 1 ? "mode" : "modes")
            : (fileCount === 1 ? "fichier" : "fichiers");

          return (
            <div key={config.key} className="mb-4">
              <div className="flex items-center gap-2 font-semibold text-sm mb-2">
                <Icon className={`h-4 w-4 ${config.meta.iconClass}`} aria-hidden="true" />
                <span className="uppercase">{config.meta.label}</span>
                <span className="font-normal text-muted-foreground">
                  ({fileCount} {fileWord})
                </span>
              </div>
              {config.fileGroups ? (
                <div className="ml-6 space-y-2">
                  <p className="text-sm text-muted-foreground">Choisissez l&apos;un des modes suivants&nbsp;:</p>
                  {config.fileGroups.map((group) => {
                    const groupFiles = config.files.filter((f) => group.slots.includes(f.key) && f.regex !== null);
                    const otherFiles = config.files.filter(
                      (f) => !config.fileGroups!.some((g) => g.slots.includes(f.key)) && f.regex !== null
                    );
                    return (
                      <div key={group.label}>
                        <p className="text-sm font-medium text-muted-foreground mb-1">{group.label}&nbsp;:</p>
                        <ul className="ml-2 space-y-1 text-sm">
                          {groupFiles.map((file) => (
                            <li key={file.key}>&bull; {file.patternHuman}</li>
                          ))}
                        </ul>
                        {otherFiles.length > 0 && group === config.fileGroups![0] && (
                          <ul className="ml-2 space-y-1 text-sm mt-1">
                            {otherFiles.map((file) => (
                              <li key={file.key} className="text-muted-foreground">
                                + {file.patternHuman} <span className="italic">(optionnel)</span>
                              </li>
                            ))}
                          </ul>
                        )}
                      </div>
                    );
                  })}
                  <p className="text-sm italic text-muted-foreground">Vous pouvez utiliser un seul mode à la fois.</p>
                </div>
              ) : (
                <ul className="ml-6 space-y-1 text-sm">
                  {config.files.filter((f) => f.required).map((file) => (
                    <li key={file.key}>&bull; {file.patternHuman}</li>
                  ))}
                  {config.files.filter((f) => !f.required).map((file) => (
                    <li key={file.key} className="text-muted-foreground">
                      + {file.patternHuman} <span className="italic">(optionnel)</span>
                    </li>
                  ))}
                </ul>
              )}
            </div>
          );
        })}

        <h3 className="font-semibold text-sm mb-2 mt-6">Exemples de noms valides</h3>
        <ul className="ml-4 space-y-1 text-sm text-muted-foreground">
          <li>&bull; Ventes Shopify Janv 2026.csv</li>
          <li>&bull; Transactions Shopify Février 2026.csv</li>
          <li>&bull; Détails versements Janvier 2026.csv</li>
          <li>&bull; Total des retours par commande Février 2026.csv</li>
          <li>&bull; CA Manomano 01-2026.csv</li>
          <li>&bull; Decathlon Mars.csv</li>
          <li>&bull; Leroy Merlin Q1 2026.csv</li>
        </ul>

        <div className="rounded-md border bg-muted/50 p-3 mt-6">
          <h3 className="font-semibold text-sm mb-1">Astuce</h3>
          <p className="text-sm text-muted-foreground">
            Vous n&apos;êtes pas obligé de traiter tous les canaux en même temps.
            Déposez uniquement les fichiers des canaux que vous souhaitez traiter.
          </p>
        </div>
      </SheetContent>
    </Sheet>
  );
}
