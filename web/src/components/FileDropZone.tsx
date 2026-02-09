"use client";

import { useCallback, useRef, useState } from "react";
import { X } from "lucide-react";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import { Card } from "@/components/ui/card";
import { detectChannel, getChannelMeta } from "@/lib/channels";
import type { UploadedFile } from "@/lib/types";

interface FileDropZoneProps {
  onFilesChange: (files: UploadedFile[]) => void;
}

function formatSize(bytes: number): string {
  if (bytes < 1024) return `${bytes} B`;
  if (bytes < 1024 * 1024) return `${(bytes / 1024).toFixed(1)} KB`;
  return `${(bytes / (1024 * 1024)).toFixed(1)} MB`;
}

export default function FileDropZone({ onFilesChange }: FileDropZoneProps) {
  const [files, setFiles] = useState<UploadedFile[]>([]);
  const [isDragOver, setIsDragOver] = useState(false);
  const inputRef = useRef<HTMLInputElement>(null);

  const addFiles = useCallback(
    (newFiles: FileList | File[]) => {
      const csvFiles = Array.from(newFiles).filter((f) =>
        f.name.toLowerCase().endsWith(".csv")
      );
      if (csvFiles.length === 0) return;

      const uploaded: UploadedFile[] = csvFiles.map((file) => ({
        file,
        channel: detectChannel(file.name),
      }));

      setFiles((prev) => {
        const updated = [...prev, ...uploaded];
        onFilesChange(updated);
        return updated;
      });
    },
    [onFilesChange]
  );

  const removeFile = useCallback(
    (index: number) => {
      setFiles((prev) => {
        const updated = prev.filter((_, i) => i !== index);
        onFilesChange(updated);
        return updated;
      });
    },
    [onFilesChange]
  );

  const handleDrop = useCallback(
    (e: React.DragEvent) => {
      e.preventDefault();
      setIsDragOver(false);
      addFiles(e.dataTransfer.files);
    },
    [addFiles]
  );

  const handleDragOver = useCallback((e: React.DragEvent) => {
    e.preventDefault();
    setIsDragOver(true);
  }, []);

  const handleDragLeave = useCallback((e: React.DragEvent) => {
    e.preventDefault();
    setIsDragOver(false);
  }, []);

  const handleInputChange = useCallback(
    (e: React.ChangeEvent<HTMLInputElement>) => {
      if (e.target.files && e.target.files.length > 0) {
        addFiles(e.target.files);
      }
      // Reset input so the same file can be re-selected
      e.target.value = "";
    },
    [addFiles]
  );

  const openFilePicker = useCallback(() => {
    inputRef.current?.click();
  }, []);

  const handleKeyDown = useCallback(
    (e: React.KeyboardEvent) => {
      if (e.key === "Enter" || e.key === " ") {
        e.preventDefault();
        openFilePicker();
      }
    },
    [openFilePicker]
  );

  return (
    <Card className="p-6">
      {/* Drop zone — uses role="button" for a11y, inner "Parcourir" is a span to avoid nested interactive elements */}
      <div
        role="button"
        tabIndex={0}
        aria-label="Zone de dépôt de fichiers CSV. Appuyez sur Entrée ou Espace pour parcourir les fichiers."
        onDrop={handleDrop}
        onDragOver={handleDragOver}
        onDragEnter={handleDragOver}
        onDragLeave={handleDragLeave}
        onKeyDown={handleKeyDown}
        onClick={openFilePicker}
        className={`border-2 border-dashed rounded-lg p-8 text-center cursor-pointer transition-colors focus:outline-none focus:ring-2 focus:ring-ring focus:ring-offset-2 ${
          isDragOver
            ? "border-primary bg-primary/5"
            : "border-muted-foreground/25 hover:border-primary/50"
        }`}
      >
        <p className="text-muted-foreground mb-2">
          Glissez-déposez vos fichiers CSV ici
        </p>
        <p className="text-sm text-muted-foreground/70 mb-4">ou</p>
        <span className="inline-flex items-center justify-center whitespace-nowrap rounded-md text-sm font-medium border border-input bg-background shadow-sm hover:bg-accent hover:text-accent-foreground h-9 px-4 py-2">
          Parcourir
        </span>
      </div>

      <input
        ref={inputRef}
        type="file"
        accept=".csv"
        multiple
        className="hidden"
        onChange={handleInputChange}
        data-testid="file-input"
        aria-label="Sélectionner des fichiers CSV"
      />

      {/* File list */}
      {files.length > 0 && (
        <ul className="mt-4 space-y-2" aria-label="Fichiers sélectionnés">
          {files.map((uploaded, index) => {
            const meta = getChannelMeta(uploaded.channel);
            const Icon = meta.icon;
            return (
              <li
                key={`${uploaded.file.name}-${index}`}
                className="flex items-center justify-between gap-3 rounded-md border px-3 py-2"
              >
                <div className="flex items-center gap-3 min-w-0">
                  <Icon className="h-4 w-4 shrink-0" aria-hidden="true" />
                  <span className="truncate text-sm font-medium">
                    {uploaded.file.name}
                  </span>
                  <span className="text-xs text-muted-foreground shrink-0">
                    {formatSize(uploaded.file.size)}
                  </span>
                  <Badge variant="outline" className={meta.badgeClass}>
                    {meta.label}
                  </Badge>
                </div>
                <Button
                  variant="ghost"
                  size="icon"
                  className="h-7 w-7 shrink-0"
                  onClick={(e) => {
                    e.stopPropagation();
                    removeFile(index);
                  }}
                  aria-label={`Retirer ${uploaded.file.name}`}
                >
                  <X className="h-4 w-4" />
                </Button>
              </li>
            );
          })}
        </ul>
      )}
    </Card>
  );
}
