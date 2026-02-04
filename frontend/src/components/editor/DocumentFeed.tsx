"use client";

import { useCallback, useRef, useEffect, createRef } from "react";
import useSWR from "swr";
import { api, fetcher } from "@/lib/axios";
import { BlockEditor, BlockEditorHandle } from "./BlockEditor";
import { VoiceInputButton } from "./VoiceInputButton";
import { TodoList } from "@/components/todos/TodoList";
import { FactsList } from "@/components/facts/FactsList";
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs";
import { Block } from "@blocknote/core";

interface Document {
  id: string;
  content: Block[];
}

export function DocumentFeed() {
  const initializedRef = useRef(false);
  const editorRefs = useRef<Map<string, React.RefObject<BlockEditorHandle | null>>>(
    new Map()
  );
  const focusedEditorIdRef = useRef<string | null>(null);

  const { data, error, isLoading, mutate } = useSWR<{ documents: Document[] }>(
    "/api/documents",
    fetcher
  );

  const documents = data?.documents || [];

  const getEditorRef = useCallback((docId: string) => {
    if (!editorRefs.current.has(docId)) {
      editorRefs.current.set(docId, createRef<BlockEditorHandle>());
    }
    return editorRefs.current.get(docId)!;
  }, []);

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

  const handleEditorFocus = useCallback((docId: string) => {
    focusedEditorIdRef.current = docId;
  }, []);

  const handleTranscript = useCallback((text: string) => {
    const focusedId = focusedEditorIdRef.current;
    if (focusedId) {
      const ref = editorRefs.current.get(focusedId);
      if (ref?.current) {
        ref.current.insertText(text);
        return;
      }
    }

    if (documents.length > 0) {
      const firstDocId = documents[0].id;
      const ref = editorRefs.current.get(firstDocId);
      if (ref?.current) {
        ref.current.insertText(text);
      }
    }
  }, [documents]);

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
    <div className="min-h-screen bg-background flex">
      {/* Document Editor - Left Side */}
      <div className="flex-1 min-w-0 py-8 border-r border-border min-h-screen">
        {documents.map((doc, index) => (
          <div key={doc.id} className="relative">
            <BlockEditor
              ref={getEditorRef(doc.id)}
              docId={doc.id}
              initialContent={doc.content}
              onChange={handleDocumentChange}
              onFocus={() => handleEditorFocus(doc.id)}
            />
            {index < documents.length - 1 && (
              <div className="my-4 border-t border-border/40" />
            )}
          </div>
        ))}
      </div>

      {/* Sidebar - Right Side */}
      <div className="min-w-[500px] w-[500px] shrink-0 border-l border-border bg-muted/30 h-screen sticky top-0 flex flex-col">
        <Tabs defaultValue="todos" className="flex flex-col h-full">
          <div className="p-6 pb-0">
            <TabsList>
              <TabsTrigger value="todos">Todos</TabsTrigger>
              <TabsTrigger value="facts">Facts</TabsTrigger>
            </TabsList>
          </div>
          <TabsContent value="todos" className="flex-1 overflow-y-auto p-6 pt-4 mt-0">
            <TodoList />
          </TabsContent>
          <TabsContent value="facts" className="flex-1 overflow-y-auto p-6 pt-4 mt-0">
            <FactsList />
          </TabsContent>
        </Tabs>
      </div>

      <VoiceInputButton onTranscript={handleTranscript} />
    </div>
  );
}
