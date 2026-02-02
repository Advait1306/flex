"use client";

import { useCreateBlockNote } from "@blocknote/react";
import { BlockNoteView } from "@blocknote/shadcn";
import "@blocknote/shadcn/style.css";
import { Block, BlockNoteEditor } from "@blocknote/core";
import {
  useCallback,
  useEffect,
  useRef,
  useImperativeHandle,
  forwardRef,
} from "react";

export interface BlockEditorHandle {
  insertText: (text: string) => void;
  focus: () => void;
  getEditor: () => BlockNoteEditor;
}

interface BlockEditorProps {
  docId: string;
  initialContent?: Block[];
  onChange?: (docId: string, content: Block[]) => void;
  onFocus?: () => void;
}

export const BlockEditor = forwardRef<BlockEditorHandle, BlockEditorProps>(
  function BlockEditor({ docId, initialContent, onChange, onFocus }, ref) {
    const saveTimeoutRef = useRef<NodeJS.Timeout | null>(null);

    const editor = useCreateBlockNote({
      initialContent: initialContent?.length ? initialContent : undefined,
      placeholders: {
        default: "Enter text...",
      },
    });

    useImperativeHandle(
      ref,
      () => ({
        insertText: (text: string) => {
          editor.focus();
          editor.insertInlineContent([{ type: "text", text: text + " " }]);
        },
        focus: () => {
          editor.focus();
        },
        getEditor: () => editor,
      }),
      [editor]
    );

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

    const handleFocus = useCallback(() => {
      onFocus?.();
    }, [onFocus]);

    return (
      <div className="w-full" onFocus={handleFocus}>
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
);
