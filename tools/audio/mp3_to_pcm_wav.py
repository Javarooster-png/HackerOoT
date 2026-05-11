#!/usr/bin/env python3
"""
Convert an MP3 to a standard PCM WAV (WAVE_FORMAT_PCM, mono, 16-bit).
"""
import subprocess
import sys
import wave

mp3_path  = sys.argv[1]
wav_path  = sys.argv[2]
rate      = int(sys.argv[3]) if len(sys.argv) > 3 else 64000

result = subprocess.run(
    ["ffmpeg", "-y", "-i", mp3_path, "-ac", "1", "-ar", str(rate), "-f", "s16le", "-"],
    capture_output=True,
)
if result.returncode != 0:
    sys.stderr.buffer.write(result.stderr)
    sys.exit(result.returncode)

with wave.open(wav_path, "wb") as w:
    w.setnchannels(1)
    w.setsampwidth(2)
    w.setframerate(rate)
    w.writeframes(result.stdout)
