import { useState, useRef, useCallback, useEffect } from "react";
import { api } from "@/lib/axios";

interface UseRealtimeTranscriptionOptions {
  onTranscript?: (text: string) => void;
  onSpeechStart?: () => void;
  onSpeechEnd?: () => void;
}

interface UseRealtimeTranscriptionReturn {
  isListening: boolean;
  isSpeaking: boolean;
  isTranscribing: boolean;
  isConnecting: boolean;
  error: string | null;
  startListening: () => Promise<void>;
  stopListening: () => void;
}

const SAMPLE_RATE = 24000;

function floatTo16BitPCM(float32Array: Float32Array): ArrayBuffer {
  const buffer = new ArrayBuffer(float32Array.length * 2);
  const view = new DataView(buffer);
  for (let i = 0; i < float32Array.length; i++) {
    const s = Math.max(-1, Math.min(1, float32Array[i]));
    view.setInt16(i * 2, s < 0 ? s * 0x8000 : s * 0x7fff, true);
  }
  return buffer;
}

function arrayBufferToBase64(buffer: ArrayBuffer): string {
  const bytes = new Uint8Array(buffer);
  let binary = "";
  for (let i = 0; i < bytes.byteLength; i++) {
    binary += String.fromCharCode(bytes[i]);
  }
  return btoa(binary);
}

export function useRealtimeTranscription(
  options: UseRealtimeTranscriptionOptions = {}
): UseRealtimeTranscriptionReturn {
  const { onTranscript, onSpeechStart, onSpeechEnd } = options;

  const [isListening, setIsListening] = useState(false);
  const [isSpeaking, setIsSpeaking] = useState(false);
  const [isTranscribing, setIsTranscribing] = useState(false);
  const [isConnecting, setIsConnecting] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const wsRef = useRef<WebSocket | null>(null);
  const audioContextRef = useRef<AudioContext | null>(null);
  const sourceRef = useRef<MediaStreamAudioSourceNode | null>(null);
  const processorRef = useRef<AudioWorkletNode | null>(null);
  const streamRef = useRef<MediaStream | null>(null);

  const onTranscriptRef = useRef(onTranscript);
  const onSpeechStartRef = useRef(onSpeechStart);
  const onSpeechEndRef = useRef(onSpeechEnd);

  useEffect(() => {
    onTranscriptRef.current = onTranscript;
    onSpeechStartRef.current = onSpeechStart;
    onSpeechEndRef.current = onSpeechEnd;
  }, [onTranscript, onSpeechStart, onSpeechEnd]);

  const cleanup = useCallback(() => {
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
    setIsListening(false);
    setIsSpeaking(false);
    setIsTranscribing(false);
    setIsConnecting(false);
  }, []);

  const startListening = useCallback(async () => {
    if (isListening || isConnecting) return;

    setError(null);
    setIsConnecting(true);

    try {
      // 1. Get ephemeral token from backend
      const { data } = await api.post("/api/transcription/session");
      const { client_secret } = data;

      // 2. Open WebSocket to OpenAI
      const ws = new WebSocket(
        "wss://api.openai.com/v1/realtime?intent=transcription",
        [
          "realtime",
          `openai-insecure-api-key.${client_secret.value}`,
          "openai-beta.realtime-v1",
        ]
      );
      wsRef.current = ws;

      await new Promise<void>((resolve, reject) => {
        ws.onopen = () => resolve();
        ws.onerror = () => reject(new Error("WebSocket connection failed"));
        const timeout = setTimeout(() => reject(new Error("Connection timeout")), 10000);
        ws.addEventListener("open", () => clearTimeout(timeout), { once: true });
      });

      // 3. Handle incoming messages
      ws.onmessage = (event) => {
        const msg = JSON.parse(event.data);

        switch (msg.type) {
          case "input_audio_buffer.speech_started":
            setIsSpeaking(true);
            setIsTranscribing(false);
            onSpeechStartRef.current?.();
            break;

          case "input_audio_buffer.speech_stopped":
            setIsSpeaking(false);
            setIsTranscribing(true);
            onSpeechEndRef.current?.();
            break;

          case "conversation.item.input_audio_transcription.completed":
            setIsTranscribing(false);
            if (msg.transcript?.trim()) {
              onTranscriptRef.current?.(msg.transcript.trim());
            }
            break;

          case "error":
            console.error("OpenAI Realtime error:", msg.error);
            setError(msg.error?.message || "Transcription error");
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

      // 4. Capture microphone audio
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

      // Create a ScriptProcessor to capture audio chunks
      // (AudioWorklet would be cleaner but requires a separate file)
      const source = audioContext.createMediaStreamSource(stream);
      sourceRef.current = source;

      const processor = audioContext.createScriptProcessor(4096, 1, 1);
      processor.onaudioprocess = (e) => {
        if (ws.readyState !== WebSocket.OPEN) return;
        const inputData = e.inputBuffer.getChannelData(0);
        const pcm16 = floatTo16BitPCM(inputData);
        const base64 = arrayBufferToBase64(pcm16);
        ws.send(JSON.stringify({
          type: "input_audio_buffer.append",
          audio: base64,
        }));
      };

      source.connect(processor);
      processor.connect(audioContext.destination);
      processorRef.current = processor as unknown as AudioWorkletNode;

      setIsConnecting(false);
      setIsListening(true);
    } catch (err) {
      console.error("Failed to start realtime transcription:", err);
      setError(err instanceof Error ? err.message : "Failed to start");
      cleanup();
      throw err;
    }
  }, [isListening, isConnecting, cleanup]);

  const stopListening = useCallback(() => {
    cleanup();
  }, [cleanup]);

  useEffect(() => {
    return () => {
      cleanup();
    };
  }, [cleanup]);

  return {
    isListening,
    isSpeaking,
    isTranscribing,
    isConnecting,
    error,
    startListening,
    stopListening,
  };
}
