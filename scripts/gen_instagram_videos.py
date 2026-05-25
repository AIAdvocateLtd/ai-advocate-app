"""
Generate 2 short Sora 2 vertical (9:16, Instagram Reels) clips for the
AI Advocate launch content pack.

Run: python3 /app/scripts/gen_instagram_videos.py
"""
import os
import sys
import time
from dotenv import load_dotenv

sys.path.insert(0, os.path.abspath("/app/backend"))
load_dotenv("/app/backend/.env")

from emergentintegrations.llm.openai.video_generation import OpenAIVideoGeneration  # noqa: E402

API_KEY = os.environ["EMERGENT_LLM_KEY"]
OUT_DIR = "/app/frontend/public/instagram-pack/videos"
os.makedirs(OUT_DIR, exist_ok=True)

CLIPS = [
    {
        "name": "hero_phone_reveal",
        "duration": 8,
        "size": "1280x720",  # horizontal — Sora 2's only supported aspect via current SDK. User can re-crop to vertical in CapCut for Reels, or post as a Story/Feed.
        "prompt": (
            "Cinematic ad shot, 8 seconds, vertical 9:16. A British woman's hand (no face) "
            "in soft warm gold light slowly raises a sleek black smartphone. The phone screen "
            "lights up showing a luxurious dark UI with a gold 'AI ADVOCATE' logo and the words "
            "'Your AI Lawyer'. Subtle blurred bokeh of a London street at dusk in the background. "
            "Slow push-in. Premium, calming, trustworthy. No on-screen text other than what's "
            "naturally on the phone screen. No music."
        ),
    },
    {
        "name": "scales_brand_loop",
        "duration": 4,
        "size": "1280x720",
        "prompt": (
            "Cinematic 4-second loop, vertical 9:16. Highly detailed antique brass scales of "
            "justice slowly rotating on a dark mahogany surface, catching warm gold studio "
            "light. Soft shallow depth of field, museum-quality product shot. Pure black "
            "background. No text, no logos, no people. Looping seamless motion."
        ),
    },
]


def gen():
    print(f"Generating {len(CLIPS)} Sora 2 vertical clips → {OUT_DIR}")
    print("(Each clip takes 2-5 minutes — please be patient.)\n")
    for clip in CLIPS:
        out = f"{OUT_DIR}/{clip['name']}.mp4"
        if os.path.exists(out) and os.path.getsize(out) > 10_000:
            print(f"  [skip] {clip['name']}.mp4 already exists")
            continue
        print(f"  ⏳ Generating {clip['name']} ({clip['duration']}s, {clip['size']})…")
        t0 = time.time()
        try:
            gen = OpenAIVideoGeneration(api_key=API_KEY)
            video_bytes = gen.text_to_video(
                prompt=clip["prompt"],
                model="sora-2",
                size=clip["size"],
                duration=clip["duration"],
                max_wait_time=600,
            )
            if not video_bytes:
                print(f"  ❌ {clip['name']} returned no bytes")
                continue
            gen.save_video(video_bytes, out)
            sz = os.path.getsize(out) // 1024
            print(f"  ✅ {clip['name']}.mp4 ({sz} KB) — took {time.time()-t0:.0f}s")
        except Exception as e:
            print(f"  ❌ {clip['name']} failed: {e}")


if __name__ == "__main__":
    gen()
    print("\nManifest:")
    for f in sorted(os.listdir(OUT_DIR)):
        sz = os.path.getsize(f"{OUT_DIR}/{f}") // 1024
        print(f"  {f}: {sz} KB")
