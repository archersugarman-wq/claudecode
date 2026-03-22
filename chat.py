import anthropic

client = anthropic.Anthropic()
messages = []

print("Chat with Claude (Ctrl+C to quit)\n")

while True:
    try:
        user_input = input("You: ").strip()
    except (KeyboardInterrupt, EOFError):
        print()
        break

    if not user_input:
        continue

    messages.append({"role": "user", "content": user_input})

    print("Claude: ", end="", flush=True)
    with client.messages.stream(
        model="claude-opus-4-6",
        max_tokens=64000,
        thinking={"type": "adaptive"},
        messages=messages,
    ) as stream:
        response_text = ""
        for text in stream.text_stream:
            print(text, end="", flush=True)
            response_text += text

    print()
    messages.append({"role": "assistant", "content": response_text})
