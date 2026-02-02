"use client";

import { useState } from "react";
import { Mic, MicOff, Loader2 } from "lucide-react";
import { Button } from "@/components/ui/button";
import { Popover, PopoverAnchor, PopoverContent } from "@/components/ui/popover";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";
import { useVoiceInput } from "@/hooks/useVoiceInput";
import { WhisperModel } from "@/hooks/useWhisperTranscription";
import { cn } from "@/lib/utils";

interface VoiceInputButtonProps {
  onTranscript: (text: string) => void;
}

const MODEL_OPTIONS: { value: WhisperModel; label: string; size: string }[] = [
  { value: "whisper-tiny", label: "Tiny", size: "~40MB" },
  { value: "whisper-base", label: "Base", size: "~75MB" },
  { value: "whisper-small", label: "Small", size: "~250MB" },
];

export function VoiceInputButton({ onTranscript }: VoiceInputButtonProps) {
  const [settingsOpen, setSettingsOpen] = useState(false);

  const {
    isListening,
    isTranscribing,
    isSpeaking,
    isModelLoading,
    isModelReady,
    modelLoadingProgress,
    modelError,
    currentModel,
    startListening,
    stopListening,
    setModel,
  } = useVoiceInput({ onTranscript });

  const handleToggle = async () => {
    if (isListening) {
      stopListening();
    } else {
      try {
        await startListening();
      } catch (err) {
        console.error("Failed to start voice input:", err);
      }
    }
  };

  const handleContextMenu = (e: React.MouseEvent) => {
    e.preventDefault();
    setSettingsOpen(true);
  };

  const handleModelChange = async (model: WhisperModel) => {
    try {
      await setModel(model);
    } catch (err) {
      console.error("Failed to change model:", err);
    }
  };

  const getButtonState = () => {
    if (isModelLoading) return "loading";
    if (isTranscribing) return "transcribing";
    if (isSpeaking) return "speaking";
    if (isListening) return "listening";
    return "idle";
  };

  const state = getButtonState();

  return (
    <div className="fixed bottom-6 right-6 z-50">
      <Popover open={settingsOpen} onOpenChange={setSettingsOpen}>
        <PopoverAnchor asChild>
          <Button
            onClick={handleToggle}
            onContextMenu={handleContextMenu}
            disabled={isModelLoading}
            size="icon-lg"
            className={cn(
              "rounded-full shadow-lg transition-all duration-200",
              state === "idle" && "bg-primary hover:bg-primary/90",
              state === "listening" &&
                "bg-amber-500 hover:bg-amber-600 animate-pulse",
              state === "speaking" &&
                "bg-green-500 hover:bg-green-600 animate-pulse",
              state === "transcribing" && "bg-blue-500 hover:bg-blue-600",
              state === "loading" && "bg-muted"
            )}
          >
            {state === "loading" || state === "transcribing" ? (
              <Loader2 className="size-5 animate-spin text-white" />
            ) : state === "idle" ? (
              <Mic className="size-5 text-white" />
            ) : (
              <MicOff className="size-5 text-white" />
            )}
          </Button>
        </PopoverAnchor>
        <PopoverContent align="end" side="top" sideOffset={8} className="w-64">
          <div className="space-y-4">
            <div className="space-y-2">
              <label className="text-sm font-medium">Whisper Model</label>
              <Select
                value={currentModel || "whisper-tiny"}
                onValueChange={(v) => handleModelChange(v as WhisperModel)}
                disabled={isModelLoading || isListening}
              >
                <SelectTrigger className="w-full">
                  <SelectValue />
                </SelectTrigger>
                <SelectContent>
                  {MODEL_OPTIONS.map((opt) => (
                    <SelectItem key={opt.value} value={opt.value}>
                      <span>{opt.label}</span>
                      <span className="ml-2 text-muted-foreground text-xs">
                        {opt.size}
                      </span>
                    </SelectItem>
                  ))}
                </SelectContent>
              </Select>
              <p className="text-xs text-muted-foreground">
                Larger models are more accurate but slower to load.
              </p>
            </div>

            {modelError && (
              <p className="text-xs text-destructive">{modelError}</p>
            )}

            {isModelLoading && (
              <div className="space-y-1">
                <div className="flex justify-between text-xs text-muted-foreground">
                  <span>Loading model...</span>
                  <span>{modelLoadingProgress}%</span>
                </div>
                <div className="h-1.5 bg-muted rounded-full overflow-hidden">
                  <div
                    className="h-full bg-primary transition-all duration-300"
                    style={{ width: `${modelLoadingProgress}%` }}
                  />
                </div>
              </div>
            )}

            {isModelReady && (
              <p className="text-xs text-muted-foreground">
                Model loaded and ready.
              </p>
            )}
          </div>
        </PopoverContent>
      </Popover>
    </div>
  );
}
