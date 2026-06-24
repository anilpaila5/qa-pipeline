import { useQuery, useMutation, type UseQueryOptions, type UseMutationOptions } from "@tanstack/react-query";
import type { JiraStory, TestCase, TraceabilityResponse, ConfigStatus } from "@workspace/api-zod";

type QueryKey = readonly [string, ...unknown[]];

function jsonFetch<T>(url: string, init?: RequestInit): Promise<T> {
  return fetch(url, {
    ...init,
    headers: { ...init?.headers, "Content-Type": "application/json" },
  }).then(async (res: Response) => {
    const data = await res.json();
    if (!res.ok) throw data;
    return data as T;
  });
}

export function getGetTraceabilityQueryKey(): QueryKey {
  return ["/api/pipeline/traceability"] as const;
}

export function useHealthCheck(options?: UseQueryOptions<{ status: string }>) {
  return useQuery<{ status: string }>({
    queryKey: ["/api/healthz"] as const,
    queryFn: () => jsonFetch<{ status: string }>("/api/healthz"),
    ...options,
  });
}

export function useGetPipelineConfig(options?: UseQueryOptions<ConfigStatus>) {
  return useQuery<ConfigStatus>({
    queryKey: ["/api/pipeline/config"] as const,
    queryFn: () => jsonFetch<ConfigStatus>("/api/pipeline/config"),
    ...options,
  });
}

export function useGetTraceability(options?: UseQueryOptions<TraceabilityResponse>) {
  return useQuery<TraceabilityResponse>({
    queryKey: getGetTraceabilityQueryKey(),
    queryFn: () => jsonFetch<TraceabilityResponse>("/api/pipeline/traceability"),
    ...options,
  });
}

export function useFetchStory(options?: UseMutationOptions<JiraStory, unknown, { data: { jiraKey: string } }>) {
  return useMutation<JiraStory, unknown, { data: { jiraKey: string } }>({
    mutationFn: ({ data }) => jsonFetch<JiraStory>("/api/pipeline/fetch-story", {
      method: "POST",
      body: JSON.stringify(data),
    }),
    ...options,
  });
}

export function useGenerateTestCases(options?: UseMutationOptions<{ testCases: TestCase[] }, unknown, { data: { story: JiraStory } }>) {
  return useMutation<{ testCases: TestCase[] }, unknown, { data: { story: JiraStory } }>({
    mutationFn: ({ data }) => jsonFetch<{ testCases: TestCase[] }>("/api/pipeline/generate", {
      method: "POST",
      body: JSON.stringify(data),
    }),
    ...options,
  });
}

export function usePublishTestCases(options?: UseMutationOptions<
  { total: number; created: number; failed: number; results: Array<{ name: string; success: boolean }> },
  unknown,
  { data: { jiraKey: string; projectId: number; folderId: number; testCases: TestCase[] } }
>) {
  return useMutation({
    mutationFn: ({ data }) => jsonFetch("/api/pipeline/publish", {
      method: "POST",
      body: JSON.stringify(data),
    }),
    ...options,
  });
}

export function useUpdateAutomation(options?: UseMutationOptions<
  unknown,
  unknown,
  { entryId: number; data: { automationMethod?: string | null; automationFile?: string | null } }
>) {
  return useMutation({
    mutationFn: ({ entryId, data }) => jsonFetch(`/api/pipeline/traceability/${entryId}/automation`, {
      method: "PATCH",
      body: JSON.stringify(data),
    }),
    ...options,
  });
}

export type { JiraStory, TestCase };
