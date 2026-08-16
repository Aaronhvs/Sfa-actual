import { lazy, Suspense } from 'react'
import { BrowserRouter, Navigate, Route, Routes } from 'react-router-dom'
import Navbar from './components/layout/Navbar'
import Footer from './components/layout/Footer'
import SeoController from './components/shared/SeoController'

const RankingPage = lazy(() => import('./pages/RankingPage'))
const PlayerPage = lazy(() => import('./pages/PlayerPage'))
const TeamsPage = lazy(() => import('./pages/TeamsPage'))
const ComparePage = lazy(() => import('./pages/ComparePage'))
const MetodologiaPage = lazy(() => import('./pages/MetodologiaPage'))
const TournamentsPage = lazy(() => import('./pages/TournamentsPage'))
const TournamentDetailPage = lazy(() => import('./pages/TournamentDetailPage'))
const TournamentMatchPage = lazy(() => import('./pages/TournamentMatchPage'))
const MundialMatchPage = lazy(() => import('./pages/MundialMatchPage'))
const MundialTeamPage = lazy(() => import('./pages/MundialTeamPage'))
const LegalPage = lazy(() => import('./pages/LegalPage'))

function RouteFallback() {
  return (
    <div className="route-loading" role="status" aria-live="polite">
      <div className="skeleton route-loading__bar" />
      <span>Cargando contenido</span>
    </div>
  )
}

export default function App() {
  return (
    <BrowserRouter>
      <SeoController />
      <Navbar />
      <main className="main-content">
        <Suspense fallback={<RouteFallback />}>
          <Routes>
            <Route path="/" element={<Navigate to="/ranking" replace />} />
            <Route path="/ranking" element={<RankingPage />} />
            <Route path="/player/:id" element={<PlayerPage />} />
            <Route path="/teams" element={<TeamsPage />} />
            <Route path="/compare" element={<ComparePage />} />
            <Route path="/metodologia" element={<MetodologiaPage />} />
            <Route path="/torneos" element={<TournamentsPage />} />
            <Route path="/torneos/:competitionId" element={<TournamentDetailPage />} />
            <Route path="/torneos/partido/:fixtureId" element={<TournamentMatchPage />} />
            <Route path="/mundial" element={<Navigate to="/torneos" replace />} />
            <Route path="/mundial/partido/:fixtureId" element={<MundialMatchPage />} />
            <Route path="/mundial/seleccion/:teamId" element={<MundialTeamPage />} />
            <Route path="/legal" element={<LegalPage />} />
          </Routes>
        </Suspense>
      </main>
      <Footer />
    </BrowserRouter>
  )
}
