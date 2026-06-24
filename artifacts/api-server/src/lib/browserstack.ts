import { logger } from "./logger";

export interface TestCase {
  name: string;
  description: string;
  preconditions: string;
  steps: string;
  expectedResult: string;
  priority: string;
  status: string;
}

export interface PublishResultItem {
  name: string;
  tcId: string | null;
  success: boolean;
  error: string | null;
}

const BS_BASE = "https://test-management.browserstack.com/api/v2";

function buildAuth(): string {
  const username = process.env.BROWSERSTACK_USERNAME;
  const accessKey = process.env.BROWSERSTACK_ACCESS_KEY;
  if (!username || !accessKey) {
    throw new Error("BROWSERSTACK_USERNAME and BROWSERSTACK_ACCESS_KEY are required");
  }
  return `Basic ${Buffer.from(`${username}:${accessKey}`).toString("base64")}`;
}

function buildSteps(stepsStr: string, expectedResult: string): Array<{ step: string; expected_result: string }> {
  if (!stepsStr.trim()) {
    return expectedResult.trim()
      ? [{ step: "See description", expected_result: expectedResult }]
      : [];
  }
  return stepsStr
    .split("|")
    .map((s) => s.trim())
    .filter(Boolean)
    .map((step) => ({ step, expected_result: expectedResult }));
}

export async function publishOneTestCase(
  projectId: number,
  folderId: number,
  tc: TestCase
): Promise<{ tcId: string }> {
  const auth = buildAuth();
  const url = `${BS_BASE}/projects/${projectId}/folders/${folderId}/test-cases`;

  const payload = {
    name: tc.name,
    description: tc.description || "",
    preconditions: tc.preconditions || "",
    priority: tc.priority || "Medium",
    status: tc.status || "Draft",
    test_case_steps: buildSteps(tc.steps, tc.expectedResult || ""),
  };

  const res = await fetch(url, {
    method: "POST",
    headers: {
      Authorization: auth,
      "Content-Type": "application/json",
      Accept: "application/json",
    },
    body: JSON.stringify(payload),
  });

  const body = await res.json().catch(() => ({})) as Record<string, unknown>;

  if (!res.ok) {
    logger.error({ status: res.status, body }, "BrowserStack API error");
    throw new Error(`BrowserStack returned ${res.status}: ${JSON.stringify(body).slice(0, 300)}`);
  }

  const tcId = (body.id ?? body.tc_id ?? body.test_case_id ?? "") as string;
  return { tcId: String(tcId) };
}

export async function listFolders(projectId: number): Promise<Array<{ id: number; name: string }>> {
  const auth = buildAuth();
  const url = `${BS_BASE}/projects/${projectId}/folders`;

  const res = await fetch(url, {
    method: "GET",
    headers: {
      Authorization: auth,
      Accept: "application/json",
    },
  });

  if (!res.ok) {
    const body = await res.text().catch(() => "");
    throw new Error(`BrowserStack returned ${res.status}: ${body.slice(0, 200)}`);
  }

  const data = (await res.json()) as Record<string, unknown>;
  const folders = (data.folders ?? data.data ?? data) as Array<Record<string, unknown>>;

  if (!Array.isArray(folders)) return [];

  return folders.map((f) => ({
    id: Number(f.id ?? f.folder_id ?? 0),
    name: String(f.name ?? ""),
  })).filter((f) => f.id > 0);
}

export async function publishTestCases(
  projectId: number,
  folderId: number,
  testCases: TestCase[]
): Promise<PublishResultItem[]> {
  const results: PublishResultItem[] = [];

  for (const tc of testCases) {
    try {
      const { tcId } = await publishOneTestCase(projectId, folderId, tc);
      logger.info({ tcId, name: tc.name }, "Test case published");
      results.push({ name: tc.name, tcId, success: true, error: null });
    } catch (err) {
      const msg = err instanceof Error ? err.message : String(err);
      logger.warn({ name: tc.name, error: msg }, "Failed to publish test case");
      results.push({ name: tc.name, tcId: null, success: false, error: msg });
    }
  }

  return results;
}
