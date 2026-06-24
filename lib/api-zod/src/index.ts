import { z } from "zod";

export const HealthCheckResponse = z.object({ status: z.string() });

export const ErrorResponse = z.object({ error: z.string() });

export const ConfigStatus = z.object({
  jiraConfigured: z.boolean(),
  anthropicConfigured: z.boolean(),
  browserstackConfigured: z.boolean(),
});

export const JiraFetchInput = z.object({
  jiraKey: z.string().min(1),
});

export const JiraStorySchema = z.object({
  key: z.string(),
  summary: z.string(),
  description: z.string().nullable(),
  acceptanceCriteria: z.string().nullable(),
  priority: z.string().nullable(),
  status: z.string().nullable(),
  labels: z.array(z.string()),
  components: z.array(z.string()),
});

export const StoryInput = z.object({
  story: JiraStorySchema,
});

export const TestCaseSchema = z.object({
  name: z.string(),
  description: z.string(),
  preconditions: z.string(),
  steps: z.string(),
  expectedResult: z.string(),
  priority: z.string(),
  status: z.string(),
});

export const GenerateResult = z.object({
  testCases: z.array(TestCaseSchema),
});

export const PublishInput = z.object({
  jiraKey: z.string(),
  folderId: z.number(),
  projectId: z.number(),
  testCases: z.array(TestCaseSchema),
});

export const PublishResultItem = z.object({
  name: z.string(),
  tcId: z.string().nullable(),
  success: z.boolean(),
  error: z.string().nullable(),
});

export const PublishResult = z.object({
  total: z.number(),
  created: z.number(),
  failed: z.number(),
  results: z.array(PublishResultItem),
});

export const TraceabilityEntrySchema = z.object({
  id: z.number(),
  jiraKey: z.string(),
  tcName: z.string(),
  bsTcId: z.string(),
  folderId: z.number().nullable(),
  automationMethod: z.string().nullable(),
  automationFile: z.string().nullable(),
  createdAt: z.string(),
  updatedAt: z.string(),
});

export const CoverageStats = z.object({
  totalTestCases: z.number(),
  automated: z.number(),
  notAutomated: z.number(),
  automationCoveragePct: z.number(),
  jiraStoriesCovered: z.number(),
});

export const TraceabilityResponse = z.object({
  entries: z.array(TraceabilityEntrySchema),
  stats: CoverageStats,
});

export const AutomationUpdate = z.object({
  automationMethod: z.string().nullable().optional(),
  automationFile: z.string().nullable().optional(),
});

export const UpdateAutomationParams = z.object({
  entryId: z.coerce.number(),
});

export const UpdateAutomationBody = z.object({
  automationMethod: z.string().nullable().optional(),
  automationFile: z.string().nullable().optional(),
});

export const FetchStoryBody = JiraFetchInput;
export const GenerateTestCasesBody = StoryInput;
export const PublishTestCasesBody = PublishInput;

export type HealthCheckResponse = z.infer<typeof HealthCheckResponse>;
export type ErrorResponse = z.infer<typeof ErrorResponse>;
export type ConfigStatus = z.infer<typeof ConfigStatus>;
export type JiraStory = z.infer<typeof JiraStorySchema>;
export type TestCase = z.infer<typeof TestCaseSchema>;
export type TraceabilityEntry = z.infer<typeof TraceabilityEntrySchema>;
export type CoverageStats = z.infer<typeof CoverageStats>;
export type TraceabilityResponse = z.infer<typeof TraceabilityResponse>;
export type AutomationUpdate = z.infer<typeof AutomationUpdate>;
