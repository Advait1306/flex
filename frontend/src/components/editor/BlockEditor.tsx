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
  save: () => void;
}

interface BlockEditorProps {
  initialContent?: Block[];
  onChange?: (content: Block[]) => void;
  onFocus?: () => void;
}

export const BlockEditor = forwardRef<BlockEditorHandle, BlockEditorProps>(
  function BlockEditor({ initialContent, onChange, onFocus }, ref) {
    const saveTimeoutRef = useRef<NodeJS.Timeout | null>(null);
    const lastContentRef = useRef<string>("");

    const editor = useCreateBlockNote({
      initialContent: initialContent?.length ? initialContent : undefined,
      placeholders: {
        default: "Enter text...",
      },
    });

    const save = useCallback(() => {
      if (saveTimeoutRef.current) {
        clearTimeout(saveTimeoutRef.current);
        saveTimeoutRef.current = null;
      }
      const content = editor.document;
      onChange?.(content);
    }, [editor, onChange]);

    useImperativeHandle(
      ref,
      () => ({
        insertText: (text: string) => {
          editor.focus();
          editor.insertInlineContent([{ type: "text", text: text + " " }]);
          console.log("[SAVE] audio");
          save();
        },
        focus: () => {
          editor.focus();
        },
        getEditor: () => editor,
        save,
      }),
      [editor, save]
    );

    const handleChange = useCallback(() => {
      if (saveTimeoutRef.current) {
        clearTimeout(saveTimeoutRef.current);
      }

      // Get current text content to detect sentence endings
      const blocks = editor.document;
      const currentText = blocks
        .map((block) => {
          if ("content" in block && Array.isArray(block.content)) {
            return block.content
              .map((item) => ("text" in item ? item.text : ""))
              .join("");
          }
          return "";
        })
        .join("\n");

      const prevText = lastContentRef.current;
      lastContentRef.current = currentText;

      // Check for sentence-ending punctuation or newline added
      const trimmedText = currentText.replace(/\n+$/, "");
      const lastChar = trimmedText.slice(-1);
      const endsWithSentence = /[.!?]/.test(lastChar);
      const newlineAdded = currentText.split("\n").length > prevText.split("\n").length;

      if (endsWithSentence) {
        console.log("[SAVE] punctuation");
        save();
      } else if (newlineAdded) {
        console.log("[SAVE] newline");
        save();
      } else {
        // Fallback: 1 second debounce
        saveTimeoutRef.current = setTimeout(() => {
          console.log("[SAVE] timeout");
          save();
        }, 1000);
      }
    }, [editor, save]);

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
