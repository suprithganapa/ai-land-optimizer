import { useState, useEffect } from 'react'
import useStore from './store/useStore'
import MapView from './views/MapView'
import ResultsView from './views/ResultsView'

export default function App() {
  const { layout } = useStore()
  const [page, setPage] = useState('map')

  useEffect(() => {
    if (layout) setPage('results')
  }, [layout])

  if (page === 'results' && layout) {
    return <ResultsView onBack={() => setPage('map')} />
  }

  return <MapView onNavigate={() => setPage('results')} />
}