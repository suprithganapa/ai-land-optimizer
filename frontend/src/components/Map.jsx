import { useEffect, useRef, useState } from 'react'
import maplibregl from 'maplibre-gl'
import 'maplibre-gl/dist/maplibre-gl.css'
import useStore from '../store/useStore'
import { useLayout } from '../hooks/useLayout'

const MAPTILER_KEY = 'gbb10k4jq9g81OSN4q0z'

export default function Map() {
  const mapContainer = useRef(null)
  const mapRef       = useRef(null)
  const [area, setArea]                   = useState(null)
  const [coordCount, setCoordCount]       = useState(0)
  const [searchInput, setSearchInput]     = useState('')
  const [searchResults, setSearchResults] = useState([])
  const [isDrawing, setIsDrawing]         = useState(false)
  const [points, setPoints]               = useState([])
  const [isClosed, setIsClosed]           = useState(false)

  const { drawnPolygon, setDrawnPolygon, isLoading, zoningResult } = useStore()
  const { analyzeZoning, generateLayout } = useLayout()

  const handleAnalyze = async () => {
    if (zoningResult && !zoningResult.is_legal) return
    if (!zoningResult) await analyzeZoning()
    else await generateLayout()
  }

  useEffect(() => {
    if (mapRef.current || !mapContainer.current) return
    const map = new maplibregl.Map({
      container: mapContainer.current,
      style: `https://api.maptiler.com/maps/satellite/style.json?key=${MAPTILER_KEY}`,
      center: [77.5946, 12.9716],
      zoom: 15,
      attributionControl: false,
    })
    mapRef.current = map
    map.addControl(new maplibregl.NavigationControl(), 'top-right')
    map.addControl(new maplibregl.AttributionControl({ compact: true }), 'bottom-right')

    map.on('load', () => {
      ;['drawn-polygon', 'drawn-points', 'drawn-line'].forEach(id => {
        map.addSource(id, { type: 'geojson', data: { type: 'FeatureCollection', features: [] } })
      })
      map.addLayer({ id: 'polygon-fill', type: 'fill', source: 'drawn-polygon',
        paint: { 'fill-color': '#4f9cf9', 'fill-opacity': 0.15 } })
      map.addLayer({ id: 'polygon-outline', type: 'line', source: 'drawn-polygon',
        paint: { 'line-color': '#4f9cf9', 'line-width': 2, 'line-dasharray': [4, 2] } })
      map.addLayer({ id: 'drawing-line', type: 'line', source: 'drawn-line',
        paint: { 'line-color': '#4f9cf9', 'line-width': 1.5, 'line-dasharray': [3, 2] } })
      map.addLayer({ id: 'vertex-halo', type: 'circle', source: 'drawn-points',
        paint: { 'circle-radius': 10, 'circle-color': '#4f9cf9', 'circle-opacity': 0.15 } })
      map.addLayer({ id: 'vertex-dots', type: 'circle', source: 'drawn-points',
        paint: { 'circle-radius': 5, 'circle-color': '#4f9cf9', 'circle-stroke-width': 2, 'circle-stroke-color': '#fff' } })
    })
    return () => { map.remove(); mapRef.current = null }
  }, [])

  useEffect(() => {
    const map = mapRef.current
    if (!map?.isStyleLoaded() || !map.getSource('drawn-points')) return

    map.getSource('drawn-points').setData({
      type: 'FeatureCollection',
      features: points.map(p => ({ type: 'Feature', geometry: { type: 'Point', coordinates: p } })),
    })

    if (points.length >= 2) {
      map.getSource('drawn-line').setData({
        type: 'FeatureCollection',
        features: [{ type: 'Feature', geometry: { type: 'LineString', coordinates: points } }],
      })
    } else {
      map.getSource('drawn-line').setData({ type: 'FeatureCollection', features: [] })
    }

    if (isClosed && points.length >= 3) {
      const closed = [...points, points[0]]
      map.getSource('drawn-polygon').setData({
        type: 'FeatureCollection',
        features: [{ type: 'Feature', geometry: { type: 'Polygon', coordinates: [closed] } }],
      })
      map.getSource('drawn-line').setData({ type: 'FeatureCollection', features: [] })
      const lats = points.map(p => p[1])
      const lngs = points.map(p => p[0])
      const a = Math.round(
        (Math.max(...lats) - Math.min(...lats)) * 111000 *
        (Math.max(...lngs) - Math.min(...lngs)) * 111000 *
        Math.cos(lats[0] * Math.PI / 180)
      )
      setArea(a)
      setCoordCount(points.length)
      setDrawnPolygon({ type: 'Polygon', coordinates: [closed] })
    }
  }, [points, isClosed])

  useEffect(() => {
    const map = mapRef.current
    if (!map) return
    const onClick = e => {
      if (!isDrawing) return
      setPoints(prev => [...prev, [e.lngLat.lng, e.lngLat.lat]])
    }
    const onDbl = e => {
      if (!isDrawing) return
      e.preventDefault()
      if (points.length >= 3) { setIsClosed(true); setIsDrawing(false); map.getCanvas().style.cursor = '' }
    }
    map.on('click', onClick)
    map.on('dblclick', onDbl)
    return () => { map.off('click', onClick); map.off('dblclick', onDbl) }
  }, [isDrawing, points])

  const startDrawing = () => {
    handleClear()
    setIsDrawing(true)
    if (mapRef.current) mapRef.current.getCanvas().style.cursor = 'crosshair'
  }

  const handleClear = () => {
    setPoints([]); setIsClosed(false); setIsDrawing(false)
    setArea(null); setCoordCount(0); setDrawnPolygon(null)
    const map = mapRef.current
    if (map?.isStyleLoaded()) {
      ;['drawn-polygon', 'drawn-points', 'drawn-line'].forEach(s => {
        map.getSource(s)?.setData({ type: 'FeatureCollection', features: [] })
      })
      map.getCanvas().style.cursor = ''
    }
  }

  const handleSearch = async q => {
    setSearchInput(q)
    if (q.length < 3) { setSearchResults([]); return }
    try {
      const r = await fetch(`https://api.maptiler.com/geocoding/${encodeURIComponent(q)}.json?key=${MAPTILER_KEY}&limit=5`)
      const d = await r.json()
      setSearchResults(d.features || [])
    } catch {}
  }

  const flyTo = f => {
    mapRef.current?.flyTo({ center: f.center, zoom: 17, duration: 1500 })
    setSearchInput(f.place_name)
    setSearchResults([])
  }

  const blocked = zoningResult && !zoningResult.is_legal
  const btnLabel = blocked ? '🚫 Plot Not Available'
    : !zoningResult ? '🔍 Analyze Land' : '🧬 Generate Layout →'
  const btnColor  = blocked ? '#f87171' : zoningResult ? '#3ecf8e' : '#4f9cf9'
  const btnBorder = blocked ? '#f8717155' : zoningResult ? '#3ecf8e55' : '#4f9cf955'
  const btnBg     = blocked ? '#1e0d0d'  : zoningResult ? '#0a1e12'  : '#0f1a2e'

  return (
    <div style={{ position: 'relative', width: '100%', height: '100%' }}>
      <div ref={mapContainer} style={{ position: 'absolute', inset: 0 }} />

      {/* Search */}
      <div style={{ position: 'absolute', top: 12, left: '50%', transform: 'translateX(-50%)', width: 360, zIndex: 20 }}>
        <div style={{ position: 'relative' }}>
          <span style={{ position: 'absolute', left: 12, top: '50%', transform: 'translateY(-50%)', fontSize: 13, pointerEvents: 'none', color: '#4f9cf9' }}>🔍</span>
          <input
            value={searchInput}
            onChange={e => handleSearch(e.target.value)}
            placeholder="Search location or enter lat, lng..."
            style={{
              width: '100%', boxSizing: 'border-box',
              background: 'rgba(9,12,20,0.95)',
              border: '1px solid #1e2235', borderRadius: 10,
              padding: '10px 12px 10px 34px',
              color: '#e2e2e2', fontSize: 12, outline: 'none',
              backdropFilter: 'blur(12px)',
              boxShadow: '0 4px 24px rgba(0,0,0,0.5)',
            }}
            onKeyDown={e => {
              if (e.key !== 'Enter') return
              const [a, b] = searchInput.split(',')
              const lat = parseFloat(a), lng = parseFloat(b)
              if (!isNaN(lat) && !isNaN(lng)) {
                mapRef.current?.flyTo({ center: [lng, lat], zoom: 17, duration: 1500 })
                setSearchResults([])
              }
            }}
          />
        </div>
        {searchResults.length > 0 && (
          <div style={{
            background: 'rgba(9,12,20,0.98)', border: '1px solid #1e2235',
            borderRadius: 10, marginTop: 4, overflow: 'hidden',
            boxShadow: '0 8px 32px rgba(0,0,0,0.6)',
          }}>
            {searchResults.map((r, i) => (
              <div key={i} onClick={() => flyTo(r)}
                style={{
                  padding: '9px 14px', fontSize: 11, color: '#888', cursor: 'pointer',
                  borderBottom: i < searchResults.length - 1 ? '0.5px solid #1a1d2e' : 'none',
                  display: 'flex', alignItems: 'center', gap: 8,
                }}
                onMouseEnter={e => e.currentTarget.style.background = '#0f1a2e'}
                onMouseLeave={e => e.currentTarget.style.background = 'transparent'}
              >
                <span style={{ color: '#4f9cf9' }}>📍</span> {r.place_name}
              </div>
            ))}
          </div>
        )}
      </div>

      {/* Draw button */}
      {!isClosed && !isDrawing && (
        <button onClick={startDrawing} style={{
          position: 'absolute', top: 12, left: 12, zIndex: 20,
          background: 'rgba(9,12,20,0.92)', border: '1px solid #4f9cf955',
          color: '#4f9cf9', borderRadius: 9, padding: '8px 16px',
          fontSize: 12, fontWeight: 600, cursor: 'pointer',
          display: 'flex', alignItems: 'center', gap: 6,
          backdropFilter: 'blur(12px)',
          boxShadow: '0 4px 16px rgba(79,156,249,0.15)',
        }}>
          ✏️ Draw Boundary
        </button>
      )}

      {/* Drawing mode */}
      {isDrawing && (
        <div style={{
          position: 'absolute', top: 12, left: 12, zIndex: 20,
          background: 'rgba(9,12,20,0.95)', border: '1px solid #4f9cf955',
          borderRadius: 10, padding: '10px 14px', minWidth: 160,
          backdropFilter: 'blur(12px)',
        }}>
          <div style={{ fontSize: 11, color: '#4f9cf9', fontWeight: 700, marginBottom: 4 }}>
            ✏️ Drawing Mode
          </div>
          <div style={{ fontSize: 10, color: '#3a3f55', marginBottom: 8 }}>
            {points.length} point{points.length !== 1 ? 's' : ''}
            {points.length >= 3 && ' · ready to close'}
          </div>
          {points.length >= 3 && (
            <button onClick={() => {
              setIsClosed(true); setIsDrawing(false)
              if (mapRef.current) mapRef.current.getCanvas().style.cursor = ''
            }} style={{
              width: '100%', background: '#4f9cf9', color: '#fff',
              border: 'none', borderRadius: 7, padding: '6px 10px',
              fontSize: 11, fontWeight: 700, cursor: 'pointer', marginBottom: 6,
            }}>
              ✅ Close & Finish
            </button>
          )}
          <button onClick={handleClear} style={{
            width: '100%', background: 'transparent',
            color: '#f87171', border: '0.5px solid #f8717133',
            borderRadius: 7, padding: '5px 10px', fontSize: 10, cursor: 'pointer',
          }}>
            ✕ Cancel
          </button>
        </div>
      )}

      {/* Instructions */}
      {!drawnPolygon && !isDrawing && (
        <div style={{
          position: 'absolute', top: '50%', left: '44%',
          transform: 'translate(-50%, -50%)',
          background: 'rgba(9,12,20,0.88)', border: '1px solid #1e2235',
          borderRadius: 14, padding: '22px 30px',
          textAlign: 'center', pointerEvents: 'none', zIndex: 5,
          backdropFilter: 'blur(16px)',
          boxShadow: '0 8px 40px rgba(0,0,0,0.5)',
        }}>
          <div style={{ fontSize: 32, marginBottom: 10 }}>🗺️</div>
          <div style={{ fontSize: 14, color: '#e2e2e2', fontWeight: 700, marginBottom: 6 }}>
            Select Your Land Parcel
          </div>
          <div style={{ fontSize: 11, color: '#3a3f55', lineHeight: 1.7 }}>
            Search for a location above<br />
            Click <span style={{ color: '#4f9cf9', fontWeight: 700 }}>Draw Boundary</span> to mark corners<br />
            <span style={{ fontSize: 10 }}>Then click Analyze Land to begin</span>
          </div>
        </div>
      )}

      {/* Live stats */}
      {coordCount > 0 && (
        <div style={{
          position: 'absolute', bottom: 70, left: 12, zIndex: 10,
          background: 'rgba(9,12,20,0.92)', border: '0.5px solid #1e2235',
          borderRadius: 10, padding: '10px 14px',
          backdropFilter: 'blur(12px)',
        }}>
          <div style={{ fontSize: 9, color: '#3a3f55', marginBottom: 5, fontWeight: 600, letterSpacing: '0.8px' }}>
            SELECTION
          </div>
          <div style={{ fontSize: 12, color: '#e2e2e2' }}>
            📐 <span style={{ color: '#4f9cf9', fontWeight: 700 }}>{coordCount}</span> boundary points
          </div>
          {area && (
            <div style={{ fontSize: 12, color: '#e2e2e2', marginTop: 3 }}>
              📏 <span style={{ color: '#3ecf8e', fontWeight: 700 }}>{area.toLocaleString()}</span> m² approx.
            </div>
          )}
        </div>
      )}

      {/* Action buttons */}
      {drawnPolygon && !isLoading && (
        <div style={{
          position: 'absolute', bottom: 16, left: '44%',
          transform: 'translateX(-50%)',
          display: 'flex', gap: 8, zIndex: 10,
        }}>
          <button onClick={handleClear} style={{
            background: 'rgba(9,12,20,0.92)', border: '1px solid #1e2235',
            color: '#555', borderRadius: 10, padding: '10px 18px',
            fontSize: 12, cursor: 'pointer', backdropFilter: 'blur(12px)',
            display: 'flex', alignItems: 'center', gap: 6,
          }}>
            🗑️ Clear
          </button>
          <button onClick={handleAnalyze} disabled={blocked} style={{
            background: btnBg, border: `1px solid ${btnBorder}`,
            color: btnColor, borderRadius: 10,
            padding: '10px 24px', fontSize: 13, fontWeight: 700,
            cursor: blocked ? 'not-allowed' : 'pointer',
            opacity: blocked ? 0.7 : 1,
            backdropFilter: 'blur(12px)',
            boxShadow: `0 4px 20px ${btnColor}22`,
            transition: 'all 0.2s',
          }}>
            {btnLabel}
          </button>
        </div>
      )}

      {/* Loading */}
      {isLoading && (
        <div style={{
          position: 'absolute', bottom: 16, left: '44%',
          transform: 'translateX(-50%)',
          background: 'rgba(9,12,20,0.96)', border: '1px solid #7c5cf633',
          borderRadius: 10, padding: '10px 22px',
          display: 'flex', alignItems: 'center', gap: 10,
          zIndex: 20, backdropFilter: 'blur(12px)',
        }}>
          <style>{`@keyframes spin{to{transform:rotate(360deg)}}`}</style>
          <div style={{
            width: 14, height: 14,
            border: '2px solid #1e1e3e', borderTop: '2px solid #7c5cf6',
            borderRadius: '50%', animation: 'spin 0.8s linear infinite',
          }} />
          <span style={{ fontSize: 12, color: '#a78bfa', fontWeight: 600 }}>
            {useStore.getState().loadingMessage || 'Running AI pipeline...'}
          </span>
        </div>
      )}

      {/* Zoning badge */}
      {zoningResult && !isLoading && (
        <div style={{
          position: 'absolute', top: 12, right: 50, zIndex: 10,
          background: zoningResult.is_legal ? 'rgba(9,20,14,0.96)' : 'rgba(20,9,9,0.96)',
          border: `1px solid ${zoningResult.is_legal ? '#3ecf8e44' : '#f8717144'}`,
          borderRadius: 10, padding: '8px 14px', maxWidth: 240,
          backdropFilter: 'blur(12px)',
        }}>
          <div style={{ display: 'flex', alignItems: 'center', gap: 6, marginBottom: 3 }}>
            <div style={{
              width: 7, height: 7, borderRadius: '50%',
              background: zoningResult.is_legal ? '#3ecf8e' : '#f87171',
              boxShadow: `0 0 6px ${zoningResult.is_legal ? '#3ecf8e' : '#f87171'}`,
            }} />
            <span style={{ fontSize: 12, fontWeight: 700, color: zoningResult.is_legal ? '#3ecf8e' : '#f87171' }}>
              {zoningResult.is_legal ? 'Legal to Build' : 'Plot Unavailable'}
            </span>
          </div>
          <div style={{ fontSize: 10, color: '#555' }}>{zoningResult.zone_label}</div>
          {zoningResult.has_buildings && (
            <div style={{
              marginTop: 5, fontSize: 10, color: '#f59e0b',
              background: '#1e1200', borderRadius: 5, padding: '3px 8px', display: 'inline-block',
            }}>
              🏗️ {zoningResult.building_count} existing structure(s)
            </div>
          )}
          <div style={{ fontSize: 10, color: '#2e3550', marginTop: 5, paddingTop: 5, borderTop: '0.5px solid #1e2235' }}>
            {zoningResult.area_m2?.toLocaleString()} m² · {zoningResult.elevation_m}m elev
          </div>
        </div>
      )}

      {/* AI watermark */}
      <div style={{
        position: 'absolute', bottom: 16, right: 12, zIndex: 10,
        background: 'rgba(9,12,20,0.85)', border: '0.5px solid #1e2235',
        borderRadius: 8, fontSize: 10, color: '#252840',
        padding: '4px 10px', backdropFilter: 'blur(8px)',
        display: 'flex', alignItems: 'center', gap: 5,
      }}>
        <span style={{ color: '#7c5cf6' }}>✦</span>
        LandAI · NSGA-III · OR-Tools · Claude
      </div>

    </div>
  )
}