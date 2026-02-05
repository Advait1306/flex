"use client";

import { useCallback, useRef } from "react";
import useSWR from "swr";
import { api, fetcher } from "@/lib/axios";
import { BlockEditor, BlockEditorHandle } from "./BlockEditor";
import { VoiceInputButton } from "./VoiceInputButton";
import { TodoList } from "@/components/todos/TodoList";
import { FactsList } from "@/components/facts/FactsList";
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs";
import { Block } from "@blocknote/core";

export function DocumentFeed() {
  const editorRef = useRef<BlockEditorHandle | null>(null);

  const { data, error, isLoading, mutate } = useSWR<{ content: Block[] }>(
    "/api/freewrite",
    fetcher
  );

  const content = data?.content || [];

  const saveContent = useCallback(async (content: Block[]) => {
    try {
      await api.put("/api/freewrite", { content });
    } catch (error) {
      console.error("Failed to save freewrite:", error);
    }
  }, []);

  const handleChange = useCallback(
    (content: Block[]) => {
      saveContent(content);
      mutate({ content }, false);
    },
    [saveContent, mutate]
  );

  const handleTranscript = useCallback((text: string) => {
    if (editorRef.current) {
      editorRef.current.insertText(text);
    }
  }, []);

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
        <div className="text-destructive">Failed to load freewrite</div>
      </div>
    );
  }

  return (
    <div className="min-h-screen bg-background flex">
      {/* Editor - Left Side */}
      <div className="flex-1 min-w-0 py-8 border-r border-border min-h-screen">
        <BlockEditor
          ref={editorRef}
          initialContent={content}
          onChange={handleChange}
        />
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
