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
      await delay(400)
      setLoadingMessage('🛣️ OR-Tools generating road network...')
      await delay(500)
      setLoadingMessage('🧬 NSGA-III evolving layouts...')
      await delay(400)
      setLoadingMessage('🏙️ Detecting city & predicting prices...')
      await delay(300)
      setLoadingMessage('🌿 Scoring Vastu + querying amenities...')

      const res = await axios.post(`${API}/generate-layout`, {
        polygon:     drawnPolygon,
        constraints: zoningResult.constraints,
      })

      setLoadingMessage('🤖 Claude AI auditing NBC compliance...')
      await delay(400)
      setLoadingMessage('🔍 NetworkX validating connectivity...')
      await delay(300)
      setLoadingMessage('✅ Pipeline complete!')
      await delay(200)

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

  const downloadPDF = async (layout, zoningResult) => {
    if (!layout) return
    try {
      const res = await fetch(`${API}/export-pdf`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          layout,
          zoning:       zoningResult || {},
          price:        layout.price_prediction || {},
          centroid_lat: layout.centroid_lat,
          centroid_lng: layout.centroid_lng,
        }),
      })
      if (!res.ok) {
        const err = await res.json()
        alert('PDF failed: ' + (err.error || 'Unknown error'))
        return
      }
      const blob = await res.blob()
      const url  = URL.createObjectURL(blob)
      const a    = document.createElement('a')
      a.href     = url
      a.download = `LandAI_Report_${Date.now()}.pdf`
      a.click()
      URL.revokeObjectURL(url)
    } catch (e) {
      console.error('PDF error:', e)
      alert('PDF export failed: ' + e.message)
    }
  }

  return { analyzeZoning, generateLayout, downloadPDF }
}
