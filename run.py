APP_URL = "http://38.49.216.219:8000/outputs/app.html"

def run(prompt: str, context=None, **kwargs):
    if context:
        context["last_prompt"] = prompt

    text = f"""🎨 *Your app is ready!*

👉 [Open your app]({APP_URL})

_"{prompt}"_

What would you like to do next?
"""

    buttons = [
        [
            {"text": "🚀 Open App", "url": APP_URL}
        ],
        [
            {"text": "🔄 Regenerate", "callback_data": "regen"},
            {"text": "✨ Improve", "callback_data": "improve"},
        ],
        [
            {"text": "🎯 New Idea", "callback_data": "new"},
        ]
    ]

    return {
        "text": text,
        "telegram": {
            "parse_mode": "Markdown",
            "buttons": buttons
        }
    }


def on_callback(callback_data, context=None, **kwargs):
    last_prompt = context.get("last_prompt", "")

    if callback_data == "regen":
        return run(last_prompt, context=context)

    elif callback_data == "improve":
        improved = f"Improve this: {last_prompt}"
        return run(improved, context=context)

    elif callback_data == "new":
        return {
            "text": "💡 Send me a new idea!"
        }
