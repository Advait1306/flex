"use client";

import { Mic, MicOff, Loader2 } from "lucide-react";
import { Button } from "@/components/ui/button";
import { useRealtimeTranscription } from "@/hooks/useRealtimeTranscription";
import { cn } from "@/lib/utils";

interface VoiceInputButtonProps {
  onTranscript: (text: string) => void;
}

export function VoiceInputButton({ onTranscript }: VoiceInputButtonProps) {
  const {
    isListening,
    isTranscribing,
    isSpeaking,
    isConnecting,
    error,
    startListening,
    stopListening,
  } = useRealtimeTranscription({ onTranscript });

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

  const getButtonState = () => {
    if (isConnecting) return "connecting";
    if (isTranscribing) return "transcribing";
    if (isSpeaking) return "speaking";
    if (isListening) return "listening";
    return "idle";
  };

  const state = getButtonState();

  return (
    <div className="absolute bottom-6 right-6 z-50">
      <Button
        onClick={handleToggle}
        disabled={isConnecting}
        size="icon-lg"
        title={error || undefined}
        className={cn(
          "rounded-full shadow-lg transition-all duration-200",
          state === "idle" && "bg-primary hover:bg-primary/90",
          state === "connecting" && "bg-amber-500 animate-pulse",
          state === "listening" &&
            "bg-amber-500 hover:bg-amber-600 animate-pulse",
          state === "speaking" &&
            "bg-green-500 hover:bg-green-600 animate-pulse",
          state === "transcribing" && "bg-blue-500 hover:bg-blue-600"
        )}
      >
        {state === "connecting" || state === "transcribing" ? (
          <Loader2 className="size-5 animate-spin text-white" />
        ) : state === "idle" ? (
          <Mic className="size-5 text-white" />
        ) : (
          <MicOff className="size-5 text-white" />
        )}
      </Button>
    </div>
  );
}
