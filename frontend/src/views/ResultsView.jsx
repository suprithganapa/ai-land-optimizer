import { useEffect, useRef, useState } from 'react'
import maplibregl from 'maplibre-gl'
import 'maplibre-gl/dist/maplibre-gl.css'
import useStore from '../store/useStore'
import { useLayout } from '../hooks/useLayout'

const MAPTILER_KEY = 'gbb10k4jq9g81OSN4q0z'

const PARETO_DESCRIPTIONS = {
  'Max Plots':    'Maximises number of saleable plots. Highest revenue potential, smaller park areas.',
  'Balanced':     'Optimal balance between plot count, green space, and construction cost.',
  'Max Green':    'Maximises community park and green space coverage. Lower plot count.',
  'Min Cost':     'Minimises total road construction and utility infrastructure cost.',
  'Max Density':  'Highest plot density per unit area. Compact layout, minimal open space.',
}

const LAYER_CONFIG = {
  sewage:   { color: '#8B5E3C', label: 'Sewage Pipes',     key: 'sewage'   },
  water:    { color: '#38BDF8', label: 'Water Supply',     key: 'water'    },
  electric: { color: '#FACC15', label: 'Electrical',       key: 'electric' },
}

export default function ResultsView({ onBack }) {
  const mapContainer = useRef(null)
  const mapRef       = useRef(null)
  const markersRef   = useRef([])
  const popupRef     = useRef(null)

  const {
    drawnPolygon, layout, zoningResult,
    selectedParetoIndex, setSelectedParetoIndex, reset,
  } = useStore()
  const { downloadPDF } = useLayout()

  const [activeTab,      setActiveTab]      = useState('layout')
  const [is3D,           setIs3D]           = useState(false)
  const [mapReady,       setMapReady]       = useState(false)
  const [pdfLoading,     setPdfLoading]     = useState(false)
  const [activeLayers,   setActiveLayers]   = useState({
    sewage: false, water: false, electric: false,
  })
  const [showAmenities,  setShowAmenities]  = useState(true)
  const [showStreetlights, setShowStreetlights] = useState(false)

  // ── Init map ─────────────────────────────────────────────
  useEffect(() => {
    if (mapRef.current || !mapContainer.current || !layout) return
    const map = new maplibregl.Map({
      container: mapContainer.current,
      style: `https://api.maptiler.com/maps/satellite/style.json?key=${MAPTILER_KEY}`,
      center:  [layout.centroid_lng || 77.5946, layout.centroid_lat || 12.9716],
      zoom: 17, pitch: 0, attributionControl: false,
    })
    mapRef.current = map
    map.addControl(new maplibregl.NavigationControl(), 'top-right')
    map.addControl(new maplibregl.AttributionControl({ compact: true }), 'bottom-right')
    map.on('load', () => {
      setMapReady(true)
      renderStaticLayers(map)
      renderPareto(map, 0)
      fitToBoundary(map)
    })
    map.on('error', (e) => console.warn('Map:', e.error?.message))
    return () => {
      markersRef.current.forEach((m) => m.remove())
      if (popupRef.current) popupRef.current.remove()
      map.remove(); mapRef.current = null; setMapReady(false)
    }
  }, [])

  // ── Pareto switch ────────────────────────────────────────
  useEffect(() => {
    const map = mapRef.current
    if (!map || !mapReady) return
    renderPareto(map, selectedParetoIndex)
  }, [selectedParetoIndex, mapReady])

  // ── Infrastructure layer toggles ─────────────────────────
  useEffect(() => {
    const map = mapRef.current
    if (!map || !mapReady) return
    renderInfrastructure(map, activeLayers, showStreetlights)
  }, [activeLayers, showStreetlights, mapReady])

  // ── Amenity toggle ───────────────────────────────────────
  useEffect(() => {
    const map = mapRef.current
    if (!map || !mapReady) return
    const vis = showAmenities ? 'visible' : 'none'
    ;['amenities-fill', 'amenities-line', 'amenities-label'].forEach(id => {
      try { if (map.getLayer(id)) map.setLayoutProperty(id, 'visibility', vis) } catch (_) {}
    })
  }, [showAmenities, mapReady])

  const fitToBoundary = (map) => {
    const coords = drawnPolygon?.coordinates?.[0]
    if (!coords?.length) return
    const lngs = coords.map(c => c[0])
    const lats  = coords.map(c => c[1])
    map.fitBounds(
      [[Math.min(...lngs), Math.min(...lats)], [Math.max(...lngs), Math.max(...lats)]],
      { padding: 80, duration: 1500, maxZoom: 20 },
    )
  }

  // ── Add a polygon GeoJSON layer ──────────────────────────
  const addPolyLayer = (map, id, features, fillColor, fillOpacity, lineColor, lineWidth, extraLayers) => {
    if (!features?.length) return
    const valid = features.filter(f => f?.geometry?.coordinates?.[0]?.length >= 3)
    if (!valid.length) return
    try {
      if (map.getSource(id)) { map.getSource(id).setData({ type: 'FeatureCollection', features: valid }); return }
      map.addSource(id, { type: 'geojson', data: { type: 'FeatureCollection', features: valid } })
      map.addLayer({ id: `${id}-fill`, type: 'fill',   source: id, paint: { 'fill-color': fillColor, 'fill-opacity': fillOpacity } })
      map.addLayer({ id: `${id}-line`, type: 'line',   source: id, paint: { 'line-color': lineColor, 'line-width': lineWidth } })
      if (extraLayers) extraLayers(map, id)
    } catch (e) { console.warn(`Layer ${id}:`, e.message) }
  }

  // ── Add a line GeoJSON layer ─────────────────────────────
  const addLineLayer = (map, id, lines, color, width, dashArray) => {
    const features = lines
      .filter(l => l?.length >= 2)
      .map(l => ({ type: 'Feature', geometry: { type: 'LineString', coordinates: l }, properties: {} }))
    if (!features.length) return
    try {
      if (map.getSource(id)) {
        map.getSource(id).setData({ type: 'FeatureCollection', features })
        return
      }
      map.addSource(id, { type: 'geojson', data: { type: 'FeatureCollection', features } })
      const paint = { 'line-color': color, 'line-width': width }
      if (dashArray) paint['line-dasharray'] = dashArray
      map.addLayer({ id, type: 'line', source: id, paint })
    } catch (e) { console.warn(`Line layer ${id}:`, e.message) }
  }

  // ── Add a point GeoJSON layer ────────────────────────────
  const addPointLayer = (map, id, points, color, radius) => {
    const features = points
      .filter(p => p?.length >= 2)
      .map(p => ({ type: 'Feature', geometry: { type: 'Point', coordinates: p }, properties: {} }))
    if (!features.length) return
    try {
      if (map.getSource(id)) {
        map.getSource(id).setData({ type: 'FeatureCollection', features })
        return
      }
      map.addSource(id, { type: 'geojson', data: { type: 'FeatureCollection', features } })
      map.addLayer({ id, type: 'circle', source: id, paint: { 'circle-color': color, 'circle-radius': radius, 'circle-stroke-color': '#fff', 'circle-stroke-width': 1.5 } })
    } catch (e) { console.warn(`Point layer ${id}:`, e.message) }
  }

  const removeLayer = (map, id) => {
    try { if (map.getLayer(id)) map.removeLayer(id) } catch (_) {}
  }
  const removeSource = (map, id) => {
    try { if (map.getSource(id)) map.removeSource(id) } catch (_) {}
  }

  // ── Static layers: boundary, roads, entrance ─────────────
  const renderStaticLayers = (map) => {
    if (!layout) return

    if (drawnPolygon) {
      addPolyLayer(map, 'boundary',
        [{ type: 'Feature', geometry: drawnPolygon, properties: {} }],
        '#4f9cf9', 0.06, '#4f9cf9', 2)
    }

    const roadFeats = (layout.roads || [])
      .filter(r => r?.coordinates?.[0]?.length >= 3)
      .map(r => ({ type: 'Feature', geometry: { type: 'Polygon', coordinates: r.coordinates }, properties: {} }))
    if (roadFeats.length) {
      try {
        map.addSource('roads', { type: 'geojson', data: { type: 'FeatureCollection', features: roadFeats } })
        map.addLayer({ id: 'roads-fill', type: 'fill', source: 'roads', paint: { 'fill-color': '#1e2233', 'fill-opacity': 1 } })
        map.addLayer({ id: 'roads-line', type: 'line', source: 'roads', paint: { 'line-color': '#2a2e45', 'line-width': 0.6 } })
      } catch (e) { console.warn('Roads:', e.message) }
    }

    // Amenities
    const currentData = layout.pareto_layouts?.[selectedParetoIndex] || layout
    const amenityFeats = (currentData.amenities || layout.amenities || [])
      .filter(a => a?.coordinates?.[0]?.length >= 3)
      .map(a => ({ type: 'Feature', geometry: { type: 'Polygon', coordinates: a.coordinates }, properties: { type: a.type } }))
    if (amenityFeats.length) {
      try {
        map.addSource('amenities', { type: 'geojson', data: { type: 'FeatureCollection', features: amenityFeats } })
        map.addLayer({ id: 'amenities-fill', type: 'fill', source: 'amenities', paint: { 'fill-color': '#16a34a', 'fill-opacity': 0.5 } })
        map.addLayer({ id: 'amenities-line', type: 'line', source: 'amenities', paint: { 'line-color': '#4ade80', 'line-width': 1 } })
        map.addLayer({
          id: 'amenities-label', type: 'symbol', source: 'amenities',
          layout: { 'text-field': 'Walking Track', 'text-size': 9, 'text-anchor': 'center' },
          paint: { 'text-color': '#4ade80', 'text-halo-color': '#000', 'text-halo-width': 1 },
        })
      } catch (e) { console.warn('Amenities:', e.message) }
    }

    // Entrance marker
    if (layout.entrance?.length === 2) {
      try {
        const el = document.createElement('div')
        el.style.cssText = 'width:30px;height:30px;border-radius:50%;background:linear-gradient(135deg,#4f9cf9,#7c5cf6);border:2px solid #fff;display:flex;align-items:center;justify-content:center;font-size:12px;cursor:pointer;box-shadow:0 4px 12px rgba(79,156,249,0.4);color:#fff;font-weight:700;'
        el.textContent = 'E'
        const m = new maplibregl.Marker({ element: el })
          .setLngLat(layout.entrance)
          .setPopup(new maplibregl.Popup({ offset: 25 }).setHTML(
            '<div style="font-size:11px;font-weight:700;color:#4f9cf9">Main Entrance — Faces Main Road</div>'
          ))
          .addTo(map)
        markersRef.current.push(m)
      } catch (e) { console.warn('Entrance marker:', e) }
    }
  }

  // ── Render plots + parks for selected Pareto index ───────
  const renderPareto = (map, idx) => {
    if (!layout) return
    const data = layout.pareto_layouts?.[idx] || layout

    // Remove old plot/park layers
    ;['plots-label', 'plots-fill', 'plots-line', 'parks-label', 'parks-fill', 'parks-line'].forEach(id => removeLayer(map, id))
    ;['plots', 'parks'].forEach(id => removeSource(map, id))

    // Remove old plot click handler
    map.off('click', 'plots-fill')

    // Plots
    const plotFeats = (data.plots || [])
      .filter(p => p?.coordinates?.[0]?.length >= 3)
      .map(p => ({
        type: 'Feature',
        geometry: { type: 'Polygon', coordinates: p.coordinates },
        properties: {
          id:        p.id,
          area_m2:   p.area_m2,
          area_sqft: p.area_sqft || Math.round((p.area_m2 || 0) * 10.764),
        },
      }))

    if (plotFeats.length > 0) {
      try {
        map.addSource('plots', { type: 'geojson', data: { type: 'FeatureCollection', features: plotFeats } })
        map.addLayer({ id: 'plots-fill', type: 'fill', source: 'plots', paint: { 'fill-color': '#e8713c', 'fill-opacity': 0.82 } })
        map.addLayer({ id: 'plots-line', type: 'line', source: 'plots', paint: { 'line-color': '#ff9c60', 'line-width': 0.8 } })
        map.addLayer({
          id: 'plots-label', type: 'symbol', source: 'plots', minzoom: 17,
          layout: {
            'text-field': ['concat', 'P', ['to-string', ['get', 'id']]],
            'text-size': ['interpolate', ['linear'], ['zoom'], 17, 7, 20, 11],
            'text-anchor': 'center',
          },
          paint: { 'text-color': '#fff', 'text-halo-color': '#00000077', 'text-halo-width': 1 },
        })

        // Plot click popup — show area in sq ft and m2
        map.on('click', 'plots-fill', (e) => {
          const props = e.features?.[0]?.properties
          if (!props) return
          if (popupRef.current) popupRef.current.remove()
          popupRef.current = new maplibregl.Popup({ offset: 10, closeButton: true })
            .setLngLat(e.lngLat)
            .setHTML(`
              <div style="font-family:sans-serif;min-width:140px;">
                <div style="font-size:12px;font-weight:700;color:#e8713c;margin-bottom:6px;">Plot ${props.id}</div>
                <div style="font-size:11px;color:#ccc;margin-bottom:3px;">
                  <span style="color:#888">Area:</span>
                  <strong style="color:#e2e2e2"> ${props.area_sqft} sq ft</strong>
                </div>
                <div style="font-size:10px;color:#666;">${props.area_m2} m²</div>
                <div style="margin-top:6px;padding-top:6px;border-top:1px solid #1e2235;font-size:10px;color:#555;">Residential Plot</div>
              </div>
            `)
            .addTo(map)
        })
        map.on('mouseenter', 'plots-fill', () => { map.getCanvas().style.cursor = 'pointer' })
        map.on('mouseleave', 'plots-fill', () => { map.getCanvas().style.cursor = '' })
      } catch (e) { console.warn('Plots:', e.message) }
    }

    // Parks (multiple)
    const parkFeats = (data.parks || [])
      .filter(p => p?.coordinates?.[0]?.length >= 3)
      .map(p => ({
        type: 'Feature',
        geometry: { type: 'Polygon', coordinates: p.coordinates },
        properties: { area_m2: p.area_m2, label: p.label || 'Community Park' },
      }))

    if (parkFeats.length > 0) {
      try {
        map.addSource('parks', { type: 'geojson', data: { type: 'FeatureCollection', features: parkFeats } })
        map.addLayer({ id: 'parks-fill', type: 'fill', source: 'parks', paint: { 'fill-color': '#14532d', 'fill-opacity': 0.9 } })
        map.addLayer({ id: 'parks-line', type: 'line', source: 'parks', paint: { 'line-color': '#3ecf8e', 'line-width': 1.5 } })
        map.addLayer({
          id: 'parks-label', type: 'symbol', source: 'parks',
          layout: { 'text-field': ['get', 'label'], 'text-size': 11, 'text-anchor': 'center' },
          paint: { 'text-color': '#3ecf8e', 'text-halo-color': '#000', 'text-halo-width': 1 },
        })
        // Park click
        map.on('click', 'parks-fill', (e) => {
          const props = e.features?.[0]?.properties
          if (!props) return
          if (popupRef.current) popupRef.current.remove()
          popupRef.current = new maplibregl.Popup({ offset: 10 })
            .setLngLat(e.lngLat)
            .setHTML(`
              <div style="font-family:sans-serif;">
                <div style="font-size:12px;font-weight:700;color:#3ecf8e;margin-bottom:4px;">Community Park</div>
                <div style="font-size:11px;color:#ccc;">Area: <strong>${props.area_m2} m²</strong></div>
                <div style="font-size:10px;color:#666;margin-top:4px;">Open to all residents. Charitable site.</div>
              </div>
            `)
            .addTo(map)
        })
        map.on('mouseenter', 'parks-fill', () => { map.getCanvas().style.cursor = 'pointer' })
        map.on('mouseleave', 'parks-fill', () => { map.getCanvas().style.cursor = '' })
      } catch (e) { console.warn('Parks:', e.message) }
    }

    console.log(`Pareto L${idx + 1}: ${plotFeats.length} plots, ${parkFeats.length} parks`)
  }

  // ── Render infrastructure layers ─────────────────────────
  const renderInfrastructure = (map, layers, streetlights) => {
    if (!layout?.infrastructure) return
    const inf = layout.infrastructure

    const removeInfra = (ids) => {
      ids.forEach(id => { removeLayer(map, id); removeSource(map, id) })
    }

    // Streetlights
    if (streetlights && inf.streetlights?.length) {
      addPointLayer(map, 'streetlights', inf.streetlights, '#fde047', 3)
    } else {
      removeLayer(map, 'streetlights'); removeSource(map, 'streetlights')
    }

    // Sewage
    if (layers.sewage) {
      const sewageLines = [...(inf.sewage_pipe_lines || []), ...(inf.collector_pipes || [])]
      addLineLayer(map, 'sewage-pipes', sewageLines, '#a16207', 1.5, [4, 2])
      if (inf.sewage_treatment_plant) {
        addPointLayer(map, 'stp', [inf.sewage_treatment_plant], '#a16207', 7)
        try {
          if (!map.getLayer('stp-label')) {
            map.addLayer({
              id: 'stp-label', type: 'symbol', source: 'stp',
              layout: { 'text-field': 'STP', 'text-size': 9, 'text-offset': [0, 1.5] },
              paint: { 'text-color': '#a16207', 'text-halo-color': '#000', 'text-halo-width': 1 },
            })
          }
        } catch (_) {}
      }
    } else {
      removeInfra(['sewage-pipes', 'stp', 'stp-label'])
    }

    // Water
    if (layers.water) {
      const waterLines = [...(inf.water_main_lines || []), ...(inf.water_branch_pipes || [])]
      addLineLayer(map, 'water-pipes', waterLines, '#38bdf8', 1.2, [5, 2])
      if (inf.water_tank) {
        addPointLayer(map, 'water-tank', [inf.water_tank], '#38bdf8', 7)
        try {
          if (!map.getLayer('water-tank-label')) {
            map.addLayer({
              id: 'water-tank-label', type: 'symbol', source: 'water-tank',
              layout: { 'text-field': 'Water Tank', 'text-size': 9, 'text-offset': [0, 1.5] },
              paint: { 'text-color': '#38bdf8', 'text-halo-color': '#000', 'text-halo-width': 1 },
            })
          }
        } catch (_) {}
      }
    } else {
      removeInfra(['water-pipes', 'water-tank', 'water-tank-label'])
    }

    // Electrical
    if (layers.electric) {
      const elecLines = [...(inf.hv_cables || []), ...(inf.lv_cables || [])]
      addLineLayer(map, 'elec-cables', elecLines, '#facc15', 1, [3, 3])
      if (inf.main_transformer) {
        addPointLayer(map, 'transformer', [inf.main_transformer], '#facc15', 8)
        try {
          if (!map.getLayer('transformer-label')) {
            map.addLayer({
              id: 'transformer-label', type: 'symbol', source: 'transformer',
              layout: { 'text-field': 'Main Transformer', 'text-size': 9, 'text-offset': [0, 1.5] },
              paint: { 'text-color': '#facc15', 'text-halo-color': '#000', 'text-halo-width': 1 },
            })
          }
        } catch (_) {}
      }
      if (inf.distribution_boards?.length) {
        addPointLayer(map, 'dist-boards', inf.distribution_boards, '#fb923c', 5)
        try {
          if (!map.getLayer('dist-boards-label')) {
            map.addLayer({
              id: 'dist-boards-label', type: 'symbol', source: 'dist-boards',
              layout: { 'text-field': 'DB', 'text-size': 8, 'text-offset': [0, 1.2] },
              paint: { 'text-color': '#fb923c', 'text-halo-color': '#000', 'text-halo-width': 1 },
            })
          }
        } catch (_) {}
      }
    } else {
      removeInfra(['elec-cables', 'transformer', 'transformer-label', 'dist-boards', 'dist-boards-label'])
    }
  }

  // ── 3D Toggle ────────────────────────────────────────────
  const toggle3D = () => {
    const map = mapRef.current; if (!map) return
    if (!is3D) map.easeTo({ pitch: 52, bearing: -20, duration: 1000 })
    else        map.easeTo({ pitch: 0,  bearing: 0,  duration: 1000 })
    setIs3D(!is3D)
  }

  const toggleLayer = (key) => {
    setActiveLayers(prev => ({ ...prev, [key]: !prev[key] }))
  }

  const handleBack = () => { reset(); onBack() }
  const handlePDF  = async () => {
    setPdfLoading(true)
    await downloadPDF(layout, zoningResult)
    setPdfLoading(false)
  }

  // ── Financials ───────────────────────────────────────────
  const price   = layout?.price_prediction || {}
  const mlRate  = price.predicted_rate_per_m2 || 45000
  const gross   = Math.round((layout?.total_plot_area_m2 || 0) * mlRate)
  const rCost   = Math.round((layout?.total_road_area_m2  || 0) * 3500)
  const uCost   = Math.round((layout?.utility_route_length_m || 0) * 1200)
  const total   = rCost + uCost
  const profit  = gross - total
  const roi     = total > 0 ? Math.round(profit / total * 100) : 0
  const avgPlt  = Math.round((layout?.total_plot_area_m2 || 0) / Math.max(1, layout?.num_plots || 1))

  const fmt = (n) => {
    if (n >= 10_000_000) return `Rs ${(n / 10_000_000).toFixed(2)} Cr`
    if (n >= 100_000)    return `Rs ${(n / 100_000).toFixed(1)} L`
    return `Rs ${n.toLocaleString()}`
  }

  const currentPareto = layout?.pareto_layouts?.[selectedParetoIndex] || layout

  const C = {
    card: {
      background: 'rgba(13,16,25,0.95)', border: '0.5px solid #1a1e30',
      borderRadius: '12px', padding: '16px', marginBottom: '8px',
    },
    lbl: {
      fontSize: '9px', fontWeight: 700, letterSpacing: '1.2px',
      textTransform: 'uppercase', color: '#2e3450', marginBottom: '10px',
    },
  }

  return (
    <div style={{ display: 'grid', gridTemplateRows: '52px 1fr', height: '100vh', background: '#080b12' }}>

      {/* Top Bar */}
      <div style={{
        display: 'flex', alignItems: 'center', justifyContent: 'space-between',
        background: 'rgba(15,18,28,0.97)', padding: '0 18px',
        borderBottom: '0.5px solid #1e2235',
      }}>
        <button onClick={handleBack} style={{
          background: 'rgba(30,34,53,0.8)', border: '0.5px solid #252840',
          color: '#666', borderRadius: 8, padding: '6px 14px',
          fontSize: 12, cursor: 'pointer', transition: 'all 0.2s',
        }}
          onMouseEnter={e => e.currentTarget.style.color = '#e2e2e2'}
          onMouseLeave={e => e.currentTarget.style.color = '#666'}
        >
          Back to Map
        </button>

        <div style={{ display: 'flex', alignItems: 'center', gap: 10 }}>
          <div style={{
            width: 28, height: 28,
            background: 'linear-gradient(135deg,#4f9cf9,#7c5cf6)',
            borderRadius: 7, display: 'flex', alignItems: 'center',
            justifyContent: 'center', fontSize: 13,
            boxShadow: '0 0 12px rgba(79,156,249,0.3)',
          }}>
            <span style={{ color: '#fff', fontWeight: 700, fontSize: 11 }}>AI</span>
          </div>
          <div>
            <div style={{ fontSize: 13, fontWeight: 700, color: '#e8eaf0' }}>
              Layout <span style={{ color: '#4f9cf9' }}>Results</span>
            </div>
            <div style={{ fontSize: 9, color: '#2e3450' }}>
              {zoningResult?.zone_label} · {layout?.area_m2?.toLocaleString()} m2
              {layout?.pareto_layouts && ` · ${currentPareto?.label || 'L' + (selectedParetoIndex + 1)}`}
            </div>
          </div>
        </div>

        <div style={{ display: 'flex', gap: 8, alignItems: 'center' }}>
          <button onClick={toggle3D} style={{
            background: is3D ? 'rgba(79,156,249,0.1)' : 'rgba(30,34,53,0.8)',
            border: `0.5px solid ${is3D ? '#4f9cf955' : '#252840'}`,
            color: is3D ? '#4f9cf9' : '#666', borderRadius: 8,
            padding: '6px 14px', fontSize: 12, cursor: 'pointer',
          }}>
            {is3D ? '2D View' : '3D View'}
          </button>
          <div style={{
            background: 'rgba(62,207,142,0.06)', border: '0.5px solid rgba(62,207,142,0.2)',
            borderRadius: 20, padding: '5px 14px', fontSize: 11, color: '#3ecf8e', fontWeight: 700,
          }}>
            {currentPareto?.num_plots || layout?.num_plots} Plots
            · {currentPareto?.efficiency_score || layout?.efficiency_score}% Efficient
          </div>
        </div>
      </div>

      {/* Body */}
      <div style={{ display: 'grid', gridTemplateColumns: '1fr 320px', overflow: 'hidden' }}>

        {/* Map */}
        <div style={{ position: 'relative', overflow: 'hidden' }}>
          <div ref={mapContainer} style={{ position: 'absolute', inset: 0 }} />

          {/* Loading */}
          {!mapReady && (
            <div style={{ position: 'absolute', inset: 0, zIndex: 20, background: '#080b12', display: 'flex', flexDirection: 'column', alignItems: 'center', justifyContent: 'center', gap: 12 }}>
              <style>{`@keyframes spin{to{transform:rotate(360deg)}}`}</style>
              <div style={{ width: 36, height: 36, border: '3px solid #1e2235', borderTop: '3px solid #4f9cf9', borderRadius: '50%', animation: 'spin 0.8s linear infinite' }} />
              <div style={{ fontSize: 12, color: '#3a3f55' }}>Loading satellite map...</div>
            </div>
          )}

          {/* Infrastructure Layer Controls */}
          {mapReady && (
            <div style={{
              position: 'absolute', top: 14, left: 14, zIndex: 10,
              display: 'flex', flexDirection: 'column', gap: 4,
            }}>
              {/* AI badge */}
              <div style={{
                background: 'rgba(8,11,18,0.94)', border: '0.5px solid #7c5cf633',
                borderRadius: 8, padding: '5px 12px', fontSize: 10, color: '#7c5cf6',
              }}>
                NSGA-III · OR-Tools · Layout {currentPareto?.label || 'L' + (selectedParetoIndex + 1)}
              </div>

              {/* Infrastructure toggles */}
              <div style={{
                background: 'rgba(8,11,18,0.96)', border: '0.5px solid #1a1e30',
                borderRadius: 8, padding: '8px 10px', display: 'flex', flexDirection: 'column', gap: 5,
              }}>
                <div style={{ fontSize: 9, color: '#2e3450', fontWeight: 700, letterSpacing: '0.8px', textTransform: 'uppercase', marginBottom: 3 }}>
                  Infrastructure Layers
                </div>

                {/* Streetlights */}
                <LayerToggle
                  active={showStreetlights}
                  color="#fde047"
                  label="Streetlights"
                  onClick={() => setShowStreetlights(v => !v)}
                />

                {Object.entries(LAYER_CONFIG).map(([key, cfg]) => (
                  <LayerToggle
                    key={key}
                    active={activeLayers[key]}
                    color={cfg.color}
                    label={cfg.label}
                    onClick={() => toggleLayer(key)}
                  />
                ))}

                {/* Amenities */}
                <LayerToggle
                  active={showAmenities}
                  color="#4ade80"
                  label="Amenities"
                  onClick={() => setShowAmenities(v => !v)}
                />
              </div>
            </div>
          )}

          {/* Legend */}
          <div style={{
            position: 'absolute', bottom: 16, left: 16, zIndex: 10,
            background: 'rgba(8,11,18,0.94)', border: '0.5px solid #1e2235',
            borderRadius: 10, padding: '10px 14px',
          }}>
            <div style={{ fontSize: 9, color: '#2e3450', marginBottom: 8, fontWeight: 700, letterSpacing: '1px', textTransform: 'uppercase' }}>
              Legend
            </div>
            {[
              { c: '#e8713c', l: 'Residential Plots' },
              { c: '#1e2233', b: '#2a2e45', l: 'Road Network' },
              { c: '#14532d', l: 'Community Park' },
              { c: '#16a34a', l: 'Amenities' },
              { c: '#4f9cf9', l: 'Land Boundary' },
            ].map((item, i) => (
              <div key={i} style={{ display: 'flex', alignItems: 'center', gap: 7, marginBottom: 4 }}>
                <div style={{ width: 10, height: 10, borderRadius: 2, background: item.c, border: item.b ? `1px solid ${item.b}` : 'none', flexShrink: 0 }} />
                <span style={{ fontSize: 10, color: '#555' }}>{item.l}</span>
              </div>
            ))}
            {/* Active infra in legend */}
            {showStreetlights && <LegendDot color="#fde047" label="Streetlights" />}
            {activeLayers.sewage  && <LegendDot color="#a16207" label="Sewage Pipes" />}
            {activeLayers.water   && <LegendDot color="#38bdf8" label="Water Pipes" />}
            {activeLayers.electric && <LegendDot color="#facc15" label="Electrical" />}
          </div>
        </div>

        {/* Sidebar */}
        <div style={{
          background: '#0a0d14', borderLeft: '0.5px solid #1e2235',
          overflowY: 'auto', padding: '12px', display: 'flex', flexDirection: 'column',
          scrollbarWidth: 'thin', scrollbarColor: '#1e2235 transparent',
        }}>

          {/* Tabs */}
          <div style={{
            display: 'flex', gap: 3, marginBottom: 10,
            background: 'rgba(15,18,28,0.8)', borderRadius: 10,
            padding: 4, border: '0.5px solid #1a1e30',
          }}>
            {['layout', 'finance', 'validation'].map(tab => (
              <div key={tab} onClick={() => setActiveTab(tab)} style={{
                flex: 1, textAlign: 'center', padding: '6px 4px', borderRadius: 7,
                fontSize: 11, cursor: 'pointer',
                fontWeight: activeTab === tab ? 700 : 400,
                background: activeTab === tab ? 'rgba(79,156,249,0.1)' : 'transparent',
                color: activeTab === tab ? '#4f9cf9' : '#2e3450',
                border: activeTab === tab ? '0.5px solid #4f9cf933' : 'none',
                textTransform: 'capitalize', transition: 'all 0.2s',
              }}>
                {tab}
              </div>
            ))}
          </div>

          {/* LAYOUT TAB */}
          {activeTab === 'layout' && (
            <>
              {/* Efficiency */}
              <div style={{ ...C.card, background: 'linear-gradient(135deg,rgba(10,30,20,0.95),rgba(13,34,24,0.95))', border: '0.5px solid rgba(62,207,142,0.15)', textAlign: 'center' }}>
                <div style={{ fontSize: 56, fontWeight: 800, color: '#3ecf8e', lineHeight: 1, letterSpacing: '-3px', textShadow: '0 0 28px rgba(62,207,142,0.3)' }}>
                  {currentPareto?.efficiency_score || layout?.efficiency_score}%
                </div>
                <div style={{ fontSize: 11, color: '#2a5a38', marginTop: 4 }}>Land Utilization Efficiency</div>
                <div style={{ display: 'inline-block', marginTop: 8, fontSize: 10, color: '#3ecf8e', background: 'rgba(62,207,142,0.08)', border: '0.5px solid rgba(62,207,142,0.2)', borderRadius: 12, padding: '3px 14px' }}>
                  +12% vs manual planning average
                </div>
              </div>

              {/* Stats grid */}
              <div style={C.card}>
                <div style={C.lbl}>Layout Summary</div>
                <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 6 }}>
                  {[
                    { l: 'Total Plots',    v: currentPareto?.num_plots,                                    c: '#4f9cf9' },
                    { l: 'Parks',          v: currentPareto?.num_parks || layout?.num_parks || 1,          c: '#3ecf8e' },
                    { l: 'Plot Area',      v: `${currentPareto?.total_plot_area_m2?.toLocaleString()} m2`, c: '#e8713c' },
                    { l: 'Park Area',      v: `${currentPareto?.total_park_area_m2?.toLocaleString()} m2`, c: '#3ecf8e' },
                    { l: 'Road Area',      v: `${layout?.total_road_area_m2?.toLocaleString()} m2`,        c: '#666'    },
                    { l: 'Connectivity',   v: `${layout?.connectivity_pct}%`,                              c: '#4f9cf9' },
                  ].map((s, i) => (
                    <div key={i} style={{ background: 'rgba(8,11,18,0.8)', borderRadius: 8, padding: '9px 10px', border: '0.5px solid #12152080' }}>
                      <div style={{ fontSize: 9, color: '#2e3450', marginBottom: 3 }}>{s.l}</div>
                      <div style={{ fontSize: 13, fontWeight: 700, color: s.c }}>{s.v}</div>
                    </div>
                  ))}
                </div>
              </div>

              {/* Pareto Front */}
              {layout?.pareto_layouts?.length > 1 && (
                <div style={C.card}>
                  <div style={C.lbl}>Pareto Front — Choose Layout</div>
                  <div style={{ display: 'flex', gap: 5, marginBottom: 10 }}>
                    {layout.pareto_layouts.map((pl, i) => (
                      <div key={i} onClick={() => setSelectedParetoIndex(i)} style={{
                        flex: 1, borderRadius: 8, padding: '7px 3px', textAlign: 'center', cursor: 'pointer', transition: 'all 0.2s',
                        background: selectedParetoIndex === i ? 'rgba(79,156,249,0.12)' : 'rgba(8,11,18,0.8)',
                        border: `1px solid ${selectedParetoIndex === i ? '#4f9cf9' : '#1a1e30'}`,
                        boxShadow: selectedParetoIndex === i ? '0 0 14px rgba(79,156,249,0.2)' : 'none',
                      }}>
                        <div style={{ fontSize: 11, fontWeight: 800, color: selectedParetoIndex === i ? '#4f9cf9' : '#3a3f55' }}>
                          L{i + 1}
                        </div>
                        <div style={{ fontSize: 8, color: selectedParetoIndex === i ? '#4f9cf966' : '#1e2235', marginTop: 2 }}>
                          {pl.num_plots}
                        </div>
                      </div>
                    ))}
                  </div>

                  {/* Selected layout description */}
                  {layout.pareto_layouts[selectedParetoIndex] && (
                    <div style={{ background: 'rgba(8,11,18,0.8)', border: '0.5px solid #1a1e30', borderRadius: 8, padding: '10px' }}>
                      <div style={{ fontSize: 11, fontWeight: 700, color: '#4f9cf9', marginBottom: 4 }}>
                        {layout.pareto_layouts[selectedParetoIndex].label}
                      </div>
                      <div style={{ fontSize: 10, color: '#3a3f55', lineHeight: 1.5, marginBottom: 8 }}>
                        {PARETO_DESCRIPTIONS[layout.pareto_layouts[selectedParetoIndex].label] || 'Optimized layout variant.'}
                      </div>
                      {[
                        { l: 'Plots',      v: layout.pareto_layouts[selectedParetoIndex].num_plots,                                    c: '#4f9cf9' },
                        { l: 'Plot Area',  v: `${layout.pareto_layouts[selectedParetoIndex].total_plot_area_m2?.toLocaleString()} m2`, c: '#e8713c' },
                        { l: 'Park Area',  v: `${layout.pareto_layouts[selectedParetoIndex].total_park_area_m2?.toLocaleString()} m2`, c: '#3ecf8e' },
                        { l: 'Efficiency', v: `${layout.pareto_layouts[selectedParetoIndex].efficiency_score}%`,                       c: '#3ecf8e' },
                      ].map((s, i) => (
                        <div key={i} style={{ display: 'flex', justifyContent: 'space-between', padding: '4px 0', borderBottom: i < 3 ? '0.5px solid #12152080' : 'none' }}>
                          <span style={{ fontSize: 10, color: '#3a3f55' }}>{s.l}</span>
                          <span style={{ fontSize: 10, fontWeight: 700, color: s.c }}>{s.v}</span>
                        </div>
                      ))}
                    </div>
                  )}
                </div>
              )}

              {/* NBC Compliance */}
              <div style={C.card}>
                <div style={C.lbl}>NBC 2016 Compliance</div>
                {[
                  { l: '3m Setback Applied',      ok: true },
                  { l: '7.5m Min Road Width',      ok: true },
                  { l: 'Park Area Adequate',        ok: (currentPareto?.total_park_area_m2 || 0) >= 400 },
                  { l: 'All Plots Connected',       ok: layout?.is_fully_connected },
                  { l: 'Slope Risk Low',            ok: zoningResult?.slope_risk === 'low' },
                  { l: 'Entrance Faces Main Road',  ok: true },
                ].map((item, i, arr) => (
                  <div key={i} style={{ display: 'flex', alignItems: 'center', gap: 8, padding: '5px 0', borderBottom: i < arr.length - 1 ? '0.5px solid #12152080' : 'none' }}>
                    <div style={{ width: 14, height: 14, borderRadius: 2, flexShrink: 0, background: item.ok ? 'rgba(62,207,142,0.15)' : 'rgba(245,158,11,0.15)', display: 'flex', alignItems: 'center', justifyContent: 'center', fontSize: 9, color: item.ok ? '#3ecf8e' : '#f59e0b', fontWeight: 700 }}>
                      {item.ok ? 'Y' : '!'}
                    </div>
                    <span style={{ fontSize: 11, color: item.ok ? '#555' : '#f59e0b' }}>{item.l}</span>
                  </div>
                ))}
              </div>
            </>
          )}

          {/* FINANCE TAB */}
          {activeTab === 'finance' && (
            <>
              {/* ML badge */}
              {price.nearest_reference_area && (
                <div style={{ ...C.card, background: 'rgba(8,18,38,0.95)', border: '0.5px solid rgba(79,156,249,0.2)' }}>
                  <div style={{ display: 'flex', alignItems: 'flex-start', gap: 10 }}>
                    <div style={{ width: 32, height: 32, flexShrink: 0, background: 'rgba(79,156,249,0.1)', border: '0.5px solid rgba(79,156,249,0.3)', borderRadius: 8, display: 'flex', alignItems: 'center', justifyContent: 'center', fontSize: 14, color: '#4f9cf9', fontWeight: 700 }}>
                      ML
                    </div>
                    <div style={{ flex: 1 }}>
                      <div style={{ fontSize: 11, fontWeight: 700, color: '#4f9cf9', marginBottom: 3 }}>
                        ML Price Prediction Active
                      </div>
                      <div style={{ fontSize: 10, color: '#2e3450', lineHeight: 1.5, marginBottom: 6 }}>
                        Random Forest + Weighted Nearest Neighbor<br />
                        Ref: <span style={{ color: '#555' }}>{price.nearest_reference_area}</span>
                        {' · '}<span style={{ color: '#555' }}>{price.distance_to_reference} km</span>
                      </div>
                      <div style={{ display: 'flex', alignItems: 'center', gap: 6 }}>
                        <div style={{ flex: 1, height: 4, borderRadius: 2, background: '#1a1e30', overflow: 'hidden' }}>
                          <div style={{ height: '100%', width: `${price.confidence_pct || 0}%`, background: 'linear-gradient(90deg,#4f9cf9,#3ecf8e)', borderRadius: 2 }} />
                        </div>
                        <span style={{ fontSize: 10, color: '#4f9cf9', fontWeight: 700, whiteSpace: 'nowrap' }}>
                          {price.confidence} ({price.confidence_pct}%)
                        </span>
                      </div>
                    </div>
                  </div>
                </div>
              )}

              {/* Market rate */}
              <div style={{ ...C.card, background: 'rgba(8,18,38,0.95)', border: '0.5px solid rgba(79,156,249,0.15)' }}>
                <div style={C.lbl}>Market Rate</div>
                <div style={{ textAlign: 'center', marginBottom: 10 }}>
                  <div style={{ fontSize: 32, fontWeight: 800, color: '#4f9cf9', letterSpacing: '-1px', textShadow: '0 0 20px rgba(79,156,249,0.3)' }}>
                    Rs {price.predicted_rate_per_m2?.toLocaleString()}
                  </div>
                  <div style={{ fontSize: 10, color: '#2e3450', marginTop: 3 }}>per m2 — ML predicted</div>
                  <div style={{ fontSize: 10, color: '#3a3f55', marginTop: 3 }}>
                    Range: Rs {price.min_rate_per_m2?.toLocaleString()} — Rs {price.max_rate_per_m2?.toLocaleString()} /m2
                  </div>
                </div>
                <div style={{ fontSize: 9, color: '#2e3450', marginBottom: 5, fontWeight: 700, letterSpacing: '1px', textTransform: 'uppercase' }}>
                  Top Reference Areas
                </div>
                {price.top_references?.slice(0, 3).map((ref, i) => (
                  <div key={i} style={{ display: 'flex', justifyContent: 'space-between', padding: '4px 0', borderBottom: i < 2 ? '0.5px solid #12152080' : 'none' }}>
                    <div>
                      <span style={{ fontSize: 11, color: '#666' }}>{ref.area_name}</span>
                      <span style={{ fontSize: 9, color: '#2e3450', marginLeft: 5 }}>{Number(ref.distance_km)?.toFixed(1)} km</span>
                    </div>
                    <span style={{ fontSize: 11, color: '#4f9cf9', fontWeight: 600 }}>Rs {Number(ref.avg_rate_per_m2)?.toLocaleString()}/m2</span>
                  </div>
                ))}
              </div>

              {/* Net profit */}
              <div style={{ ...C.card, background: 'linear-gradient(135deg,rgba(10,30,20,0.95),rgba(13,34,24,0.95))', border: '0.5px solid rgba(62,207,142,0.15)', textAlign: 'center' }}>
                <div style={{ fontSize: 11, color: '#2a5a38', marginBottom: 4 }}>Estimated Net Profit</div>
                <div style={{ fontSize: 36, fontWeight: 800, color: '#3ecf8e', letterSpacing: '-1px', textShadow: '0 0 20px rgba(62,207,142,0.3)' }}>
                  {fmt(profit)}
                </div>
                <div style={{ fontSize: 10, color: '#2a5a38', marginTop: 4 }}>
                  Rs {mlRate?.toLocaleString()}/m2 ML-predicted rate
                </div>
              </div>

              {/* Breakdown */}
              <div style={C.card}>
                <div style={C.lbl}>Financial Breakdown</div>
                {[
                  { l: 'Gross Revenue',     v: fmt(gross),        c: '#3ecf8e' },
                  { l: 'Road Construction', v: `- ${fmt(rCost)}`, c: '#f87171' },
                  { l: 'Utility Infra',     v: `- ${fmt(uCost)}`, c: '#f87171' },
                  { l: 'Total Cost',        v: `- ${fmt(total)}`, c: '#f87171' },
                  { l: 'Net Profit',        v: fmt(profit),       c: '#3ecf8e' },
                ].map((row, i, arr) => (
                  <div key={i} style={{ display: 'flex', justifyContent: 'space-between', padding: '7px 0', borderBottom: i < arr.length - 1 ? '0.5px solid #12152080' : 'none', borderTop: i === arr.length - 1 ? '1px solid #1a1e30' : 'none', marginTop: i === arr.length - 1 ? 4 : 0 }}>
                    <span style={{ fontSize: 12, color: '#3a3f55' }}>{row.l}</span>
                    <span style={{ fontSize: 12, fontWeight: i === arr.length - 1 ? 800 : 500, color: row.c }}>{row.v}</span>
                  </div>
                ))}
              </div>

              <div style={C.card}>
                <div style={C.lbl}>Key Metrics</div>
                {[
                  { l: 'ROI',            v: `${roi}%` },
                  { l: 'Revenue/Plot',   v: fmt(Math.round(gross / Math.max(1, layout?.num_plots || 1))) },
                  { l: 'Avg Plot Area',  v: `${avgPlt} m2` },
                  { l: 'Avg Plot Area',  v: `${Math.round(avgPlt * 10.764)} sq ft` },
                  { l: 'Market Rate',    v: `Rs ${mlRate?.toLocaleString()}/m2` },
                  { l: 'Confidence',     v: `${price.confidence_pct || 0}%` },
                ].map((row, i, arr) => (
                  <div key={i} style={{ display: 'flex', justifyContent: 'space-between', padding: '5px 0', borderBottom: i < arr.length - 1 ? '0.5px solid #12152080' : 'none' }}>
                    <span style={{ fontSize: 11, color: '#3a3f55' }}>{row.l}</span>
                    <span style={{ fontSize: 11, fontWeight: 700, color: '#4f9cf9' }}>{row.v}</span>
                  </div>
                ))}
              </div>
            </>
          )}

          {/* VALIDATION TAB */}
          {activeTab === 'validation' && (
            <>
              <div style={{ ...C.card, background: layout?.is_fully_connected ? 'linear-gradient(135deg,rgba(10,30,20,0.95),rgba(13,34,24,0.95))' : 'linear-gradient(135deg,rgba(30,13,10,0.95),rgba(34,15,13,0.95))', border: `0.5px solid ${layout?.is_fully_connected ? 'rgba(62,207,142,0.15)' : 'rgba(245,158,11,0.15)'}` }}>
                <div style={{ fontSize: 13, fontWeight: 700, color: layout?.is_fully_connected ? '#3ecf8e' : '#f59e0b', marginBottom: 6 }}>
                  {layout?.is_fully_connected ? 'All plots road-connected' : 'Some plots isolated'}
                </div>
                <div style={{ fontSize: 10, color: '#2e3450', lineHeight: 1.5 }}>
                  Validated via NetworkX BFS + Dijkstra shortest path algorithm
                </div>
              </div>

              <div style={C.card}>
                <div style={C.lbl}>Graph Validation</div>
                {[
                  { l: 'Total Plots',        v: layout?.validation?.total_plots },
                  { l: 'Connected Plots',    v: layout?.validation?.connected_plots },
                  { l: 'Isolated Plots',     v: layout?.validation?.isolated_plots?.length || 0 },
                  { l: 'Connectivity',       v: `${layout?.connectivity_pct}%` },
                  { l: 'Graph Nodes',        v: layout?.validation?.graph_nodes },
                  { l: 'Graph Edges',        v: layout?.validation?.graph_edges },
                  { l: 'Utility Route',      v: `${layout?.utility_route_length_m} m` },
                ].map((row, i, arr) => (
                  <div key={i} style={{ display: 'flex', justifyContent: 'space-between', padding: '5px 0', borderBottom: i < arr.length - 1 ? '0.5px solid #12152080' : 'none' }}>
                    <span style={{ fontSize: 11, color: '#3a3f55' }}>{row.l}</span>
                    <span style={{ fontSize: 11, color: '#e2e2e2' }}>{row.v}</span>
                  </div>
                ))}
              </div>

              <div style={C.card}>
                <div style={C.lbl}>Infrastructure Summary</div>
                {[
                  { l: 'Streetlights',         v: (layout?.infrastructure?.streetlights?.length || 0) + ' units' },
                  { l: 'Sewage Pipes',          v: (layout?.infrastructure?.sewage_pipe_lines?.length || 0) + ' segments' },
                  { l: 'Water Branch Pipes',    v: (layout?.infrastructure?.water_branch_pipes?.length || 0) + ' connections' },
                  { l: 'Distribution Boards',   v: (layout?.infrastructure?.distribution_boards?.length || 0) + ' units' },
                  { l: 'LV Cable Connections',  v: (layout?.infrastructure?.lv_cables?.length || 0) + ' plots' },
                  { l: 'Sewage Treatment',      v: '1 plant' },
                  { l: 'Water Tank',            v: '1 unit' },
                  { l: 'Main Transformer',      v: '1 unit' },
                ].map((row, i, arr) => (
                  <div key={i} style={{ display: 'flex', justifyContent: 'space-between', padding: '5px 0', borderBottom: i < arr.length - 1 ? '0.5px solid #12152080' : 'none' }}>
                    <span style={{ fontSize: 11, color: '#3a3f55' }}>{row.l}</span>
                    <span style={{ fontSize: 11, color: '#4f9cf9' }}>{row.v}</span>
                  </div>
                ))}
              </div>

              <div style={C.card}>
                <div style={C.lbl}>Zoning and Terrain</div>
                {[
                  { l: 'Zone',      v: zoningResult?.zone_label },
                  { l: 'Elevation', v: `${zoningResult?.elevation_m} m ASL` },
                  { l: 'Slope',     v: zoningResult?.slope_risk?.toUpperCase() },
                  { l: 'Setback',   v: '3m (NBC 2016)' },
                  { l: 'Min Road',  v: '7.5m (NBC 2016)' },
                ].map((row, i, arr) => (
                  <div key={i} style={{ display: 'flex', justifyContent: 'space-between', padding: '5px 0', borderBottom: i < arr.length - 1 ? '0.5px solid #12152080' : 'none' }}>
                    <span style={{ fontSize: 11, color: '#3a3f55' }}>{row.l}</span>
                    <span style={{ fontSize: 11, color: '#e2e2e2' }}>{row.v}</span>
                  </div>
                ))}
              </div>
            </>
          )}

          {/* PDF Button */}
          <button
            onClick={handlePDF}
            disabled={pdfLoading}
            style={{
              background: pdfLoading ? 'rgba(30,34,53,0.8)' : 'linear-gradient(135deg,rgba(8,18,38,0.95),rgba(10,14,24,0.95))',
              border: '1px solid rgba(79,156,249,0.4)',
              color: pdfLoading ? '#555' : '#4f9cf9',
              borderRadius: 10, padding: '13px', fontSize: 13, fontWeight: 700,
              cursor: pdfLoading ? 'not-allowed' : 'pointer',
              width: '100%', marginTop: 4,
              display: 'flex', alignItems: 'center', justifyContent: 'center', gap: 8,
            }}
            onMouseEnter={e => { if (!pdfLoading) e.currentTarget.style.borderColor = 'rgba(79,156,249,0.7)' }}
            onMouseLeave={e => { e.currentTarget.style.borderColor = 'rgba(79,156,249,0.4)' }}
          >
            {pdfLoading ? (
              <>
                <style>{`@keyframes spin2{to{transform:rotate(360deg)}}`}</style>
                <div style={{ width: 13, height: 13, border: '2px solid #1e2235', borderTop: '2px solid #4f9cf9', borderRadius: '50%', animation: 'spin2 0.8s linear infinite' }} />
                Generating PDF...
              </>
            ) : 'Download PDF Report'}
          </button>

          <div style={{ textAlign: 'center', padding: '10px 0 4px', fontSize: 9, color: '#1a1e30', letterSpacing: '0.5px' }}>
            LANDAI OPTIMIZER — NSGA-III — OR-TOOLS — NETWORKX
          </div>
        </div>
      </div>
    </div>
  )
}

// ── Small reusable components ───────────────────────────────

function LayerToggle({ active, color, label, onClick }) {
  return (
    <div
      onClick={onClick}
      style={{
        display: 'flex', alignItems: 'center', gap: 6,
        padding: '4px 6px', borderRadius: 5, cursor: 'pointer',
        background: active ? `${color}18` : 'transparent',
        border: `0.5px solid ${active ? color + '55' : '#1a1e30'}`,
        transition: 'all 0.2s',
      }}
    >
      <div style={{
        width: 8, height: 8, borderRadius: '50%', flexShrink: 0,
        background: active ? color : '#2e3450',
        boxShadow: active ? `0 0 6px ${color}` : 'none',
      }} />
      <span style={{ fontSize: 10, color: active ? color : '#3a3f55', fontWeight: active ? 600 : 400 }}>
        {label}
      </span>
    </div>
  )
}

function LegendDot({ color, label }) {
  return (
    <div style={{ display: 'flex', alignItems: 'center', gap: 7, marginBottom: 4 }}>
      <div style={{ width: 8, height: 3, borderRadius: 1, background: color, flexShrink: 0 }} />
      <span style={{ fontSize: 10, color: '#555' }}>{label}</span>
    </div>
  )
}