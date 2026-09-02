"use client";

import { useCallback, useEffect, useRef, useState } from "react";
import type { WordTiming } from "@/lib/types";

export function useSpeechAudio() {
  const audioRef = useRef<HTMLAudioElement | null>(null);
  const ctxRef = useRef<AudioContext | null>(null);
  const analyserRef = useRef<AnalyserNode | null>(null);
  const dataRef = useRef<Uint8Array | null>(null);
  const destRef = useRef<MediaStreamAudioDestinationNode | null>(null);
  const levelRef = useRef(0);
  const rafRef = useRef<number | null>(null);
  const wordsRef = useRef<WordTiming[]>([]);
  
  // For Web Speech API fallback
  const synthIntervalRef = useRef<NodeJS.Timeout | null>(null);

  const [playing, setPlaying] = useState(false);
  const [muted, setMuted] = useState(false);
  const [wordIndex, setWordIndex] = useState(-1);

  useEffect(() => {
    const el = new Audio();
    el.preload = "auto";
    el.crossOrigin = "anonymous";
    audioRef.current = el;

    const onEnd = () => {
      setPlaying(false);
      setWordIndex(-1);
      levelRef.current = 0;
    };
    el.addEventListener("ended", onEnd);
    el.addEventListener("pause", () => setPlaying(false));
    el.addEventListener("play", () => setPlaying(true));

    return () => {
      el.removeEventListener("ended", onEnd);
      el.pause();
      if (rafRef.current) cancelAnimationFrame(rafRef.current);
      ctxRef.current?.close().catch(() => {});
      window.speechSynthesis.cancel();
      if (synthIntervalRef.current) clearInterval(synthIntervalRef.current);
    };
  }, []);

  const ensureAnalyser = useCallback(() => {
    if (ctxRef.current || !audioRef.current) return;
    try {
      const Ctx = window.AudioContext || (window as any).webkitAudioContext;
      const ctx = new Ctx();
      const src = ctx.createMediaElementSource(audioRef.current);
      const analyser = ctx.createAnalyser();
      analyser.fftSize = 512;
      src.connect(analyser);
      analyser.connect(ctx.destination);
      const dest = ctx.createMediaStreamDestination();
      analyser.connect(dest);
      destRef.current = dest;
      ctxRef.current = ctx;
      analyserRef.current = analyser;
      dataRef.current = new Uint8Array(analyser.frequencyBinCount);
    } catch {}
  }, []);

  useEffect(() => {
    const tick = () => {
      const el = audioRef.current;
      const analyser = analyserRef.current;
      const data = dataRef.current;

      if (analyser && data && el && !el.paused) {
        analyser.getByteTimeDomainData(data as any);
        let sum = 0;
        for (let i = 0; i < data.length; i++) {
          const v = (data[i] - 128) / 128;
          sum += v * v;
        }
        const rms = Math.sqrt(sum / data.length);
        levelRef.current = levelRef.current * 0.6 + Math.min(1, rms * 3.2) * 0.4;
      } else if (el && !el.paused) {
        levelRef.current = 0.35 + 0.35 * Math.abs(Math.sin(performance.now() / 90));
      } else if (!window.speechSynthesis.speaking) {
        levelRef.current *= 0.8; // fade out if nothing is playing
      }

      if (el && !el.paused && wordsRef.current.length) {
        const ms = el.currentTime * 1000;
        const words = wordsRef.current;
        let idx = -1;
        for (let i = words.length - 1; i >= 0; i--) {
          if (ms >= words[i].start_ms) { idx = i; break; }
        }
        setWordIndex((prev) => (prev === idx ? prev : idx));
      }

      rafRef.current = requestAnimationFrame(tick);
    };
    rafRef.current = requestAnimationFrame(tick);
    return () => { if (rafRef.current) cancelAnimationFrame(rafRef.current); };
  }, []);

  const play = useCallback(
    async (url: string, words: WordTiming[] = [], text?: string) => {
      window.speechSynthesis.cancel();
      if (synthIntervalRef.current) clearInterval(synthIntervalRef.current);

      // If backend gave an audio URL, use that
      if (url) {
        const el = audioRef.current;
        if (!el) return;
        wordsRef.current = words;
        setWordIndex(-1);
        ensureAnalyser();
        try { await ctxRef.current?.resume(); } catch {}
        el.src = url;
        el.muted = muted;
        try {
          await el.play();
        } catch {
          setPlaying(false);
        }
      } else if (text && !muted) {
        // Fallback to Web Speech API if Edge TTS failed
        setPlaying(true);
        const utterance = new SpeechSynthesisUtterance(text);
        
        // Pick a decent voice
        const voices = window.speechSynthesis.getVoices();
        const googleVoice = voices.find(v => v.name.includes("Google") || v.name.includes("Natural"));
        if (googleVoice) utterance.voice = googleVoice;
        
        utterance.rate = 1.0;
        
        utterance.onend = () => {
          setPlaying(false);
          levelRef.current = 0;
          if (synthIntervalRef.current) clearInterval(synthIntervalRef.current);
        };
        
        // Fake lip-sync amplitude while speaking
        synthIntervalRef.current = setInterval(() => {
          levelRef.current = window.speechSynthesis.speaking ? Math.random() * 0.8 : 0;
        }, 100);

        window.speechSynthesis.speak(utterance);
      }
    },
    [ensureAnalyser, muted]
  );

  const stop = useCallback(() => {
    audioRef.current?.pause();
    window.speechSynthesis.cancel();
    if (synthIntervalRef.current) clearInterval(synthIntervalRef.current);
    setPlaying(false);
  }, []);

  const toggleMute = useCallback(() => {
    setMuted((m) => {
      if (audioRef.current) audioRef.current.muted = !m;
      if (!m) window.speechSynthesis.cancel();
      return !m;
    });
  }, []);

  const getAudioStream = useCallback(() => {
    ensureAnalyser();
    return destRef.current?.stream ?? null;
  }, [ensureAnalyser]);

  return {
    play, stop, playing, muted, toggleMute,
    levelRef, wordIndex, audioRef, getAudioStream,
  };
}
