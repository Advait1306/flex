"use client";

import { useCreateBlockNote } from "@blocknote/react";
import { BlockNoteView } from "@blocknote/shadcn";
import "@blocknote/shadcn/style.css";
import { Block } from "@blocknote/core";
import { useCallback, useEffect, useRef } from "react";

interface BlockEditorProps {
  docId: string;
  initialContent?: Block[];
  onChange?: (docId: string, content: Block[]) => void;
}

export function BlockEditor({
  docId,
  initialContent,
  onChange,
}: BlockEditorProps) {
  const saveTimeoutRef = useRef<NodeJS.Timeout | null>(null);

  const editor = useCreateBlockNote({
    initialContent: initialContent?.length ? initialContent : undefined,
    placeholders: {
      default: "Enter text...",
    },
  });

  const handleChange = useCallback(() => {
    if (saveTimeoutRef.current) {
      clearTimeout(saveTimeoutRef.current);
    }

    saveTimeoutRef.current = setTimeout(() => {
      const content = editor.document;
      onChange?.(docId, content);
    }, 500);
  }, [editor, docId, onChange]);

  useEffect(() => {
    return () => {
      if (saveTimeoutRef.current) {
        clearTimeout(saveTimeoutRef.current);
      }
    };
  }, []);

  return (
    <div className="w-full">
      <BlockNoteView
        editor={editor}
        onChange={handleChange}
        theme="light"
        sideMenu={false}
        slashMenu={false}
        formattingToolbar={false}
      />
    </div>
  );
}
