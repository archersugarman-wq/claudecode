import anthropic
from dataclasses import dataclass, field

client = anthropic.Anthropic()

SYSTEM_PROMPT = """You are Mythos, a master storyteller and collaborative narrative AI. \
Co-create rich, immersive stories with the user.

Strengths:
- Vivid, literary prose with sensory detail and emotional depth
- Distinct, authentic voices for characters and NPCs
- Consistent, richly-detailed world-building
- Advancing the story meaningfully in response to player choices
- Sustaining narrative tension and open story threads

Style:
- Paint the scene before moving it — atmosphere first
- Keep responses to 2-4 paragraphs unless the moment demands more
- Make player choices matter: consequences should feel real
- End each response with something unresolved — a question, a sound, a shadow at the door
- Follow the user's lead while steering toward dramatic moments

Story context (characters, world lore) appears in the system prompt when available. Use it consistently."""

W = 62


def hr(char="─"):
    return f"\033[90m{char * W}\033[0m"


def banner(text, char="═"):
    pad = W - len(text) - 2
    left = pad // 2
    return f"\033[35m{char * left} {text} {char * (pad - left)}\033[0m"


def teal(text):
    return f"\033[36m{text}\033[0m"


def yellow(text):
    return f"\033[33m{text}\033[0m"


def dim(text):
    return f"\033[90m{text}\033[0m"


@dataclass
class Story:
    title: str = "New Story"
    characters: dict = field(default_factory=dict)
    world: dict = field(default_factory=dict)
    messages: list = field(default_factory=list)

    def context(self) -> str | None:
        if not self.characters and not self.world:
            return None
        lines = [f"[Story: {self.title}]"]
        if self.characters:
            lines.append("\nCharacters:")
            for name, desc in self.characters.items():
                lines.append(f"  {name}: {desc}")
        if self.world:
            lines.append("\nWorld:")
            for aspect, desc in self.world.items():
                lines.append(f"  {aspect}: {desc}")
        return "\n".join(lines)

    def system_blocks(self) -> list:
        blocks = [{"type": "text", "text": SYSTEM_PROMPT, "cache_control": {"type": "ephemeral"}}]
        ctx = self.context()
        if ctx:
            blocks.append({"type": "text", "text": ctx})
        return blocks


def stream_response(story: Story, messages: list, max_tokens: int = 2048) -> str:
    response_text = ""
    with client.messages.stream(
        model="claude-sonnet-4-6",
        max_tokens=max_tokens,
        system=story.system_blocks(),
        messages=messages,
    ) as stream:
        for text in stream.text_stream:
            print(text, end="", flush=True)
            response_text += text
    print()
    return response_text


def cmd_help():
    print(f"\n{banner('Commands')}")
    rows = [
        ("/character",            "List all characters"),
        ("/character NAME DESC",  "Add or update a character"),
        ("/world",                "List all world lore"),
        ("/world ASPECT DESC",    "Add or update world lore"),
        ("/recap",                "Summarize the story so far"),
        ("/title NAME",           "Set the story title"),
        ("/new",                  "Start a fresh story"),
        ("/help",                 "Show this help"),
    ]
    for cmd, desc in rows:
        print(f"  {teal(cmd):<42} {dim(desc)}")
    print(hr())


def cmd_character(story: Story, args: list):
    if not args:
        if not story.characters:
            print(f"\n{dim('No characters yet.  →  /character <name> <description>')}")
            return
        print(f"\n{banner('Characters')}")
        for name, desc in story.characters.items():
            print(f"  {yellow(name)}: {desc}")
        print(hr())
    elif len(args) >= 2:
        name, desc = args[0], " ".join(args[1:])
        story.characters[name] = desc
        print(f"\n{dim(f'✓ Character saved: {name}')}")
    else:
        print(f"\n{dim('Usage: /character <name> <description>')}")


def cmd_world(story: Story, args: list):
    if not args:
        if not story.world:
            print(f"\n{dim('No world lore yet.  →  /world <aspect> <description>')}")
            return
        print(f"\n{banner('World Lore')}")
        for aspect, desc in story.world.items():
            print(f"  {yellow(aspect)}: {desc}")
        print(hr())
    elif len(args) >= 2:
        aspect, desc = args[0], " ".join(args[1:])
        story.world[aspect] = desc
        print(f"\n{dim(f'✓ World lore saved: {aspect}')}")
    else:
        print(f"\n{dim('Usage: /world <aspect> <description>')}")


def cmd_recap(story: Story):
    if not story.messages:
        print(f"\n{dim('No story to recap yet.')}")
        return
    recap_msgs = [
        *story.messages,
        {"role": "user", "content": "Give a brief 3-5 sentence recap of our story so far, written as a narrator's summary."},
    ]
    print(f"\n{banner('Story So Far')}")
    print(f"\n{teal('Mythos')} │ ", end="", flush=True)
    stream_response(story, recap_msgs, max_tokens=512)
    print(hr())


def main():
    story = Story()

    print(f"\n{banner('M Y T H O S')}")
    print(f"\n  {dim('A collaborative storytelling AI')}")
    print(f"  {dim('Type your story — or /help for commands.')}")
    print(f"\n{hr()}")

    while True:
        try:
            user_input = input(f"\n\033[32mYou\033[0m   │ ").strip()
        except (KeyboardInterrupt, EOFError):
            print(f"\n\n{dim('The story rests here. Until next time.')}\n")
            break

        if not user_input:
            continue

        if user_input.startswith("/"):
            parts = user_input[1:].split()
            if not parts:
                continue
            cmd, args = parts[0].lower(), parts[1:]

            match cmd:
                case "help":
                    cmd_help()
                case "character":
                    cmd_character(story, args)
                case "world":
                    cmd_world(story, args)
                case "recap":
                    cmd_recap(story)
                case "title":
                    if args:
                        story.title = " ".join(args)
                        print(f"\n{dim(f'✓ Title: {story.title}')}")
                    else:
                        print(f"\n{dim('Usage: /title <name>')}")
                case "new":
                    story = Story()
                    print(f"\n{dim('✓ New story started. The page is blank.')}")
                case _:
                    print(f"\n{dim(f'Unknown command: /{cmd}  — try /help')}")
        else:
            print(hr())
            print(f"\n{teal('Mythos')} │ ", end="", flush=True)
            story.messages.append({"role": "user", "content": user_input})
            response = stream_response(story, story.messages)
            story.messages.append({"role": "assistant", "content": response})
            print(hr())


if __name__ == "__main__":
    main()
