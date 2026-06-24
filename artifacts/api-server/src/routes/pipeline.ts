import { Router, type IRouter } from "express";
import { eq } from "drizzle-orm";
import { z } from "zod";
import { db, traceabilityEntriesTable } from "@workspace/db";
import {
  FetchStoryBody,
  GenerateTestCasesBody,
  PublishTestCasesBody,
  UpdateAutomationParams,
  UpdateAutomationBody,
} from "@workspace/api-zod";
import { fetchJiraStory, JiraError } from "../lib/jira";
import { generateTestCases } from "../lib/ai";
import { publishTestCases, publishOneTestCase, listFolders } from "../lib/browserstack";

const PublishOneBody = z.object({
  jiraKey: z.string().min(1),
  folderId: z.number(),
  projectId: z.number(),
  testCase: z.object({
    name: z.string().min(1),
    description: z.string(),
    preconditions: z.string(),
    steps: z.string(),
    expectedResult: z.string(),
    priority: z.string(),
    status: z.string(),
  }),
});

const router: IRouter = Router();

router.get("/pipeline/config", async (_req, res): Promise<void> => {
  res.json({
    jiraConfigured: !!(
      process.env.JIRA_BASE_URL &&
      process.env.JIRA_EMAIL &&
      process.env.JIRA_API_TOKEN
    ),
    anthropicConfigured: !!process.env.ANTHROPIC_API_KEY,
    browserstackConfigured: !!(
      process.env.BROWSERSTACK_USERNAME &&
      process.env.BROWSERSTACK_ACCESS_KEY
    ),
  });
});

router.post("/pipeline/fetch-story", async (req, res): Promise<void> => {
  const parsed = FetchStoryBody.safeParse(req.body);
  if (!parsed.success) {
    res.status(400).json({ error: parsed.error.message });
    return;
  }

  try {
    const story = await fetchJiraStory(parsed.data.jiraKey);
    res.json(story);
  } catch (err) {
    const msg = err instanceof Error ? err.message : String(err);
    req.log.error({ err }, "fetchStory failed");
    const status = err instanceof JiraError ? err.statusCode : 502;
    res.status(status).json({ error: msg });
  }
});

router.post("/pipeline/generate", async (req, res): Promise<void> => {
  const parsed = GenerateTestCasesBody.safeParse(req.body);
  if (!parsed.success) {
    res.status(400).json({ error: parsed.error.message });
    return;
  }

  try {
    const testCases = await generateTestCases(parsed.data.story);
    res.json({ testCases });
  } catch (err) {
    const msg = err instanceof Error ? err.message : String(err);
    req.log.error({ err }, "generateTestCases failed");
    res.status(502).json({ error: msg });
  }
});

router.post("/pipeline/publish", async (req, res): Promise<void> => {
  const parsed = PublishTestCasesBody.safeParse(req.body);
  if (!parsed.success) {
    res.status(400).json({ error: parsed.error.message });
    return;
  }

  const { jiraKey, folderId, projectId, testCases } = parsed.data;

  try {
    const results = await publishTestCases(projectId, folderId, testCases);

    for (const r of results) {
      if (r.success && r.tcId) {
        await db.insert(traceabilityEntriesTable).values({
          jiraKey,
          tcName: r.name,
          bsTcId: r.tcId,
          folderId,
        });
      }
    }

    const created = results.filter((r) => r.success).length;
    const failed = results.filter((r) => !r.success).length;

    res.json({
      total: results.length,
      created,
      failed,
      results,
    });
  } catch (err) {
    const msg = err instanceof Error ? err.message : String(err);
    req.log.error({ err }, "publishTestCases failed");
    res.status(502).json({ error: msg });
  }
});

router.get("/pipeline/browserstack-folders", async (req, res): Promise<void> => {
  const projectId = Number(req.query.projectId);
  if (!projectId || isNaN(projectId)) {
    res.status(400).json({ error: "projectId query parameter is required" });
    return;
  }

  try {
    const folders = await listFolders(projectId);
    res.json({ folders });
  } catch (err) {
    const msg = err instanceof Error ? err.message : String(err);
    req.log.error({ err }, "listFolders failed");
    res.status(502).json({ error: msg });
  }
});

router.post("/pipeline/publish-one", async (req, res): Promise<void> => {
  const parsed = PublishOneBody.safeParse(req.body);
  if (!parsed.success) {
    res.status(400).json({ error: parsed.error.message });
    return;
  }

  const { jiraKey, folderId, projectId, testCase } = parsed.data;

  try {
    const { tcId } = await publishOneTestCase(projectId, folderId, testCase);

    await db.insert(traceabilityEntriesTable).values({
      jiraKey,
      tcName: testCase.name,
      bsTcId: tcId,
      folderId,
    });

    res.json({ success: true, tcId, name: testCase.name });
  } catch (err) {
    const msg = err instanceof Error ? err.message : String(err);
    req.log.error({ err }, "publishOneTestCase failed");
    res.status(502).json({ success: false, error: msg, name: testCase.name });
  }
});

router.get("/pipeline/traceability", async (req, res): Promise<void> => {
  try {
    const entries = await db
      .select()
      .from(traceabilityEntriesTable)
      .orderBy(traceabilityEntriesTable.createdAt);

    const totalTestCases = entries.length;
    const automated = entries.filter((e) => e.automationMethod).length;
    const notAutomated = totalTestCases - automated;
    const automationCoveragePct =
      totalTestCases > 0 ? Math.round((automated / totalTestCases) * 100) : 0;
    const jiraStoriesCovered = new Set(entries.map((e) => e.jiraKey)).size;

    res.json({
      entries: entries.map((e) => ({
        ...e,
        createdAt: e.createdAt.toISOString(),
        updatedAt: e.updatedAt.toISOString(),
      })),
      stats: {
        totalTestCases,
        automated,
        notAutomated,
        automationCoveragePct,
        jiraStoriesCovered,
      },
    });
  } catch (err) {
    req.log.error({ err }, "getTraceability failed");
    res.status(500).json({ error: "Internal server error" });
  }
});

router.patch(
  "/pipeline/traceability/:entryId/automation",
  async (req, res): Promise<void> => {
    const params = UpdateAutomationParams.safeParse(req.params);
    if (!params.success) {
      res.status(400).json({ error: params.error.message });
      return;
    }

    const body = UpdateAutomationBody.safeParse(req.body);
    if (!body.success) {
      res.status(400).json({ error: body.error.message });
      return;
    }

    const [updated] = await db
      .update(traceabilityEntriesTable)
      .set({
        automationMethod: body.data.automationMethod ?? null,
        automationFile: body.data.automationFile ?? null,
        updatedAt: new Date(),
      })
      .where(eq(traceabilityEntriesTable.id, params.data.entryId))
      .returning();

    if (!updated) {
      res.status(404).json({ error: "Entry not found" });
      return;
    }

    res.json({
      ...updated,
      createdAt: updated.createdAt.toISOString(),
      updatedAt: updated.updatedAt.toISOString(),
    });
  }
);

export default router;
