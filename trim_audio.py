#!/usr/bin/env python3
"""Trim original ElevenLabs audio by compressing inter-sentence silences.

Takes 33.38s original → ~27s by reducing pauses from ~0.35s to ~0.08s each.
Keeps all speech at natural speed — no pitch or tempo changes.
"""

from pydub import AudioSegment
from pydub.silence import detect_nonsilent
import os

INPUT = "/opt/autonomous-ai/factpay/demo_frames/voiceover_elevenlabs_v2.mp3"
OUTPUT = "/opt/autonomous-ai/factpay/demo_frames/voiceover_trimmed.mp3"

# Load audio
audio = AudioSegment.from_mp3(INPUT)
print(f"Original duration: {len(audio)/1000:.2f}s")

# Detect non-silent chunks (speech segments)
# min_silence_len=200ms, silence_thresh=-28dBFS
chunks = detect_nonsilent(audio, min_silence_len=200, silence_thresh=-28)

print(f"Found {len(chunks)} speech segments:")
for i, (start, end) in enumerate(chunks):
    print(f"  Segment {i}: {start/1000:.2f}s - {end/1000:.2f}s ({(end-start)/1000:.2f}s)")

# Reconstruct audio with compressed pauses
GAP_MS = 80  # 80ms between sentences (natural but tight)
LEADING_SILENCE_MS = 50  # tiny lead-in

result = AudioSegment.silent(duration=LEADING_SILENCE_MS)

for i, (start, end) in enumerate(chunks):
    # Add speech segment (with a tiny margin on each side for natural sound)
    margin = 30  # 30ms margin to avoid clipping speech edges
    seg_start = max(0, start - margin)
    seg_end = min(len(audio), end + margin)
    result += audio[seg_start:seg_end]

    # Add gap between segments (not after the last one)
    if i < len(chunks) - 1:
        result += AudioSegment.silent(duration=GAP_MS)

# Add tiny trailing silence
result += AudioSegment.silent(duration=50)

print(f"\nTrimmed duration: {len(result)/1000:.2f}s")
print(f"Saved: {(len(audio) - len(result))/1000:.2f}s")

# Export
result.export(OUTPUT, format="mp3", bitrate="128k")
print(f"Saved to: {OUTPUT}")

# If still over 27s, try tighter gaps
if len(result) > 27500:
    print(f"\nStill over 27s. Trying tighter gaps (50ms)...")
    result2 = AudioSegment.silent(duration=30)
    for i, (start, end) in enumerate(chunks):
        margin = 25
        seg_start = max(0, start - margin)
        seg_end = min(len(audio), end + margin)
        result2 += audio[seg_start:seg_end]
        if i < len(chunks) - 1:
            result2 += AudioSegment.silent(duration=50)
    result2 += AudioSegment.silent(duration=30)
    print(f"Tighter duration: {len(result2)/1000:.2f}s")

    if len(result2) < len(result):
        result2.export(OUTPUT, format="mp3", bitrate="128k")
        print(f"Using tighter version. Saved to: {OUTPUT}")
