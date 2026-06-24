import Anthropic from "@anthropic-ai/sdk";
import { logger } from "./logger";
export interface JiraStoryInput {
  key: string;
  summary: string;
  description?: string | null;
  acceptanceCriteria?: string | null;
  priority?: string | null;
  status?: string | null;
  labels: string[];
  components: string[];
}

export interface TestCase {
  name: string;
  description: string;
  preconditions: string;
  steps: string;
  expectedResult: string;
  priority: string;
  status: string;
}

const MODEL = process.env.ANTHROPIC_MODEL ?? "claude-opus-4-5";

const SYSTEM_PROMPT = `You are a senior QA engineer. Given a Jira story, generate thorough test cases in JSON format.

Generate a variety of:
- Positive/happy-path scenarios
- Negative/error scenarios
- Boundary and edge cases
- Permission and access-control scenarios (if applicable)
- UI/UX field validation

Return ONLY a valid JSON array of test case objects. Each object must have these exact keys:
- name: string (concise, descriptive test case title)
- description: string (what this test case verifies)
- preconditions: string (required state before executing, or empty string)
- steps: string (pipe-separated steps: "Step 1 | Step 2 | Step 3")
- expectedResult: string (what should happen after the steps)
- priority: string ("Low" | "Medium" | "High" | "Critical")
- status: string (always "Draft")

Aim for 8–15 test cases. Do not include any text outside the JSON array.`;

export async function generateTestCases(story: JiraStoryInput): Promise<TestCase[]> {
  const apiKey = process.env.ANTHROPIC_API_KEY;
  if (!apiKey) {
    throw new Error("ANTHROPIC_API_KEY is required");
  }

  const client = new Anthropic({ apiKey });

  const storyText = [
    `Issue: ${story.key}`,
    `Summary: ${story.summary}`,
    story.description ? `Description:\n${story.description}` : "",
    story.acceptanceCriteria ? `Acceptance Criteria:\n${story.acceptanceCriteria}` : "",
    story.priority ? `Priority: ${story.priority}` : "",
    story.labels.length ? `Labels: ${story.labels.join(", ")}` : "",
    story.components.length ? `Components: ${story.components.join(", ")}` : "",
  ]
    .filter(Boolean)
    .join("\n\n");

  logger.info({ model: MODEL, jiraKey: story.key }, "Calling Anthropic to generate test cases");

  const message = await client.messages.create({
    model: MODEL,
    max_tokens: 4096,
    system: SYSTEM_PROMPT,
    messages: [
      {
        role: "user",
        content: `Generate test cases for this Jira story:\n\n${storyText}`,
      },
    ],
  });

  const raw = message.content
    .filter((b) => b.type === "text")
    .map((b) => (b as { text: string }).text)
    .join("");

  const jsonMatch = raw.match(/\[[\s\S]*\]/);
  if (!jsonMatch) {
    logger.error({ raw: raw.slice(0, 500) }, "AI response did not contain a JSON array");
    throw new Error("AI did not return a valid JSON array of test cases");
  }

  const parsed = JSON.parse(jsonMatch[0]) as TestCase[];
  logger.info({ count: parsed.length }, "Test cases generated");
  return parsed;
}
