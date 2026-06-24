import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { useGetPipelineConfig, useGetTraceability } from "@workspace/api-client-react";
import { CheckCircle2, XCircle, Activity, BarChart, Server, Layers } from "lucide-react";
import { Skeleton } from "@/components/ui/skeleton";
import { Progress } from "@/components/ui/progress";

export default function Dashboard() {
  const { data: config, isLoading: isConfigLoading } = useGetPipelineConfig();
  const { data: traceability, isLoading: isTraceabilityLoading } = useGetTraceability();

  const renderStatusIcon = (status?: boolean) => {
    if (status) return <CheckCircle2 className="h-5 w-5 text-green-500" />;
    return <XCircle className="h-5 w-5 text-red-500" />;
  };

  return (
    <div className="p-8 max-w-7xl mx-auto w-full space-y-8 animate-in fade-in zoom-in duration-500">
      <div className="space-y-2">
        <h1 className="text-3xl font-bold tracking-tight">QA Pipeline Dashboard</h1>
        <p className="text-muted-foreground">
          Overview of system integrations and automation coverage.
        </p>
      </div>

      <div className="grid gap-6 md:grid-cols-2 lg:grid-cols-4">
        <Card>
          <CardHeader className="flex flex-row items-center justify-between pb-2 space-y-0">
            <CardTitle className="text-sm font-medium">Jira Integration</CardTitle>
            <Layers className="h-4 w-4 text-muted-foreground" />
          </CardHeader>
          <CardContent>
            {isConfigLoading ? <Skeleton className="h-8 w-20" /> : (
              <div className="flex items-center space-x-2">
                {renderStatusIcon(config?.jiraConfigured)}
                <span className="font-semibold text-lg">{config?.jiraConfigured ? "Connected" : "Missing"}</span>
              </div>
            )}
          </CardContent>
        </Card>
        
        <Card>
          <CardHeader className="flex flex-row items-center justify-between pb-2 space-y-0">
            <CardTitle className="text-sm font-medium">Anthropic AI</CardTitle>
            <Activity className="h-4 w-4 text-muted-foreground" />
          </CardHeader>
          <CardContent>
            {isConfigLoading ? <Skeleton className="h-8 w-20" /> : (
              <div className="flex items-center space-x-2">
                {renderStatusIcon(config?.anthropicConfigured)}
                <span className="font-semibold text-lg">{config?.anthropicConfigured ? "Connected" : "Missing"}</span>
              </div>
            )}
          </CardContent>
        </Card>

        <Card>
          <CardHeader className="flex flex-row items-center justify-between pb-2 space-y-0">
            <CardTitle className="text-sm font-medium">BrowserStack</CardTitle>
            <Server className="h-4 w-4 text-muted-foreground" />
          </CardHeader>
          <CardContent>
            {isConfigLoading ? <Skeleton className="h-8 w-20" /> : (
              <div className="flex items-center space-x-2">
                {renderStatusIcon(config?.browserstackConfigured)}
                <span className="font-semibold text-lg">{config?.browserstackConfigured ? "Connected" : "Missing"}</span>
              </div>
            )}
          </CardContent>
        </Card>

        <Card>
          <CardHeader className="flex flex-row items-center justify-between pb-2 space-y-0">
            <CardTitle className="text-sm font-medium">Test Coverage</CardTitle>
            <BarChart className="h-4 w-4 text-muted-foreground" />
          </CardHeader>
          <CardContent>
            {isTraceabilityLoading ? <Skeleton className="h-8 w-20" /> : (
              <div className="space-y-2">
                <div className="flex items-center justify-between text-sm">
                  <span className="font-semibold text-lg">{traceability?.stats.automationCoveragePct.toFixed(1)}%</span>
                  <span className="text-muted-foreground">{traceability?.stats.automated} / {traceability?.stats.totalTestCases}</span>
                </div>
                <Progress value={traceability?.stats.automationCoveragePct || 0} className="h-2" />
              </div>
            )}
          </CardContent>
        </Card>
      </div>

      <div className="grid gap-6 md:grid-cols-2">
        <Card className="col-span-2">
          <CardHeader>
            <CardTitle>Recent Traceability Entries</CardTitle>
            <CardDescription>Latest test cases published from Jira stories.</CardDescription>
          </CardHeader>
          <CardContent>
            {isTraceabilityLoading ? (
              <div className="space-y-4">
                <Skeleton className="h-10 w-full" />
                <Skeleton className="h-10 w-full" />
                <Skeleton className="h-10 w-full" />
              </div>
            ) : (
              <div className="relative w-full overflow-auto">
                <table className="w-full caption-bottom text-sm">
                  <thead className="[&_tr]:border-b">
                    <tr className="border-b transition-colors hover:bg-muted/50 data-[state=selected]:bg-muted">
                      <th className="h-12 px-4 text-left align-middle font-medium text-muted-foreground">Jira Key</th>
                      <th className="h-12 px-4 text-left align-middle font-medium text-muted-foreground">Test Case</th>
                      <th className="h-12 px-4 text-left align-middle font-medium text-muted-foreground">BrowserStack ID</th>
                      <th className="h-12 px-4 text-left align-middle font-medium text-muted-foreground">Automation</th>
                    </tr>
                  </thead>
                  <tbody className="[&_tr:last-child]:border-0">
                    {traceability?.entries.slice(0, 5).map((entry) => (
                      <tr key={entry.id} className="border-b transition-colors hover:bg-muted/50 data-[state=selected]:bg-muted">
                        <td className="p-4 font-medium">{entry.jiraKey}</td>
                        <td className="p-4">{entry.tcName}</td>
                        <td className="p-4 font-mono text-xs">{entry.bsTcId}</td>
                        <td className="p-4">
                          {entry.automationMethod ? (
                            <span className="inline-flex items-center rounded-md bg-green-50 px-2 py-1 text-xs font-medium text-green-700 ring-1 ring-inset ring-green-600/20">
                              Automated ({entry.automationMethod})
                            </span>
                          ) : (
                            <span className="inline-flex items-center rounded-md bg-yellow-50 px-2 py-1 text-xs font-medium text-yellow-800 ring-1 ring-inset ring-yellow-600/20">
                              Manual
                            </span>
                          )}
                        </td>
                      </tr>
                    ))}
                    {traceability?.entries.length === 0 && (
                      <tr>
                        <td colSpan={4} className="p-4 text-center text-muted-foreground">No test cases generated yet.</td>
                      </tr>
                    )}
                  </tbody>
                </table>
              </div>
            )}
          </CardContent>
        </Card>
      </div>
    </div>
  );
}
