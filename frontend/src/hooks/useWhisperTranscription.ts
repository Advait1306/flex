import { useState, useRef, useCallback, useEffect } from "react";
import { pipeline, Pipeline } from "@huggingface/transformers";

export type WhisperModel = "whisper-tiny" | "whisper-base" | "whisper-small";

interface WhisperState {
  isLoading: boolean;
  isReady: boolean;
  loadingProgress: number;
  error: string | null;
}

interface UseWhisperTranscriptionReturn extends WhisperState {
  transcribe: (audioData: Float32Array) => Promise<string>;
  loadModel: (model?: WhisperModel) => Promise<void>;
  currentModel: WhisperModel | null;
}

const MODEL_MAP: Record<WhisperModel, string> = {
  "whisper-tiny": "onnx-community/whisper-tiny",
  "whisper-base": "onnx-community/whisper-base",
  "whisper-small": "onnx-community/whisper-small",
};

export function useWhisperTranscription(): UseWhisperTranscriptionReturn {
  const [state, setState] = useState<WhisperState>({
    isLoading: false,
    isReady: false,
    loadingProgress: 0,
    error: null,
  });
  const [currentModel, setCurrentModel] = useState<WhisperModel | null>(null);
  const pipelineRef = useRef<Pipeline | null>(null);

  const loadModel = useCallback(async (model: WhisperModel = "whisper-tiny") => {
    if (pipelineRef.current && currentModel === model) {
      return;
    }

    // Dispose of previous model to free memory
    if (pipelineRef.current) {
      await pipelineRef.current.dispose();
      pipelineRef.current = null;
    }

    setState({
      isLoading: true,
      isReady: false,
      loadingProgress: 0,
      error: null,
    });

    try {
      const transcriber = await pipeline(
        "automatic-speech-recognition",
        MODEL_MAP[model],
        {
          dtype: "fp32",
          device: "wasm",
          progress_callback: (progress: { progress?: number }) => {
            if (progress.progress !== undefined) {
              setState((prev) => ({
                ...prev,
                loadingProgress: Math.round(progress.progress!),
              }));
            }
          },
        }
      );

      pipelineRef.current = transcriber;
      setCurrentModel(model);
      setState({
        isLoading: false,
        isReady: true,
        loadingProgress: 100,
        error: null,
      });
    } catch (err) {
      setState({
        isLoading: false,
        isReady: false,
        loadingProgress: 0,
        error: err instanceof Error ? err.message : "Failed to load model",
      });
    }
  }, [currentModel]);

  const transcribe = useCallback(
    async (audioData: Float32Array): Promise<string> => {
      if (!pipelineRef.current) {
        throw new Error("Model not loaded. Call loadModel() first.");
      }

      const result = await pipelineRef.current(audioData, {
        sampling_rate: 16000,
        language: "english",
        task: "transcribe",
      });

      if (Array.isArray(result)) {
        return result.map((r) => r.text).join(" ");
      }
      return (result as { text: string }).text || "";
    },
    []
  );

  // Cleanup on unmount
  useEffect(() => {
    return () => {
      if (pipelineRef.current) {
        pipelineRef.current.dispose();
        pipelineRef.current = null;
      }
    };
  }, []);

  return {
    ...state,
    transcribe,
    loadModel,
    currentModel,
  };
}
