import { logger } from "./logger";

export class JiraError extends Error {
  constructor(
    public readonly statusCode: number,
    message: string,
  ) {
    super(message);
    this.name = "JiraError";
  }
}

export interface JiraStory {
  key: string;
  summary: string;
  description: string | null;
  acceptanceCriteria: string | null;
  priority: string | null;
  status: string | null;
  labels: string[];
  components: string[];
}

function extractTextFromAdf(node: unknown): string {
  if (!node || typeof node !== "object") return "";
  const n = node as Record<string, unknown>;
  if (n.type === "text" && typeof n.text === "string") return n.text;
  if (Array.isArray(n.content)) {
    return (n.content as unknown[]).map(extractTextFromAdf).join("\n");
  }
  return "";
}

function extractAc(fields: Record<string, unknown>): string | null {
  const candidates = ["customfield_10034", "customfield_10300", "customfield_10016"];
  for (const key of candidates) {
    const val = fields[key];
    if (typeof val === "string" && val.trim()) return val.trim();
    if (val && typeof val === "object") {
      const text = extractTextFromAdf(val);
      if (text.trim()) return text.trim();
    }
  }
  const desc = typeof fields.description === "string"
    ? fields.description
    : extractTextFromAdf(fields.description);
  const acMatch = desc.match(/acceptance criteria[:\s]+([\s\S]+?)(?:\n\n|$)/i);
  return acMatch ? acMatch[1].trim() : null;
}

export async function fetchJiraStory(jiraKey: string): Promise<JiraStory> {
  const baseUrl = process.env.JIRA_BASE_URL?.replace(/\/$/, "");
  const email = process.env.JIRA_EMAIL;
  const token = process.env.JIRA_API_TOKEN;

  if (!baseUrl || !email || !token) {
    throw new Error("JIRA_BASE_URL, JIRA_EMAIL, and JIRA_API_TOKEN are required");
  }

  const creds = Buffer.from(`${email}:${token}`).toString("base64");
  const fields = "summary,description,priority,status,labels,components,customfield_10034,customfield_10300,customfield_10016";
  const url = `${baseUrl}/rest/api/3/issue/${encodeURIComponent(jiraKey)}?fields=${fields}`;

  logger.info({ jiraKey }, "Fetching Jira story");

  const res = await fetch(url, {
    headers: {
      Authorization: `Basic ${creds}`,
      Accept: "application/json",
    },
  });

  if (!res.ok) {
    const body = await res.text().catch(() => "");
    logger.error({ status: res.status, body }, "Jira API error");
    const hint = res.status === 404
      ? `Issue "${jiraKey}" not found. Check the key and your project permissions.`
      : `Jira returned ${res.status}: ${body.slice(0, 200)}`;
    throw new JiraError(res.status, hint);
  }

  const data = (await res.json()) as Record<string, unknown>;
  const fields_ = (data.fields ?? {}) as Record<string, unknown>;

  const description =
    typeof fields_.description === "string"
      ? fields_.description
      : extractTextFromAdf(fields_.description) || null;

  const priority = (fields_.priority as Record<string, string> | null)?.name ?? null;
  const status = ((fields_.status as Record<string, unknown> | null)?.name as string) ?? null;
  const labels = (fields_.labels as string[] | null) ?? [];
  const components = ((fields_.components as Array<Record<string, string>> | null) ?? []).map(
    (c) => c.name
  );

  return {
    key: jiraKey,
    summary: (fields_.summary as string) ?? jiraKey,
    description,
    acceptanceCriteria: extractAc(fields_),
    priority,
    status,
    labels,
    components,
  };
}
