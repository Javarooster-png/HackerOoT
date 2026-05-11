#!/usr/bin/env python3
"""Stamp a WAV smpl chunk with a full-length infinite forward loop."""
import sys
import struct
import wave

def add_wav_loop(wav_path):
    with wave.open(wav_path, 'rb') as wf:
        n_frames = wf.getnframes()
        sample_rate = wf.getframerate()

    sample_period = int(1e9 / sample_rate)

    smpl_payload = struct.pack('<IIIIIIIII',
        0,              # manufacturer
        0,              # product
        sample_period,  # nanoseconds per sample
        69,             # unity note (A4)
        0,              # pitch fraction
        0,              # SMPTE format
        0,              # SMPTE offset
        1,              # num loops
        0,              # sampler data size
    ) + struct.pack('<IIIIII',
        0,              # cue point id
        0,              # type: forward loop
        0,              # loop start sample
        n_frames - 1,   # loop end sample (inclusive)
        0,              # fraction
        0xFFFFFFFF,     # play count: 0xFFFFFFFF = infinite
    )

    smpl_chunk = b'smpl' + struct.pack('<I', len(smpl_payload)) + smpl_payload

    with open(wav_path, 'rb') as f:
        data = f.read()

    if data[:4] != b'RIFF' or data[8:12] != b'WAVE':
        sys.exit(f"error: {wav_path} is not a valid WAV file")

    data += smpl_chunk
    data = data[:4] + struct.pack('<I', len(data) - 8) + data[8:]

    with open(wav_path, 'wb') as f:
        f.write(data)

if __name__ == '__main__':
    if len(sys.argv) != 2:
        sys.exit(f"usage: {sys.argv[0]} <wav_file>")
    add_wav_loop(sys.argv[1])
