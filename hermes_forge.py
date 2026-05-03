import subprocess
import os
import json
import re
import sys
import time

# =========================
# ⚙️ CONFIG
# =========================
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
OUTPUT_DIR = os.path.join(BASE_DIR, "outputs")
SKILLS_FILE = os.path.join(BASE_DIR, "skills/skills.json")

os.makedirs(OUTPUT_DIR, exist_ok=True)
os.makedirs(os.path.dirname(SKILLS_FILE), exist_ok=True)

SYSTEM_PROMPT = """
You are a creative software builder.

Generate a COMPLETE single-file HTML app.

Rules:
- One HTML file only
- No external dependencies
- Must be interactive
- Clean UI
- Output ONLY raw HTML
"""

# =========================
# 🧠 INPUT MODE (FIXED)
# =========================
def get_user_prompt():
    if not sys.stdin.isatty():
        # 🔥 TELEGRAM MODE
        data = sys.stdin.read().strip()
        if data:
            return data

    # 💻 CLI MODE
    return input("Describe your app: ")


# =========================
# 🔥 RUN HERMES
# =========================
def run_hermes(prompt):
    full_prompt = f"{SYSTEM_PROMPT}\n\nUser request:\n{prompt}"

    result = subprocess.run(
        ["hermes", "chat", "-q", full_prompt, "-Q"],
        capture_output=True,
        text=True
    )

    return result.stdout


# =========================
# 🧹 CLEAN HTML
# =========================
def clean_html(output):
    start = output.find("<!DOCTYPE html>")
    if start == -1:
        start = output.lower().find("<html")

    if start != -1:
        return output[start:]

    return output


def is_valid(html):
    html_lower = html.lower()
    return (
        "<html" in html_lower and
        "</html>" in html_lower and
        "<script" in html_lower and
        len(html) > 500
    )


# =========================
# 🚀 MAIN
# =========================
def main():
    print("\n────────────────────────────")
    print("🚀 Hermes Forge")
    print("────────────────────────────\n")

    user_prompt = get_user_prompt()

    print("\n[Hermes Forge] Generating application...\n")

    output_file = os.path.join(
        OUTPUT_DIR,
        f"app_{int(time.time())}.html"
    )

    html = ""

    for attempt in range(3):
        html = run_hermes(user_prompt)
        html = clean_html(html)

        if is_valid(html):
            print(f"[Hermes Forge] Success on attempt {attempt + 1}")
            break

        print(f"[Hermes Forge] Retry {attempt + 1}...")

    else:
        print("[Hermes Forge] Failed to generate valid HTML")
        return

    with open(output_file, "w") as f:
        f.write(html)

    # 🔥 CRITICAL FOR TELEGRAM
    abs_path = os.path.abspath(output_file)
    print(f"OUTPUT_FILE:{abs_path}")

    print(f"\n✅ Done: {abs_path}")

    # CLI hint
    if sys.stdin.isatty():
        print("\n🌐 To view:")
        print("python -m http.server 8000")
        print(f"http://localhost:8000/outputs/{os.path.basename(output_file)}")


# =========================
# ▶️ RUN
# =========================
if __name__ == "__main__":
    main()
