import { BrowserRouter, Routes, Route, Navigate } from 'react-router-dom';
import { JobProvider } from './contexts/JobContext';
import { LanguageProvider } from './contexts/LanguageContext';
import { Dashboard } from './pages/Dashboard';
import { CreateJob } from './pages/CreateJob';
import { JobDetail } from './pages/JobDetail';
import { Settings } from './pages/Settings';
import { Templates } from './pages/Templates';
import { TemplateEditor } from './pages/TemplateEditor';

function App() {
  return (
    <LanguageProvider>
      <JobProvider>
        <BrowserRouter>
          <Routes>
            <Route path="/" element={<Dashboard />} />
            <Route path="/jobs" element={<Dashboard />} />
            <Route path="/jobs/new" element={<CreateJob />} />
            <Route path="/jobs/:jobId" element={<JobDetail />} />
            <Route path="/settings" element={<Settings />} />
            <Route path="/templates" element={<Templates />} />
            <Route path="/templates/:templateId" element={<TemplateEditor />} />
            <Route path="*" element={<Navigate to="/" replace />} />
          </Routes>
        </BrowserRouter>
      </JobProvider>
    </LanguageProvider>
  );
}

export default App;
