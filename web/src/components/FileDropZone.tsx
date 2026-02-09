"use client";

import { useCallback, useRef, useState } from "react";
import { Card } from "@/components/ui/card";
import { detectChannel } from "@/lib/channels";
import type { UploadedFile } from "@/lib/types";

interface FileDropZoneProps {
  files: UploadedFile[];
  onAddFiles: (newFiles: UploadedFile[]) => void;
}

export default function FileDropZone({ files, onAddFiles }: FileDropZoneProps) {
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

      onAddFiles(uploaded);
    },
    [onAddFiles]
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

  const unmatchedCount = files.filter((f) => f.channel === null).length;

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
        <p className="text-xs text-muted-foreground/60 mt-4">
          Fichiers acceptés : exports CSV de Shopify, ManoMano, Décathlon ou Leroy Merlin.
          Les fichiers sont identifiés automatiquement par leur nom.
        </p>
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

      {files.length > 0 && (
        <p className="text-sm text-muted-foreground mt-3 text-center">
          {files.length === 1 ? "1 fichier déposé" : `${files.length} fichiers déposés`}
          {unmatchedCount > 0 && (
            <span className="text-amber-600">
              {" · "}
              {unmatchedCount === 1 ? "1 non reconnu" : `${unmatchedCount} non reconnus`}
            </span>
          )}
        </p>
      )}
    </Card>
  );
}
