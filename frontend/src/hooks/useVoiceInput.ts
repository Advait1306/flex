import { useState, useRef, useCallback, useEffect } from "react";
import { MicVAD, RealTimeVADOptions } from "@ricky0123/vad-web";
import {
  useWhisperTranscription,
  WhisperModel,
} from "./useWhisperTranscription";

interface UseVoiceInputOptions {
  onTranscript?: (text: string) => void;
  onSpeechStart?: () => void;
  onSpeechEnd?: () => void;
}

interface UseVoiceInputReturn {
  isListening: boolean;
  isTranscribing: boolean;
  isSpeaking: boolean;
  isModelLoading: boolean;
  isModelReady: boolean;
  modelLoadingProgress: number;
  modelError: string | null;
  currentModel: WhisperModel | null;
  startListening: () => Promise<void>;
  stopListening: () => void;
  setModel: (model: WhisperModel) => Promise<void>;
}

export function useVoiceInput(
  options: UseVoiceInputOptions = {}
): UseVoiceInputReturn {
  const { onTranscript, onSpeechStart, onSpeechEnd } = options;

  const [isListening, setIsListening] = useState(false);
  const [isTranscribing, setIsTranscribing] = useState(false);
  const [isSpeaking, setIsSpeaking] = useState(false);

  const vadRef = useRef<MicVAD | null>(null);
  const onTranscriptRef = useRef(onTranscript);
  const onSpeechStartRef = useRef(onSpeechStart);
  const onSpeechEndRef = useRef(onSpeechEnd);

  const {
    isLoading: isModelLoading,
    isReady: isModelReady,
    loadingProgress: modelLoadingProgress,
    error: modelError,
    transcribe,
    loadModel,
    currentModel,
  } = useWhisperTranscription();

  useEffect(() => {
    onTranscriptRef.current = onTranscript;
    onSpeechStartRef.current = onSpeechStart;
    onSpeechEndRef.current = onSpeechEnd;
  }, [onTranscript, onSpeechStart, onSpeechEnd]);

  const handleSpeechEnd = useCallback(
    async (audio: Float32Array) => {
      onSpeechEndRef.current?.();
      setIsSpeaking(false);
      setIsTranscribing(true);

      try {
        const text = await transcribe(audio);
        const trimmed = text.trim();
        if (trimmed) {
          onTranscriptRef.current?.(trimmed);
        }
      } catch (err) {
        console.error("Transcription error:", err);
      } finally {
        setIsTranscribing(false);
      }
    },
    [transcribe]
  );

  const handleSpeechStart = useCallback(() => {
    onSpeechStartRef.current?.();
    setIsSpeaking(true);
  }, []);

  const startListening = useCallback(async () => {
    if (isListening) return;

    if (!isModelReady) {
      await loadModel();
    }

    try {
      const vadOptions: Partial<RealTimeVADOptions> = {
        onSpeechStart: handleSpeechStart,
        onSpeechEnd: handleSpeechEnd,
        positiveSpeechThreshold: 0.5,
        negativeSpeechThreshold: 0.35,
        minSpeechFrames: 4,
        preSpeechPadFrames: 10,
        redemptionFrames: 8,
        baseAssetPath:
          "https://cdn.jsdelivr.net/npm/@ricky0123/vad-web@0.0.30/dist/",
        onnxWASMBasePath:
          "https://cdn.jsdelivr.net/npm/onnxruntime-web@1.22.0/dist/",
      };

      vadRef.current = await MicVAD.new(vadOptions);
      vadRef.current.start();
      setIsListening(true);
    } catch (err) {
      console.error("Failed to start VAD:", err);
      throw err;
    }
  }, [isListening, isModelReady, loadModel, handleSpeechStart, handleSpeechEnd]);

  const stopListening = useCallback(() => {
    if (vadRef.current) {
      vadRef.current.pause();
      vadRef.current.destroy();
      vadRef.current = null;
    }
    setIsListening(false);
    setIsSpeaking(false);
  }, []);

  const setModel = useCallback(
    async (model: WhisperModel) => {
      const wasListening = isListening;
      if (wasListening) {
        stopListening();
      }
      await loadModel(model);
      if (wasListening) {
        await startListening();
      }
    },
    [isListening, stopListening, loadModel, startListening]
  );

  useEffect(() => {
    return () => {
      if (vadRef.current) {
        vadRef.current.pause();
        vadRef.current.destroy();
        vadRef.current = null;
      }
    };
  }, []);

  return {
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
  };
}
