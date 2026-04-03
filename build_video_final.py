#!/usr/bin/env python3
"""Build final FactPay video: opening slide + original audio (trimmed) + closing slide.

Audio: voiceover_trimmed.mp3 (26.83s) — original ElevenLabs at natural speed,
       with inter-sentence pauses compressed.
Opening: 1.5s branded slide (silent)
Closing: 1.5s branded slide (silent)
Total target: ~29.8s
"""

import subprocess
import os

os.chdir("/opt/autonomous-ai/factpay")

FRAMES_DIR = "demo_frames"
AUDIO = f"{FRAMES_DIR}/voiceover_trimmed.mp3"
OUTPUT = "demo_final.mp4"

# Get exact audio duration
probe = subprocess.run(
    ["ffprobe", "-v", "quiet", "-show_entries", "format=duration", "-of", "csv=p=0", AUDIO],
    capture_output=True, text=True
)
AUDIO_DUR = float(probe.stdout.strip())
print(f"Trimmed audio duration: {AUDIO_DUR:.2f}s")

OPENING_DUR = 1.5
CLOSING_DUR = 1.5
CROSSFADE = 0.3
CONTENT_DUR = AUDIO_DUR  # Audio fills the content section

# 8 crossfades at 0.3s each = 2.4s eaten by transitions.
N_CROSSFADES = 8
CROSSFADE_COMPENSATION = N_CROSSFADES * CROSSFADE
TARGET_VIDEO_DUR = AUDIO_DUR + OPENING_DUR + CLOSING_DUR
# Remainder goes to the final content frame
REMAINDER = CONTENT_DUR - 20.0 + CROSSFADE_COMPENSATION

SEGMENTS = [
    # (frame, duration_seconds)
    ("opening_slide.png",              OPENING_DUR),   # Opening slide (silent)
    ("rec_01_landing.png",             1.5),            # "FactPay — pay only for proven answers"
    ("rec_02_typing.png",              3.0),            # User types + AI queries x402
    ("rec_03_verified.png",            5.5),            # Citation found, payment signed, verified
    ("rec_04_typing_unverified.png",   3.0),            # USDC confirmed + unverifiable question
    ("rec_05_unverified.png",          4.0),            # No citation, refuses to sign, pay nothing
    ("rec_06_second_verified.png",     3.0),            # OWS wallet enforces truth
    ("rec_07_final_state.png",         REMAINDER),      # Closing voiceover (remainder + crossfade compensation)
    ("closing_slide.png",             CLOSING_DUR),    # Closing slide (silent)
]

# Verify total
total = sum(dur for _, dur in SEGMENTS)
print(f"Planned total: {total:.2f}s (target: {AUDIO_DUR + OPENING_DUR + CLOSING_DUR:.2f}s)")

def build():
    # Step 1: Create frame clips
    frame_clips = []
    for i, (frame, dur) in enumerate(SEGMENTS):
        clip_path = f"/tmp/factpay_final_clip_{i:02d}.mp4"
        frame_path = os.path.join(FRAMES_DIR, frame)

        if not os.path.exists(frame_path):
            print(f"  ERROR: Missing frame {frame_path}")
            return False

        cmd = [
            "ffmpeg", "-y",
            "-loop", "1",
            "-i", frame_path,
            "-t", str(dur),
            "-vf", "scale=1920:1080:force_original_aspect_ratio=decrease,pad=1920:1080:(ow-iw)/2:(oh-ih)/2:color=0x1a1a2e",
            "-c:v", "libx264", "-preset", "medium", "-crf", "18",
            "-pix_fmt", "yuv420p",
            "-r", "30",
            clip_path
        ]
        subprocess.run(cmd, capture_output=True, check=True)
        frame_clips.append(clip_path)
        print(f"  Clip {i}: {frame} ({dur:.1f}s)")

    # Step 2: Crossfade filter chain
    inputs = []
    for clip in frame_clips:
        inputs.extend(["-i", clip])

    n = len(frame_clips)
    offsets = []
    cumulative = 0
    for i in range(n - 1):
        _, dur = SEGMENTS[i]
        cumulative += dur
        offset = cumulative - CROSSFADE * (i + 1)
        offsets.append(offset)

    filter_parts = []
    prev = "0:v"
    for i in range(n - 1):
        out_label = f"v{i}" if i < n - 2 else "outv"
        filter_parts.append(
            f"[{prev}][{i+1}:v]xfade=transition=fade:duration={CROSSFADE}:offset={offsets[i]:.3f}[{out_label}]"
        )
        prev = out_label
    filter_complex = ";".join(filter_parts)

    # Step 3: Composite video
    video_only = "/tmp/factpay_final_video_only.mp4"
    cmd = [
        "ffmpeg", "-y",
        *inputs,
        "-filter_complex", filter_complex,
        "-map", "[outv]",
        "-c:v", "libx264", "-preset", "medium", "-crf", "18",
        "-pix_fmt", "yuv420p",
        "-r", "30",
        video_only
    ]
    print("\n  Compositing with crossfades...")
    result = subprocess.run(cmd, capture_output=True, text=True)
    if result.returncode != 0:
        print(f"  ERROR: {result.stderr[-800:]}")
        return False

    # Check video duration
    probe = subprocess.run(
        ["ffprobe", "-v", "quiet", "-show_entries", "format=duration", "-of", "csv=p=0", video_only],
        capture_output=True, text=True
    )
    video_dur = float(probe.stdout.strip())
    print(f"  Video-only duration: {video_dur:.2f}s")

    # Step 4: Create audio track with silence padding for opening/closing
    padded_audio = "/tmp/factpay_padded_audio.wav"
    # Add 1.5s silence at start and 1.5s silence at end
    cmd = [
        "ffmpeg", "-y",
        "-f", "lavfi", "-i", f"anullsrc=channel_layout=mono:sample_rate=44100",
        "-i", AUDIO,
        "-f", "lavfi", "-i", f"anullsrc=channel_layout=mono:sample_rate=44100",
        "-filter_complex",
        f"[0:a]atrim=0:{OPENING_DUR}[silence1];"
        f"[2:a]atrim=0:{CLOSING_DUR}[silence2];"
        f"[silence1][1:a][silence2]concat=n=3:v=0:a=1[outa]",
        "-map", "[outa]",
        "-c:a", "pcm_s16le",
        padded_audio
    ]
    print("  Creating padded audio...")
    result = subprocess.run(cmd, capture_output=True, text=True)
    if result.returncode != 0:
        print(f"  Audio ERROR: {result.stderr[-500:]}")
        return False

    # Step 5: Merge video + padded audio
    cmd = [
        "ffmpeg", "-y",
        "-i", video_only,
        "-i", padded_audio,
        "-c:v", "copy",
        "-c:a", "aac", "-b:a", "192k",
        "-shortest",
        OUTPUT
    ]
    print("  Merging video + audio...")
    result = subprocess.run(cmd, capture_output=True, text=True)
    if result.returncode != 0:
        print(f"  Merge ERROR: {result.stderr[-500:]}")
        return False

    # Final check
    probe = subprocess.run(
        ["ffprobe", "-v", "quiet", "-show_entries", "format=duration", "-of", "csv=p=0", OUTPUT],
        capture_output=True, text=True
    )
    final_dur = float(probe.stdout.strip())
    file_size = os.path.getsize(OUTPUT) / (1024 * 1024)

    print(f"\n  DONE: {OUTPUT}")
    print(f"  Duration: {final_dur:.2f}s")
    print(f"  Size: {file_size:.1f} MB")
    print(f"  Resolution: 1920x1080 @ 30fps")
    print(f"  Audio: Original ElevenLabs at natural speed (pauses compressed)")

    # Cleanup
    for clip in frame_clips:
        if os.path.exists(clip):
            os.remove(clip)
    for tmp in [video_only, padded_audio]:
        if os.path.exists(tmp):
            os.remove(tmp)

    return final_dur <= 30.0

if __name__ == "__main__":
    print("Building FactPay final video (original audio, natural speed)...")
    success = build()
    if success:
        print("\n  Video is UNDER 30s limit. Ready for submission.")
    else:
        print("\n  WARNING: Video may exceed 30s or build failed!")
