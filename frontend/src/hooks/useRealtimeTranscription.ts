import { useState, useRef, useCallback, useEffect } from "react";
import { getAuth } from "@/lib/auth";

export type MicState = "off" | "connecting" | "on" | "speaking";

interface UseRealtimeTranscriptionOptions {
  onTranscript?: (text: string) => void;
  onSpeechStart?: () => void;
  onSpeechEnd?: () => void;
}

interface UseRealtimeTranscriptionReturn {
  micState: MicState;
  error: string | null;
  startListening: () => Promise<void>;
  stopListening: () => void;
}

const SAMPLE_RATE = 16000;
const RMS_THRESHOLD = 0.015;
const SILENCE_TIMEOUT_MS = 600;

function floatTo16BitPCM(float32Array: Float32Array): ArrayBuffer {
  const buffer = new ArrayBuffer(float32Array.length * 2);
  const view = new DataView(buffer);
  for (let i = 0; i < float32Array.length; i++) {
    const s = Math.max(-1, Math.min(1, float32Array[i]));
    view.setInt16(i * 2, s < 0 ? s * 0x8000 : s * 0x7fff, true);
  }
  return buffer;
}

function computeRMS(float32Array: Float32Array): number {
  let sum = 0;
  for (let i = 0; i < float32Array.length; i++) {
    sum += float32Array[i] * float32Array[i];
  }
  return Math.sqrt(sum / float32Array.length);
}

export function useRealtimeTranscription(
  options: UseRealtimeTranscriptionOptions = {}
): UseRealtimeTranscriptionReturn {
  const { onTranscript, onSpeechStart, onSpeechEnd } = options;

  const [micState, setMicState] = useState<MicState>("off");
  const [error, setError] = useState<string | null>(null);

  const wsRef = useRef<WebSocket | null>(null);
  const audioContextRef = useRef<AudioContext | null>(null);
  const sourceRef = useRef<MediaStreamAudioSourceNode | null>(null);
  const processorRef = useRef<ScriptProcessorNode | null>(null);
  const streamRef = useRef<MediaStream | null>(null);
  const isSpeakingRef = useRef(false);
  const silenceTimerRef = useRef<ReturnType<typeof setTimeout> | null>(null);

  const onTranscriptRef = useRef(onTranscript);
  const onSpeechStartRef = useRef(onSpeechStart);
  const onSpeechEndRef = useRef(onSpeechEnd);

  useEffect(() => {
    onTranscriptRef.current = onTranscript;
    onSpeechStartRef.current = onSpeechStart;
    onSpeechEndRef.current = onSpeechEnd;
  }, [onTranscript, onSpeechStart, onSpeechEnd]);

  const cleanup = useCallback(() => {
    if (silenceTimerRef.current) {
      clearTimeout(silenceTimerRef.current);
      silenceTimerRef.current = null;
    }
    if (processorRef.current) {
      processorRef.current.disconnect();
      processorRef.current = null;
    }
    if (sourceRef.current) {
      sourceRef.current.disconnect();
      sourceRef.current = null;
    }
    if (audioContextRef.current) {
      audioContextRef.current.close();
      audioContextRef.current = null;
    }
    if (streamRef.current) {
      streamRef.current.getTracks().forEach((t) => t.stop());
      streamRef.current = null;
    }
    if (wsRef.current) {
      wsRef.current.close();
      wsRef.current = null;
    }
    isSpeakingRef.current = false;
    setMicState("off");
  }, []);

  const startListening = useCallback(async () => {
    if (micState !== "off") return;

    setError(null);
    setMicState("connecting");

    try {
      const apiUrl = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000";
      const wsBase = apiUrl.replace(/^http/, "ws");
      const token = getAuth();
      if (!token) {
        throw new Error("Not authenticated");
      }

      const ws = new WebSocket(
        `${wsBase}/api/transcription/ws?token=${encodeURIComponent(token)}`
      );
      wsRef.current = ws;

      await new Promise<void>((resolve, reject) => {
        ws.onopen = () => resolve();
        ws.onerror = () => reject(new Error("WebSocket connection failed"));
        const timeout = setTimeout(
          () => reject(new Error("Connection timeout")),
          10000
        );
        ws.addEventListener("open", () => clearTimeout(timeout), {
          once: true,
        });
      });

      ws.onmessage = (event) => {
        const msg = JSON.parse(event.data);

        switch (msg.type) {
          case "transcription.text.delta":
            if (msg.text) {
              onTranscriptRef.current?.(msg.text);
            }
            break;

          case "error":
            console.error("Transcription error:", msg.message);
            setError(msg.message || "Transcription error");
            break;
        }
      };

      ws.onclose = () => {
        cleanup();
      };

      ws.onerror = () => {
        setError("WebSocket error");
        cleanup();
      };

      const stream = await navigator.mediaDevices.getUserMedia({
        audio: {
          sampleRate: SAMPLE_RATE,
          channelCount: 1,
          echoCancellation: true,
          noiseSuppression: true,
        },
      });
      streamRef.current = stream;

      const audioContext = new AudioContext({ sampleRate: SAMPLE_RATE });
      audioContextRef.current = audioContext;

      const source = audioContext.createMediaStreamSource(stream);
      sourceRef.current = source;

      const processor = audioContext.createScriptProcessor(4096, 1, 1);
      processor.onaudioprocess = (e) => {
        if (ws.readyState !== WebSocket.OPEN) return;
        const inputData = e.inputBuffer.getChannelData(0);

        const rms = computeRMS(inputData);
        if (rms > RMS_THRESHOLD) {
          if (!isSpeakingRef.current) {
            isSpeakingRef.current = true;
            setMicState("speaking");
            onSpeechStartRef.current?.();
          }
          if (silenceTimerRef.current) {
            clearTimeout(silenceTimerRef.current);
            silenceTimerRef.current = null;
          }
        } else if (isSpeakingRef.current) {
          if (!silenceTimerRef.current) {
            silenceTimerRef.current = setTimeout(() => {
              isSpeakingRef.current = false;
              setMicState("on");
              onSpeechEndRef.current?.();
              silenceTimerRef.current = null;
            }, SILENCE_TIMEOUT_MS);
          }
        }

        const pcm16 = floatTo16BitPCM(inputData);
        ws.send(pcm16);
      };

      source.connect(processor);
      processor.connect(audioContext.destination);
      processorRef.current = processor;

      setMicState("on");
    } catch (err) {
      console.error("Failed to start realtime transcription:", err);
      setError(err instanceof Error ? err.message : "Failed to start");
      cleanup();
      throw err;
    }
  }, [micState, cleanup]);

  const stopListening = useCallback(() => {
    cleanup();
  }, [cleanup]);

  useEffect(() => {
    return () => {
      cleanup();
    };
  }, [cleanup]);

  return {
    micState,
    error,
    startListening,
    stopListening,
  };
}
