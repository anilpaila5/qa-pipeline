import { Switch, Route, Router as WouterRouter } from "wouter";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { Toaster } from "@/components/ui/toaster";
import { TooltipProvider } from "@/components/ui/tooltip";
import { PipelineProvider } from "./context/pipeline-context";
import { Layout } from "./components/layout";
import Dashboard from "./pages/dashboard";
import Generate from "./pages/generate";
import Review from "./pages/review";
import Traceability from "./pages/traceability";
import NotFound from "./pages/not-found";

const queryClient = new QueryClient();

function Router() {
  return (
    <Layout>
      <Switch>
        <Route path="/" component={Dashboard} />
        <Route path="/generate" component={Generate} />
        <Route path="/review" component={Review} />
        <Route path="/traceability" component={Traceability} />
        <Route component={NotFound} />
      </Switch>
    </Layout>
  );
}

function App() {
  return (
    <QueryClientProvider client={queryClient}>
      <PipelineProvider>
        <TooltipProvider>
          <WouterRouter base={import.meta.env.BASE_URL.replace(/\/$/, "")}>
            <Router />
          </WouterRouter>
          <Toaster />
        </TooltipProvider>
      </PipelineProvider>
    </QueryClientProvider>
  );
}

export default App;
