import { BrowserRouter, Navigate, Route, Routes } from 'react-router-dom'
import Navbar from './components/layout/Navbar'
import PlayerPage from './pages/PlayerPage'
import RankingPage from './pages/RankingPage'
import TeamsPage from './pages/TeamsPage'
import ComparePage from './pages/ComparePage'
import MetodologiaPage from './pages/MetodologiaPage'
import MundialPage from './pages/MundialPage'
import MundialMatchPage from './pages/MundialMatchPage'
import LegalPage from './pages/LegalPage'
import Footer from './components/layout/Footer'

export default function App() {
  return (
    <BrowserRouter>
      <Navbar />
      <main className="main-content">
        <Routes>
          <Route path="/" element={<Navigate to="/ranking" replace />} />
          <Route path="/ranking" element={<RankingPage />} />
          <Route path="/player/:id" element={<PlayerPage />} />
          <Route path="/teams" element={<TeamsPage />} />
          <Route path="/compare" element={<ComparePage />} />
          <Route path="/metodologia" element={<MetodologiaPage />} />
          <Route path="/mundial" element={<MundialPage />} />
          <Route path="/mundial/partido/:fixtureId" element={<MundialMatchPage />} />
          <Route path="/legal" element={<LegalPage />} />
        </Routes>
      </main>
      <Footer />
    </BrowserRouter>
  )
}
