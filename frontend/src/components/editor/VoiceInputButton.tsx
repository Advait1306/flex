"use client";

import { Mic, MicOff, Loader2 } from "lucide-react";
import { Button } from "@/components/ui/button";
import { useRealtimeTranscription } from "@/hooks/useRealtimeTranscription";
import { cn } from "@/lib/utils";

interface VoiceInputButtonProps {
  onTranscript: (text: string) => void;
}

export function VoiceInputButton({ onTranscript }: VoiceInputButtonProps) {
  const { micState, error, startListening, stopListening } =
    useRealtimeTranscription({ onTranscript });

  const handleToggle = async () => {
    if (micState !== "off") {
      stopListening();
    } else {
      try {
        onTranscript(""); // claim a new block for this session
        await startListening();
      } catch (err) {
        console.error("Failed to start voice input:", err);
      }
    }
  };

  return (
    <div className="absolute bottom-6 right-6 z-50">
      <Button
        onClick={handleToggle}
        disabled={micState === "connecting"}
        size="icon-lg"
        title={error || undefined}
        className={cn(
          "rounded-full shadow-lg transition-all duration-200",
          micState === "off" && "bg-primary hover:bg-primary/90",
          micState === "connecting" && "bg-amber-500 animate-pulse",
          micState === "on" &&
            "bg-amber-500 hover:bg-amber-600 animate-pulse",
          micState === "speaking" &&
            "bg-green-500 hover:bg-green-600 animate-pulse"
        )}
      >
        {micState === "connecting" ? (
          <Loader2 className="size-5 animate-spin text-white" />
        ) : micState === "off" ? (
          <Mic className="size-5 text-white" />
        ) : (
          <MicOff className="size-5 text-white" />
        )}
      </Button>
    </div>
  );
}
