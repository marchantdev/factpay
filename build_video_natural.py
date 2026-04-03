#!/usr/bin/env python3
"""Build FactPay demo video with natural-speed audio (27.95s)."""

import subprocess
import os

FRAMES_DIR = "demo_frames"
AUDIO = f"{FRAMES_DIR}/voiceover_tight.mp3"
OUTPUT = "demo_final.mp4"

# Audio is 27.95s at natural speed.
# Opening slide (2s silent) + 25.95s voiceover content.
# Timings adjusted to match natural speech pace.
SEGMENTS = [
    # (frame, start_time, duration)
    ("rec_01_landing.png",           0.0,   2.0),   # Opening slide (silent)
    ("rec_02_typing.png",            2.0,   3.0),   # "Pay only for proven answers" + user types
    ("rec_03_verified.png",          5.0,   6.5),   # 402 + citation + payment signed + verified
    ("rec_04_typing_unverified.png", 11.5,  3.0),   # "USDC confirmed" + "unverifiable"
    ("rec_05_unverified.png",        14.5,  4.0),   # "No citation. Policy rejects. You pay nothing."
    ("rec_06_second_verified.png",   18.5,  3.0),   # Transition
    ("rec_07_final_state.png",       21.5,  8.0),   # Closing + outro (extra for crossfade)
]

TOTAL_DURATION = 27.95
CROSSFADE = 0.3

def build():
    os.chdir("/opt/autonomous-ai/factpay")

    # Step 1: Create frame clips
    frame_clips = []
    for i, (frame, start, dur) in enumerate(SEGMENTS):
        clip_path = f"/tmp/factpay_clip_{i:02d}.mp4"
        frame_path = os.path.join(FRAMES_DIR, frame)

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
        print(f"  Clip {i}: {frame} ({dur}s)")

    # Step 2: Crossfade filter
    inputs = []
    for clip in frame_clips:
        inputs.extend(["-i", clip])

    n = len(frame_clips)
    filter_parts = []
    offsets = []
    cumulative = 0
    for i in range(n - 1):
        _, _, dur = SEGMENTS[i]
        cumulative += dur
        offset = cumulative - CROSSFADE * (i + 1)
        offsets.append(offset)

    if n == 1:
        filter_complex = "[0:v]null[outv]"
    else:
        prev = "0:v"
        for i in range(n - 1):
            out_label = f"v{i}" if i < n - 2 else "outv"
            filter_parts.append(
                f"[{prev}][{i+1}:v]xfade=transition=fade:duration={CROSSFADE}:offset={offsets[i]:.3f}[{out_label}]"
            )
            prev = out_label
        filter_complex = ";".join(filter_parts)

    # Step 3: Composite video
    video_only = "/tmp/factpay_video_only.mp4"
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
    print("\n  Compositing...")
    result = subprocess.run(cmd, capture_output=True, text=True)
    if result.returncode != 0:
        print(f"  ERROR: {result.stderr[-500:]}")
        return False

    # Step 4: Merge audio
    cmd = [
        "ffmpeg", "-y",
        "-i", video_only,
        "-i", AUDIO,
        "-c:v", "copy",
        "-c:a", "aac", "-b:a", "192k",
        "-shortest",
        OUTPUT
    ]
    print("  Merging audio (natural speed)...")
    result = subprocess.run(cmd, capture_output=True, text=True)
    if result.returncode != 0:
        print(f"  ERROR: {result.stderr[-500:]}")
        return False

    # Final check
    probe = subprocess.run(
        ["ffprobe", "-v", "quiet", "-show_entries", "format=duration", "-of", "csv=p=0", OUTPUT],
        capture_output=True, text=True
    )
    final_dur = float(probe.stdout.strip())
    file_size = os.path.getsize(OUTPUT) / (1024 * 1024)

    print(f"\n  DONE: {OUTPUT}")
    print(f"  Duration: {final_dur:.2f}s (audio: natural 1.0x speed)")
    print(f"  Size: {file_size:.1f} MB")
    print(f"  Resolution: 1920x1080 @ 30fps")

    for clip in frame_clips:
        if os.path.exists(clip):
            os.remove(clip)
    if os.path.exists(video_only):
        os.remove(video_only)

    return final_dur <= 30.0

if __name__ == "__main__":
    print("Building FactPay demo video (natural audio speed)...")
    success = build()
    if success:
        print("\n  Video is under 30s limit.")
    else:
        print("\n  WARNING: Video may exceed 30s limit!")
