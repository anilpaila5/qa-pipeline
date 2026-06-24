import { useState } from "react";
import { useLocation } from "wouter";
import { useFetchStory, useGenerateTestCases } from "@workspace/api-client-react";
import { usePipeline } from "@/context/pipeline-context";
import { useToast } from "@/hooks/use-toast";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Card, CardContent, CardDescription, CardHeader, CardTitle, CardFooter } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { Loader2, ArrowRight, Wand2, Search } from "lucide-react";
import { Separator } from "@/components/ui/separator";

export default function Generate() {
  const [, setLocation] = useLocation();
  const { toast } = useToast();
  const { story, setStory, setTestCases } = usePipeline();
  const [jiraKey, setJiraKey] = useState("");

  const fetchStory = useFetchStory();
  const generateTestCases = useGenerateTestCases();

  const handleFetch = (e: React.FormEvent) => {
    e.preventDefault();
    if (!jiraKey) return;
    
    fetchStory.mutate({ data: { jiraKey } }, {
      onSuccess: (data) => {
        setStory(data);
        toast({ title: "Story fetched successfully", description: `Loaded ${data.key}` });
      },
      onError: (err: any) => {
        toast({ 
          variant: "destructive", 
          title: "Failed to fetch story", 
          description: err?.error || "Check your Jira Key and configuration." 
        });
      }
    });
  };

  const handleGenerate = () => {
    if (!story) return;

    generateTestCases.mutate({ data: { story } }, {
      onSuccess: (data) => {
        setTestCases(data.testCases);
        toast({ title: "Test Cases Generated", description: `Generated ${data.testCases.length} test cases.` });
        setLocation("/review");
      },
      onError: (err: any) => {
        toast({ 
          variant: "destructive", 
          title: "Generation failed", 
          description: err?.error || "Failed to generate test cases via AI." 
        });
      }
    });
  };

  return (
    <div className="p-8 max-w-4xl mx-auto w-full space-y-8">
      <div className="space-y-2">
        <h1 className="text-3xl font-bold tracking-tight">Generate Test Cases</h1>
        <p className="text-muted-foreground">
          Pull a story from Jira and use AI to draft a comprehensive test suite.
        </p>
      </div>

      <Card>
        <CardHeader>
          <CardTitle>Target Jira Issue</CardTitle>
          <CardDescription>Enter the issue key to fetch details.</CardDescription>
        </CardHeader>
        <CardContent>
          <form onSubmit={handleFetch} className="flex gap-4">
            <div className="flex-1 space-y-1">
              <Label htmlFor="jiraKey" className="sr-only">Jira Key</Label>
              <Input
                id="jiraKey"
                placeholder="e.g. QA-1831"
                value={jiraKey}
                onChange={(e) => setJiraKey(e.target.value)}
                autoComplete="off"
              />
            </div>
            <Button type="submit" disabled={fetchStory.isPending || !jiraKey}>
              {fetchStory.isPending ? <Loader2 className="mr-2 h-4 w-4 animate-spin" /> : <Search className="mr-2 h-4 w-4" />}
              Fetch Story
            </Button>
          </form>
        </CardContent>
      </Card>

      {story && (
        <Card className="animate-in slide-in-from-bottom-4 duration-500">
          <CardHeader>
            <div className="flex justify-between items-start">
              <div className="space-y-1">
                <CardTitle className="text-xl flex items-center gap-2">
                  {story.key}: {story.summary}
                  {story.status && <Badge variant="secondary">{story.status}</Badge>}
                  {story.priority && <Badge variant="outline">{story.priority}</Badge>}
                </CardTitle>
                <CardDescription>
                  {story.labels.length > 0 && <span className="mr-2">Labels: {story.labels.join(", ")}</span>}
                  {story.components.length > 0 && <span>Components: {story.components.join(", ")}</span>}
                </CardDescription>
              </div>
            </div>
          </CardHeader>
          <CardContent className="space-y-6">
            {story.description && (
              <div className="space-y-2">
                <h4 className="text-sm font-semibold text-foreground">Description</h4>
                <div className="text-sm text-muted-foreground whitespace-pre-wrap bg-muted/50 p-4 rounded-md">
                  {story.description}
                </div>
              </div>
            )}
            
            {story.acceptanceCriteria && (
              <div className="space-y-2">
                <h4 className="text-sm font-semibold text-foreground">Acceptance Criteria</h4>
                <div className="text-sm text-muted-foreground whitespace-pre-wrap border p-4 rounded-md">
                  {story.acceptanceCriteria}
                </div>
              </div>
            )}
          </CardContent>
          <Separator />
          <CardFooter className="flex justify-between p-6">
            <p className="text-sm text-muted-foreground">Ready to generate test cases?</p>
            <Button onClick={handleGenerate} disabled={generateTestCases.isPending} size="lg" className="w-full sm:w-auto">
              {generateTestCases.isPending ? (
                <Loader2 className="mr-2 h-5 w-5 animate-spin" />
              ) : (
                <Wand2 className="mr-2 h-5 w-5" />
              )}
              Generate with AI
              <ArrowRight className="ml-2 h-4 w-4" />
            </Button>
          </CardFooter>
        </Card>
      )}
    </div>
  );
}
