import { useState } from "react";
import { useGetTraceability, useUpdateAutomation, getGetTraceabilityQueryKey } from "@workspace/api-client-react";
import { useQueryClient } from "@tanstack/react-query";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from "@/components/ui/table";
import { Input } from "@/components/ui/input";
import { Button } from "@/components/ui/button";
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select";
import { Loader2, Edit2, Check, X, Download, BarChart3, PieChart as PieChartIcon } from "lucide-react";
import { Badge } from "@/components/ui/badge";
import { BarChart, Bar, XAxis, YAxis, Tooltip, ResponsiveContainer, PieChart, Pie, Cell, Legend } from "recharts";

export default function Traceability() {
  const queryClient = useQueryClient();
  const { data, isLoading } = useGetTraceability();
  const updateAutomation = useUpdateAutomation();

  const [editingId, setEditingId] = useState<number | null>(null);
  const [editMethod, setEditMethod] = useState<string>("");
  const [editFile, setEditFile] = useState<string>("");

  const startEditing = (entry: any) => {
    setEditingId(entry.id);
    setEditMethod(entry.automationMethod || "None");
    setEditFile(entry.automationFile || "");
  };

  const cancelEditing = () => {
    setEditingId(null);
    setEditMethod("");
    setEditFile("");
  };

  const downloadCsv = () => {
    if (!data?.entries.length) return;
    const headers = ["Jira Key", "Test Case Name", "BrowserStack ID", "Method", "Automation File", "Created At", "Updated At"];
    const rows = data.entries.map((e) => [
      e.jiraKey,
      `"${e.tcName.replace(/"/g, '""')}"`,
      e.bsTcId,
      e.automationMethod || "Manual",
      e.automationFile || "",
      e.createdAt,
      e.updatedAt,
    ]);
    const csv = [headers.join(","), ...rows.map((r) => r.join(","))].join("\n");
    const blob = new Blob([csv], { type: "text/csv;charset=utf-8;" });
    const url = URL.createObjectURL(blob);
    const a = document.createElement("a");
    a.href = url;
    a.download = `traceability-${new Date().toISOString().slice(0, 10)}.csv`;
    a.click();
    URL.revokeObjectURL(url);
  };

  const saveEditing = async (id: number) => {
    await updateAutomation.mutateAsync({
      entryId: id,
      data: {
        automationMethod: editMethod === "None" ? null : editMethod,
        automationFile: editFile || null,
      }
    });
    
    // Invalidate to refresh the table and stats
    queryClient.invalidateQueries({ queryKey: getGetTraceabilityQueryKey() });
    cancelEditing();
  };

  if (isLoading) {
    return (
      <div className="p-8 flex items-center justify-center min-h-[50vh]">
        <Loader2 className="w-8 h-8 animate-spin text-primary" />
      </div>
    );
  }

  return (
    <div className="p-8 max-w-7xl mx-auto w-full space-y-8">
      <div className="space-y-2">
        <h1 className="text-3xl font-bold tracking-tight">Traceability Matrix</h1>
        <p className="text-muted-foreground">
          Track coverage from Jira requirements to automated test files.
        </p>
      </div>

      <div className="grid gap-6 md:grid-cols-4">
        <Card>
          <CardHeader className="pb-2">
            <CardTitle className="text-sm font-medium">Total Test Cases</CardTitle>
          </CardHeader>
          <CardContent>
            <p className="text-3xl font-bold">{data?.stats.totalTestCases ?? 0}</p>
          </CardContent>
        </Card>
        <Card>
          <CardHeader className="pb-2">
            <CardTitle className="text-sm font-medium text-green-600">Automated</CardTitle>
          </CardHeader>
          <CardContent>
            <p className="text-3xl font-bold text-green-600">{data?.stats.automated ?? 0}</p>
          </CardContent>
        </Card>
        <Card>
          <CardHeader className="pb-2">
            <CardTitle className="text-sm font-medium text-yellow-600">Manual</CardTitle>
          </CardHeader>
          <CardContent>
            <p className="text-3xl font-bold text-yellow-600">{data?.stats.notAutomated ?? 0}</p>
          </CardContent>
        </Card>
        <Card>
          <CardHeader className="pb-2">
            <CardTitle className="text-sm font-medium">Coverage</CardTitle>
          </CardHeader>
          <CardContent>
            <p className="text-3xl font-bold">{data?.stats.automationCoveragePct ?? 0}%</p>
          </CardContent>
        </Card>
      </div>

      <div className="grid gap-6 md:grid-cols-2">
        <Card>
          <CardHeader>
            <div className="flex items-center gap-2">
              <BarChart3 className="h-5 w-5 text-muted-foreground" />
              <CardTitle className="text-base">Automation Status</CardTitle>
            </div>
          </CardHeader>
          <CardContent>
            {data?.stats ? (
              <div className="h-64">
                <ResponsiveContainer width="100%" height="100%">
                  <BarChart data={[
                    { name: "Automated", count: data.stats.automated, fill: "#16a34a" },
                    { name: "Manual", count: data.stats.notAutomated, fill: "#ca8a04" },
                  ]}>
                    <XAxis dataKey="name" />
                    <YAxis allowDecimals={false} />
                    <Tooltip />
                    <Bar dataKey="count" radius={[4, 4, 0, 0]} />
                  </BarChart>
                </ResponsiveContainer>
              </div>
            ) : (
              <p className="text-muted-foreground text-sm py-8 text-center">No data</p>
            )}
          </CardContent>
        </Card>
        <Card>
          <CardHeader>
            <div className="flex items-center gap-2">
              <PieChartIcon className="h-5 w-5 text-muted-foreground" />
              <CardTitle className="text-base">Coverage Breakdown</CardTitle>
            </div>
          </CardHeader>
          <CardContent>
            {data?.stats && data.stats.totalTestCases > 0 ? (
              <div className="h-64">
                <ResponsiveContainer width="100%" height="100%">
                  <PieChart>
                    <Pie
                      data={[
                        { name: "Automated", value: data.stats.automated },
                        { name: "Manual", value: data.stats.notAutomated },
                      ]}
                      cx="50%"
                      cy="50%"
                      innerRadius={60}
                      outerRadius={90}
                      paddingAngle={4}
                      dataKey="value"
                    >
                      <Cell fill="#16a34a" />
                      <Cell fill="#ca8a04" />
                    </Pie>
                    <Tooltip />
                    <Legend />
                  </PieChart>
                </ResponsiveContainer>
              </div>
            ) : (
              <p className="text-muted-foreground text-sm py-8 text-center">No data</p>
            )}
          </CardContent>
        </Card>
      </div>

      <Card>
        <CardHeader className="flex flex-row items-start justify-between">
          <div>
            <CardTitle>Test Coverage Matrix</CardTitle>
            <CardDescription>
              Showing {data?.entries.length} tracked test cases across {data?.stats.jiraStoriesCovered} stories.
            </CardDescription>
          </div>
          <Button variant="outline" size="sm" onClick={downloadCsv} disabled={!data?.entries.length}>
            <Download className="mr-2 h-4 w-4" />
            CSV
          </Button>
        </CardHeader>
        <CardContent className="p-0">
          <div className="rounded-md border border-t-0 border-x-0 border-b">
            <Table>
              <TableHeader>
                <TableRow>
                  <TableHead className="w-[120px]">Jira Key</TableHead>
                  <TableHead>Test Case Name</TableHead>
                  <TableHead className="w-[150px]">BS ID</TableHead>
                  <TableHead className="w-[200px]">Method</TableHead>
                  <TableHead>Automation File</TableHead>
                  <TableHead className="w-[100px] text-right">Actions</TableHead>
                </TableRow>
              </TableHeader>
              <TableBody>
                {data?.entries.map((entry) => (
                  <TableRow key={entry.id}>
                    <TableCell className="font-medium">{entry.jiraKey}</TableCell>
                    <TableCell className="max-w-[300px] truncate" title={entry.tcName}>
                      {entry.tcName}
                    </TableCell>
                    <TableCell>
                      <Badge variant="secondary" className="font-mono">{entry.bsTcId}</Badge>
                    </TableCell>
                    
                    {editingId === entry.id ? (
                      <>
                        <TableCell>
                          <Select value={editMethod} onValueChange={setEditMethod}>
                            <SelectTrigger className="h-8 w-full">
                              <SelectValue />
                            </SelectTrigger>
                            <SelectContent>
                              <SelectItem value="None">None</SelectItem>
                              <SelectItem value="Playwright">Playwright</SelectItem>
                              <SelectItem value="Cypress">Cypress</SelectItem>
                              <SelectItem value="Selenium">Selenium</SelectItem>
                              <SelectItem value="Appium">Appium</SelectItem>
                            </SelectContent>
                          </Select>
                        </TableCell>
                        <TableCell>
                          <Input 
                            value={editFile} 
                            onChange={(e) => setEditFile(e.target.value)} 
                            className="h-8"
                            placeholder="e.g. tests/login.spec.ts"
                          />
                        </TableCell>
                        <TableCell className="text-right">
                          <div className="flex justify-end gap-1">
                            <Button size="icon" variant="ghost" className="h-8 w-8 text-green-600" onClick={() => saveEditing(entry.id)}>
                              <Check className="h-4 w-4" />
                            </Button>
                            <Button size="icon" variant="ghost" className="h-8 w-8 text-red-600" onClick={cancelEditing}>
                              <X className="h-4 w-4" />
                            </Button>
                          </div>
                        </TableCell>
                      </>
                    ) : (
                      <>
                        <TableCell>
                          {entry.automationMethod ? (
                            <Badge variant="outline" className="bg-primary/5 text-primary">
                              {entry.automationMethod}
                            </Badge>
                          ) : (
                            <span className="text-muted-foreground text-sm">Manual</span>
                          )}
                        </TableCell>
                        <TableCell>
                          {entry.automationFile ? (
                            <span className="font-mono text-xs truncate max-w-[200px] inline-block" title={entry.automationFile}>
                              {entry.automationFile}
                            </span>
                          ) : (
                            <span className="text-muted-foreground text-sm">-</span>
                          )}
                        </TableCell>
                        <TableCell className="text-right">
                          <Button size="icon" variant="ghost" className="h-8 w-8" onClick={() => startEditing(entry)}>
                            <Edit2 className="h-4 w-4" />
                          </Button>
                        </TableCell>
                      </>
                    )}
                  </TableRow>
                ))}
                {(!data?.entries || data.entries.length === 0) && (
                  <TableRow>
                    <TableCell colSpan={6} className="h-24 text-center text-muted-foreground">
                      No traceability records found.
                    </TableCell>
                  </TableRow>
                )}
              </TableBody>
            </Table>
          </div>
        </CardContent>
      </Card>
    </div>
  );
}
