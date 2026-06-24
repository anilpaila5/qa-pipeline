import { createContext, useContext, useState, ReactNode } from "react";
import type { JiraStory, TestCase } from "@workspace/api-client-react";

interface PipelineContextType {
  story: JiraStory | null;
  setStory: (story: JiraStory | null) => void;
  testCases: TestCase[];
  setTestCases: (testCases: TestCase[]) => void;
  clearPipeline: () => void;
}

const PipelineContext = createContext<PipelineContextType | undefined>(undefined);

export function PipelineProvider({ children }: { children: ReactNode }) {
  const [story, setStory] = useState<JiraStory | null>(null);
  const [testCases, setTestCases] = useState<TestCase[]>([]);

  const clearPipeline = () => {
    setStory(null);
    setTestCases([]);
  };

  return (
    <PipelineContext.Provider
      value={{
        story,
        setStory,
        testCases,
        setTestCases,
        clearPipeline,
      }}
    >
      {children}
    </PipelineContext.Provider>
  );
}

export function usePipeline() {
  const context = useContext(PipelineContext);
  if (context === undefined) {
    throw new Error("usePipeline must be used within a PipelineProvider");
  }
  return context;
}
