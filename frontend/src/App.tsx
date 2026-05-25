import { Navigate, Route, Routes } from 'react-router-dom';
import ConfigPage from './pages/ConfigPage';
import BranchesPage from './pages/BranchesPage';
import SimulatePage from './pages/SimulatePage';
import ReportPage from './pages/ReportPage';

export default function App() {
  return (
    <Routes>
      <Route path="/" element={<Navigate to="/config" replace />} />
      <Route path="/config" element={<ConfigPage />} />
      <Route path="/branches" element={<BranchesPage />} />
      <Route path="/simulate/:branchId" element={<SimulatePage />} />
      <Route path="/report/:branchId" element={<ReportPage />} />
      <Route path="*" element={<Navigate to="/config" replace />} />
    </Routes>
  );
}
