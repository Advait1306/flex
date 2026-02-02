"use client";

import { useCallback, useRef, useEffect } from "react";
import useSWR from "swr";
import { api, fetcher } from "@/lib/axios";
import { BlockEditor } from "./BlockEditor";
import { Block } from "@blocknote/core";

interface Document {
  id: string;
  content: Block[];
}

export function DocumentFeed() {
  const initializedRef = useRef(false);

  const { data, error, isLoading, mutate } = useSWR<{ documents: Document[] }>(
    "/api/documents",
    fetcher
  );

  const documents = data?.documents || [];

  const createDocument = useCallback(async () => {
    try {
      const res = await api.post("/api/documents");
      const newDoc: Document = { id: res.data.id, content: [] };
      mutate(
        (current) => ({
          documents: [...(current?.documents || []), newDoc],
        }),
        false
      );
      return newDoc;
    } catch (error) {
      console.error("Failed to create document:", error);
      return null;
    }
  }, [mutate]);

  const saveDocument = useCallback(async (docId: string, content: Block[]) => {
    try {
      await api.put(`/api/documents/${docId}`, { content });
    } catch (error) {
      console.error("Failed to save document:", error);
    }
  }, []);

  useEffect(() => {
    if (initializedRef.current || isLoading) return;

    if (documents.length === 0) {
      initializedRef.current = true;
      createDocument();
    }
  }, [isLoading, documents.length, createDocument]);

  const handleDocumentChange = useCallback(
    (docId: string, content: Block[]) => {
      saveDocument(docId, content);
      mutate(
        (current) => ({
          documents:
            current?.documents.map((doc) =>
              doc.id === docId ? { ...doc, content } : doc
            ) || [],
        }),
        false
      );
    },
    [saveDocument, mutate]
  );

  if (isLoading) {
    return (
      <div className="flex min-h-screen items-center justify-center">
        <div className="text-muted-foreground">Loading...</div>
      </div>
    );
  }

  if (error) {
    return (
      <div className="flex min-h-screen items-center justify-center">
        <div className="text-destructive">Failed to load documents</div>
      </div>
    );
  }

  return (
    <div className="min-h-screen bg-background">
      <div className="mx-auto max-w-4xl py-8 border-l border-r border-border min-h-screen">
        {documents.map((doc, index) => (
          <div key={doc.id} className="relative">
            <BlockEditor
              docId={doc.id}
              initialContent={doc.content}
              onChange={handleDocumentChange}
            />
            {index < documents.length - 1 && (
              <div className="my-4 border-t border-border/40" />
            )}
          </div>
        ))}
      </div>
    </div>
  );
}
