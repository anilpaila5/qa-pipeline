import { useState } from "react";
import { useLocation } from "wouter";
import { usePublishTestCases } from "@workspace/api-client-react";
import { usePipeline } from "@/context/pipeline-context";
import { useToast } from "@/hooks/use-toast";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Card, CardContent, CardDescription, CardHeader, CardTitle, CardFooter } from "@/components/ui/card";
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from "@/components/ui/table";
import { Textarea } from "@/components/ui/textarea";
import { Loader2, Save, Send, AlertCircle, Edit2, CheckCircle2, XCircle, FolderTree } from "lucide-react";
import { Badge } from "@/components/ui/badge";
import { Progress } from "@/components/ui/progress";
import { Dialog, DialogContent, DialogHeader, DialogTitle, DialogFooter } from "@/components/ui/dialog";
import { ScrollArea } from "@/components/ui/scroll-area";

export default function Review() {
  const [, setLocation] = useLocation();
  const { toast } = useToast();
  const { story, testCases, setTestCases } = usePipeline();
  
  const [projectId, setProjectId] = useState<string>("");
  const [folderId, setFolderId] = useState<string>("");
  const [editingIndex, setEditingIndex] = useState<number | null>(null);
  const [editForm, setEditForm] = useState<any>(null);
  const [publishProgress, setPublishProgress] = useState<{ current: number; total: number; results: { name: string; success: boolean }[] } | null>(null);
  const [folders, setFolders] = useState<{ id: number; name: string }[]>([]);
  const [foldersOpen, setFoldersOpen] = useState(false);
  const [loadingFolders, setLoadingFolders] = useState(false);

  const publishTestCases = usePublishTestCases();

  if (!story || testCases.length === 0) {
    return (
      <div className="p-8 max-w-4xl mx-auto w-full text-center space-y-4">
        <AlertCircle className="w-12 h-12 text-muted-foreground mx-auto" />
        <h2 className="text-xl font-semibold">No test cases to review</h2>
        <p className="text-muted-foreground">Generate test cases first from a Jira story.</p>
        <Button onClick={() => setLocation("/generate")}>Go to Generate</Button>
      </div>
    );
  }

  const handleEditClick = (index: number) => {
    setEditingIndex(index);
    setEditForm({ ...testCases[index] });
  };

  const handleSaveEdit = () => {
    if (editingIndex !== null) {
      const newTestCases = [...testCases];
      newTestCases[editingIndex] = editForm;
      setTestCases(newTestCases);
      setEditingIndex(null);
    }
  };

  const handleBrowseFolders = async () => {
    if (!projectId) {
      toast({ variant: "destructive", title: "Validation Error", description: "Project ID is required first." });
      return;
    }
    setLoadingFolders(true);
    setFoldersOpen(true);
    try {
      const res = await fetch(`/api/pipeline/browserstack-folders?projectId=${Number(projectId)}`);
      const data = await res.json();
      setFolders(data.folders ?? []);
    } catch {
      toast({ variant: "destructive", title: "Failed to load folders", description: "Check the Project ID and your BrowserStack configuration." });
      setFolders([]);
    } finally {
      setLoadingFolders(false);
    }
  };

  const handleSelectFolder = (id: number) => {
    setFolderId(String(id));
    setFoldersOpen(false);
  };

  const handlePublish = async () => {
    if (!projectId || !folderId) {
      toast({ variant: "destructive", title: "Validation Error", description: "Project ID and Folder ID are required." });
      return;
    }

    const results: { name: string; success: boolean }[] = [];
    setPublishProgress({ current: 0, total: testCases.length, results: [] });

    for (let i = 0; i < testCases.length; i++) {
      const tc = testCases[i];
      try {
        const res = await fetch("/api/pipeline/publish-one", {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({
            jiraKey: story.key,
            projectId: Number(projectId),
            folderId: Number(folderId),
            testCase: tc,
          }),
        });
        const data = await res.json();
        results.push({ name: tc.name, success: data.success });
      } catch {
        results.push({ name: tc.name, success: false });
      }
      setPublishProgress({ current: i + 1, total: testCases.length, results: [...results] });
    }

    const created = results.filter((r) => r.success).length;
    const failed = results.filter((r) => !r.success).length;

    toast({
      title: "Publish Complete",
      description: `${created} published, ${failed} failed.`,
      variant: failed > 0 ? "destructive" : "default",
    });

    setPublishProgress(null);
    if (created > 0) {
      setLocation("/traceability");
    }
  };

  return (
    <div className="p-8 max-w-6xl mx-auto w-full space-y-8">
      <div className="flex justify-between items-end">
        <div className="space-y-2">
          <h1 className="text-3xl font-bold tracking-tight">Review & Publish</h1>
          <p className="text-muted-foreground">
            Review {testCases.length} generated test cases for <span className="font-semibold text-foreground">{story.key}</span> before publishing to BrowserStack.
          </p>
        </div>
      </div>

      <div className="grid gap-6 md:grid-cols-3 items-start">
        <Card className="md:col-span-2">
          <CardHeader>
            <CardTitle>Generated Test Cases</CardTitle>
            <CardDescription>Click edit on any test case to modify its contents.</CardDescription>
          </CardHeader>
          <CardContent className="p-0">
            <Table>
              <TableHeader>
                <TableRow>
                  <TableHead className="w-[40%]">Name</TableHead>
                  <TableHead>Priority</TableHead>
                  <TableHead>Expected Result</TableHead>
                  <TableHead className="w-[100px]"></TableHead>
                </TableRow>
              </TableHeader>
              <TableBody>
                {testCases.map((tc, idx) => (
                  <TableRow key={idx}>
                    <TableCell className="font-medium">
                      {tc.name}
                      <p className="text-xs text-muted-foreground line-clamp-1 mt-1">{tc.description}</p>
                    </TableCell>
                    <TableCell><Badge variant="outline">{tc.priority}</Badge></TableCell>
                    <TableCell className="text-xs text-muted-foreground line-clamp-2">{tc.expectedResult}</TableCell>
                    <TableCell>
                      <Button variant="ghost" size="sm" onClick={() => handleEditClick(idx)}>
                        <Edit2 className="h-4 w-4" />
                      </Button>
                    </TableCell>
                  </TableRow>
                ))}
              </TableBody>
            </Table>
          </CardContent>
        </Card>

        <Card className="sticky top-8">
          <CardHeader>
            <CardTitle>Publish Settings</CardTitle>
            <CardDescription>Target BrowserStack directory</CardDescription>
          </CardHeader>
          <CardContent className="space-y-4">
            <div className="space-y-2">
              <Label htmlFor="projectId">Project ID</Label>
              <Input
                id="projectId"
                type="number"
                placeholder="e.g. 12345"
                value={projectId}
                onChange={(e) => setProjectId(e.target.value)}
              />
            </div>
            <div className="space-y-2">
              <Label htmlFor="folderId">Folder ID</Label>
              <div className="flex gap-2">
                <Input
                  id="folderId"
                  type="number"
                  placeholder="e.g. 67890"
                  value={folderId}
                  onChange={(e) => setFolderId(e.target.value)}
                  className="flex-1"
                />
                <Button variant="outline" size="icon" onClick={handleBrowseFolders} type="button" title="Browse folders">
                  <FolderTree className="h-4 w-4" />
                </Button>
              </div>
            </div>
          </CardContent>
          <CardFooter className="flex-col gap-3">
            {publishProgress ? (
              <div className="w-full space-y-3">
                <Progress value={(publishProgress.current / publishProgress.total) * 100} className="h-2 w-full" />
                <div className="flex justify-between text-xs text-muted-foreground">
                  <span>{publishProgress.current} / {publishProgress.total} test cases</span>
                  <span>{publishProgress.results.filter((r) => r.success).length} succeeded</span>
                </div>
                <div className="flex flex-wrap gap-1 max-h-24 overflow-y-auto">
                  {publishProgress.results.map((r, i) => (
                    <span key={i} title={r.name}>
                      {r.success ? (
                        <CheckCircle2 className="h-4 w-4 text-green-500 inline" />
                      ) : (
                        <XCircle className="h-4 w-4 text-red-500 inline" />
                      )}
                    </span>
                  ))}
                </div>
              </div>
            ) : (
              <Button
                className="w-full"
                size="lg"
                onClick={handlePublish}
                disabled={publishTestCases.isPending || !projectId || !folderId}
              >
                {publishTestCases.isPending ? (
                  <Loader2 className="mr-2 h-5 w-5 animate-spin" />
                ) : (
                  <Send className="mr-2 h-5 w-5" />
                )}
                Publish to BrowserStack
              </Button>
            )}
          </CardFooter>
        </Card>
      </div>

      <Dialog open={editingIndex !== null} onOpenChange={(open) => !open && setEditingIndex(null)}>
        <DialogContent className="max-w-2xl max-h-[80vh] overflow-y-auto">
          <DialogHeader>
            <DialogTitle>Edit Test Case</DialogTitle>
          </DialogHeader>
          {editForm && (
            <div className="space-y-4 py-4">
              <div className="space-y-2">
                <Label>Name</Label>
                <Input value={editForm.name} onChange={e => setEditForm({...editForm, name: e.target.value})} />
              </div>
              <div className="space-y-2">
                <Label>Description</Label>
                <Textarea value={editForm.description} onChange={e => setEditForm({...editForm, description: e.target.value})} />
              </div>
              <div className="space-y-2">
                <Label>Steps</Label>
                <Textarea value={editForm.steps} onChange={e => setEditForm({...editForm, steps: e.target.value})} rows={5} />
              </div>
              <div className="space-y-2">
                <Label>Expected Result</Label>
                <Textarea value={editForm.expectedResult} onChange={e => setEditForm({...editForm, expectedResult: e.target.value})} />
              </div>
            </div>
          )}
          <DialogFooter>
            <Button variant="outline" onClick={() => setEditingIndex(null)}>Cancel</Button>
            <Button onClick={handleSaveEdit}>Save Changes</Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>
      <Dialog open={foldersOpen} onOpenChange={(open) => !open && setFoldersOpen(false)}>
        <DialogContent>
          <DialogHeader>
            <DialogTitle>BrowserStack Folders</DialogTitle>
          </DialogHeader>
          {loadingFolders ? (
            <div className="flex items-center justify-center py-8">
              <Loader2 className="h-6 w-6 animate-spin" />
            </div>
          ) : folders.length === 0 ? (
            <p className="text-muted-foreground py-4 text-center">No folders found for this project.</p>
          ) : (
            <ScrollArea className="max-h-64">
              <div className="space-y-1">
                {folders.map((f) => (
                  <Button
                    key={f.id}
                    variant="ghost"
                    className="w-full justify-start text-left"
                    onClick={() => handleSelectFolder(f.id)}
                  >
                    <FolderTree className="mr-2 h-4 w-4 shrink-0" />
                    <span className="truncate">{f.name}</span>
                    <span className="ml-auto text-xs text-muted-foreground">ID: {f.id}</span>
                  </Button>
                ))}
              </div>
            </ScrollArea>
          )}
        </DialogContent>
      </Dialog>
    </div>
  );
}
