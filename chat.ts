import Anthropic from "@anthropic-ai/sdk";
import * as readline from "readline";

const client = new Anthropic();
const messages: Anthropic.MessageParam[] = [];

const rl = readline.createInterface({ input: process.stdin, output: process.stdout });
const ask = (prompt: string) => new Promise<string>((resolve) => rl.question(prompt, resolve));

console.log("Chat with Claude (Ctrl+C to quit)\n");

while (true) {
  const input = (await ask("You: ")).trim();
  if (!input) continue;

  messages.push({ role: "user", content: input });

  process.stdout.write("Claude: ");
  let responseText = "";

  const stream = client.messages.stream({
    model: "claude-opus-4-6",
    max_tokens: 64000,
    thinking: { type: "adaptive" },
    messages,
  });

  for await (const event of stream) {
    if (event.type === "content_block_delta" && event.delta.type === "text_delta") {
      process.stdout.write(event.delta.text);
      responseText += event.delta.text;
    }
  }

  console.log();
  messages.push({ role: "assistant", content: responseText });
}
