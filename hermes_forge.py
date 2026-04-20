import subprocess
import os
import json

# Ensure directories exist
os.makedirs("outputs", exist_ok=True)
os.makedirs("skills", exist_ok=True)

SKILLS_FILE = "skills/skills.json"
OUTPUT_FILE = "outputs/app.html"

SYSTEM_PROMPT = """
You are a creative software builder.

Your job is to generate COMPLETE, working, single-file HTML applications.

You can build:
- Games (canvas-based)
- Visual tools (drawing apps, simulations)
- Audio tools (basic synthesizers, sequencers)
- Interactive demos

Requirements:
- Everything in ONE HTML file
- No external dependencies
- Must be interactive and usable
- Include UI where appropriate
- Prefer clean UI and modern styling

IMPORTANT:
- Output ONLY valid HTML code
- Do NOT include explanations
- Do NOT use markdown
- Do NOT wrap output in ```html
"""

def run_hermes(prompt):
    prompt_lower = prompt.lower()

    if "draw" in prompt_lower or "paint" in prompt_lower:
        mode = "visual"
    elif "music" in prompt_lower or "audio" in prompt_lower:
        mode = "audio"
    elif "game" in prompt_lower:
        mode = "game"
    else:
        mode = "app"

    memory_context = get_skill_context(mode)

    extra_rules = ""

    if mode != "game":
        extra_rules = """
This is NOT a game.
Do NOT include enemies, scoring, levels, or gameplay mechanics.
Focus only on the requested tool functionality.
"""

    full_prompt = f"""
You are building a {mode}.

{extra_rules}

""" + SYSTEM_PROMPT + memory_context + "\n\nUser request: " + prompt

    result = subprocess.run(
        ["hermes", "chat", "-q", full_prompt, "-Q"],
        capture_output=True,
        text=True
    )

    return result.stdout


def clean_html(output):
    start = output.find("<!DOCTYPE html>")
    if start == -1:
        start = output.lower().find("<html")

    if start != -1:
        return output[start:]

    return output


def load_skills():
    if not os.path.exists(SKILLS_FILE):
        return []
    with open(SKILLS_FILE, "r") as f:
        return json.load(f)


def save_skill(prompt, html):
    skills = load_skills()

    # Avoid duplicate prompts
    for s in skills:
        if s["prompt"] == prompt:
            return

    html_lower = html.lower()
    start = html_lower.find("<script")

    if start != -1:
        snippet = html[start:start + 3000]
    else:
        snippet = html[:3000]

    skills.append({
        "prompt": prompt,
        "snippet": snippet
    })

    with open(SKILLS_FILE, "w") as f:
        json.dump(skills, f, indent=2)


def get_skill_context(mode):
    skills = load_skills()
    if not skills:
        return ""

    # Only use memory for games (avoid bias)
    if mode != "game":
        return ""

    context = """
You have previously built working interactive games.

Reuse and adapt these patterns:
- game loops (requestAnimationFrame)
- movement systems
- collision detection
- scoring systems
- UI overlays and state handling

Examples:
"""

    for s in skills[-2:]:
        context += f"\n\nExample:\n{s['snippet']}\n"

    return context


def is_valid(html):
    html_lower = html.lower()
    return (
        "<html" in html_lower and
        "</html>" in html_lower and
        "<script" in html_lower and
        len(html) > 500
    )


def save_app(html):
    with open(OUTPUT_FILE, "w") as f:
        f.write(html)


def open_app():
    print(f"[Hermes Forge] Open '{OUTPUT_FILE}' in your browser (download or serve it)")


if __name__ == "__main__":
    user_prompt = input("Describe your app: ")

    print("\n[Hermes Forge] Generating application...\n")

    html = ""

    for attempt in range(3):
        html = run_hermes(user_prompt)
        html = clean_html(html)

        if is_valid(html):
            print(f"[Hermes Forge] Success on attempt {attempt + 1}")
            break

        print(f"[Hermes Forge] Retry {attempt + 1}...")

    else:
        print("[Hermes Forge] Failed to generate valid HTML after retries")
        print("\n--- DEBUG OUTPUT ---\n")
        print(html[:500])
        exit(1)

    save_app(html)
    save_skill(user_prompt, html)

    print("[Hermes Forge] App saved as outputs/app.html")
    open_app()
