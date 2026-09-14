"use client";

import { useState } from "react";

import { uploadLeaseDocument } from "@/lib/api-client";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Input } from "@/components/ui/input";

export function DocumentUpload({ leaseId }: { leaseId: string }) {
  const [file, setFile] = useState<File | null>(null);
  const [title, setTitle] = useState("");
  const [notes, setNotes] = useState("");
  const [documentType, setDocumentType] = useState("licence");
  const [status, setStatus] = useState<"idle" | "uploading" | "success" | "error">("idle");
  const [message, setMessage] = useState("");

  async function onSubmit(event: React.FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (!file) {
      setStatus("error");
      setMessage("Choose a file before uploading.");
      return;
    }

    const formData = new FormData();
    formData.append("file", file);
    formData.append("document_type", documentType);
    formData.append("title", title || file.name);
    formData.append("notes", notes);
    formData.append("source", "web-ui");

    try {
      setStatus("uploading");
      setMessage("Uploading and extracting metadata...");
      await uploadLeaseDocument(leaseId, formData);
      setStatus("success");
      setMessage("Document uploaded and queued for review.");
      setFile(null);
      setTitle("");
      setNotes("");
      window.location.reload();
    } catch (error) {
      setStatus("error");
      setMessage(error instanceof Error ? error.message : "Upload failed.");
    }
  }

  return (
    <Card>
      <CardHeader>
        <CardTitle>Upload compliance document</CardTitle>
      </CardHeader>
      <CardContent>
        <form onSubmit={onSubmit} className="space-y-3">
          <div className="grid gap-3 sm:grid-cols-2">
            <label className="space-y-1 text-sm">
              <span className="text-muted-foreground">Document type</span>
              <select
                value={documentType}
                onChange={(event) => setDocumentType(event.target.value)}
                className="h-9 w-full rounded-md border border-input bg-background px-2 text-sm"
              >
                <option value="licence">Licence</option>
                <option value="obligation">Obligation</option>
                <option value="evidence">Evidence</option>
                <option value="general">General</option>
              </select>
            </label>

            <label className="space-y-1 text-sm">
              <span className="text-muted-foreground">Title</span>
              <Input
                value={title}
                onChange={(event) => setTitle(event.target.value)}
                placeholder="Environmental clearance"
              />
            </label>
          </div>

          <label className="block space-y-1 text-sm">
            <span className="text-muted-foreground">File</span>
            <Input
              type="file"
              accept=".pdf,.png,.jpg,.jpeg,.doc,.docx,.txt"
              onChange={(event) => setFile(event.target.files?.[0] ?? null)}
            />
          </label>

          <label className="block space-y-1 text-sm">
            <span className="text-muted-foreground">Notes</span>
            <textarea
              value={notes}
              onChange={(event) => setNotes(event.target.value)}
              rows={3}
              className="w-full rounded-md border border-input bg-background px-2 py-2 text-sm"
              placeholder="Optional context for the review team"
            />
          </label>

          <div className="flex items-center justify-between gap-3">
            <Button type="submit" disabled={status === "uploading"}>
              {status === "uploading" ? "Uploading..." : "Upload"}
            </Button>
            {message && (
              <span
                className={
                  status === "error"
                    ? "text-red-600"
                    : status === "success"
                      ? "text-emerald-600"
                      : "text-muted-foreground"
                }
              >
                {message}
              </span>
            )}
          </div>
        </form>
      </CardContent>
    </Card>
  );
}
