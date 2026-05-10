import axios from 'axios'
import useStore from '../store/useStore'

const API = 'http://localhost:8000/api'
const delay = ms => new Promise(r => setTimeout(r, ms))

export function useLayout() {
  const {
    drawnPolygon,
    zoningResult,
    setZoningResult,
    setLayout,
    setIsLoading,
    setLoadingMessage,
  } = useStore()

  const analyzeZoning = async () => {
    if (!drawnPolygon) return
    setIsLoading(true)
    setLoadingMessage('🌍 Querying OpenStreetMap zoning data...')
    try {
      const res = await axios.post(`${API}/check-zoning`, drawnPolygon)
      setZoningResult(res.data)
      return res.data
    } catch (e) {
      console.error('Zoning error:', e)
      alert('Zoning check failed: ' + (e.response?.data?.detail || e.message))
      return null
    } finally {
      setIsLoading(false)
      setLoadingMessage('')
    }
  }

  const generateLayout = async () => {
    if (!drawnPolygon || !zoningResult || !zoningResult.is_legal) return
    setIsLoading(true)
    try {
      setLoadingMessage('🔵 Bayesian warm start...')
      await delay(600)
      setLoadingMessage('🛣️ OR-Tools generating road network...')
      await delay(700)
      setLoadingMessage('🧬 NSGA-III evolving 100 layouts...')

      const res = await axios.post(`${API}/generate-layout`, {
        polygon:     drawnPolygon,
        constraints: zoningResult.constraints,
      })

      setLoadingMessage('🔍 NetworkX validating connectivity...')
      await delay(500)
      setLoadingMessage('✅ Pipeline complete!')
      await delay(300)

      setLayout(res.data)
      return res.data
    } catch (e) {
      console.error('Layout error:', e)
      alert('Layout generation failed: ' + (e.response?.data?.detail || e.message))
      return null
    } finally {
      setIsLoading(false)
      setLoadingMessage('')
    }
  }

  return { analyzeZoning, generateLayout }
}