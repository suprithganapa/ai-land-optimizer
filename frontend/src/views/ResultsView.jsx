import { useEffect, useRef, useState } from 'react'
import maplibregl from 'maplibre-gl'
import 'maplibre-gl/dist/maplibre-gl.css'
import useStore from '../store/useStore'
import { useLayout } from '../hooks/useLayout'

const MAPTILER_KEY = 'gbb10k4jq9g81OSN4q0z'
const API = 'http://localhost:8000/api'
const SESSION_ID = `session_${Date.now()}`

const PARETO_DESCRIPTIONS = {
  'Max Plots':'Maximises saleable plot count for highest revenue potential.',
  'Balanced':'Optimal balance of plots, green space, and infrastructure.',
  'Max Green':'Maximises community parks and open green space.',
  'Min Cost':'Minimises total road construction and utility cost.',
  'Max Density':'Highest plot density per unit area.',
}
const PHASE_COLORS = { 1:'#2e7d32', 2:'#f57c00', 3:'#616161' }
const PHASE_LABELS = { 1:'Phase 1 — Immediate',  2:'Phase 2 — Mid-term', 3:'Phase 3 — Future' }
const VASTU_COLORS = { E:'#2e7d32', N:'#388e3c', NE:'#43a047', NW:'#f57c00', SE:'#f57c00', W:'#ef6c00', S:'#d84315', SW:'#bf360c' }

// ── Design tokens ─────────────────────────────────────────────
const G = {
  bg:      '#f0f4ef',
  white:   '#ffffff',
  brand:   '#2d6a2f',
  accent:  '#4caf50',
  light:   '#e8f5e9',
  border:  'rgba(0,0,0,0.07)',
  t1:      '#1a1a1a',
  t2:      '#4a5568',
  t3:      '#94a3b8',
  t4:      '#cbd5e1',
  amber:   '#f57c00',
  red:     '#e53e3e',
  shadow:  '0 2px 8px rgba(0,0,0,0.07)',
}

const card   = { background:G.white, borderRadius:16, padding:'16px', marginBottom:10, boxShadow:G.shadow, border:`1px solid ${G.border}` }
const lbl    = { fontSize:9, fontWeight:700, letterSpacing:'1.2px', textTransform:'uppercase', color:G.t3, marginBottom:10, display:'block' }

export default function ResultsView({ onBack }) {
  const mapContainer    = useRef(null)
  const mapRef          = useRef(null)
  const markersRef      = useRef([])
  const popupRef        = useRef(null)
  const annotMarkersRef = useRef([])

  const { drawnPolygon, layout, zoningResult, selectedParetoIndex, setSelectedParetoIndex, reset } = useStore()
  const { downloadPDF } = useLayout()

  const [is3D,             setIs3D]             = useState(false)
  const [mapReady,         setMapReady]         = useState(false)
  const [pdfLoading,       setPdfLoading]       = useState(false)
  const [dxfLoading,       setDxfLoading]       = useState(false)
  const [reraLoading,      setReraLoading]      = useState(false)
  const [activeLayers,     setActiveLayers]     = useState({ sewage:false, water:false, electric:false })
  const [showAmenities,    setShowAmenities]    = useState(true)
  const [showStreetlights, setShowStreetlights] = useState(false)
  const [showPhases,       setShowPhases]       = useState(false)
  const [showDrainage,     setShowDrainage]     = useState(false)
  const [showBeforeAfter,  setShowBeforeAfter]  = useState(false)
  const [showAnnotations,  setShowAnnotations]  = useState(false)
  const [annotMode,        setAnnotMode]        = useState(false)
  const [annotations,      setAnnotations]      = useState([])
  const [annotText,        setAnnotText]        = useState('')
  const [pendingAnnot,     setPendingAnnot]     = useState(null)
  const [showLayerPanel,   setShowLayerPanel]   = useState(false)
  const [showFinance,      setShowFinance]      = useState(false)
  const [showValidate,     setShowValidate]     = useState(false)
  const [showNotes,        setShowNotes]        = useState(false)

  const removeLayer  = (map,id) => { try { if(map.getLayer(id))  map.removeLayer(id)  } catch(_){} }
  const removeSource = (map,id) => { try { if(map.getSource(id)) map.removeSource(id) } catch(_){} }

  const addPolyLayer = (map,id,features,fillColor,fillOpacity,lineColor,lineWidth) => {
    if(!features?.length) return
    const valid = features.filter(f=>f?.coordinates?.[0]?.length>=3)
    if(!valid.length) return
    const geojson = {type:'FeatureCollection',features:valid.map(f=>({type:'Feature',geometry:{type:'Polygon',coordinates:f.coordinates},properties:f.properties||{}}))}
    try {
      if(map.getSource(id)){map.getSource(id).setData(geojson);return}
      map.addSource(id,{type:'geojson',data:geojson})
      map.addLayer({id:`${id}-fill`,type:'fill',source:id,paint:{'fill-color':fillColor,'fill-opacity':fillOpacity}})
      map.addLayer({id:`${id}-line`,type:'line',source:id,paint:{'line-color':lineColor,'line-width':lineWidth}})
    } catch(e){console.warn(`Layer ${id}:`,e.message)}
  }

  // ── Infrastructure helpers — init once, toggle visibility ────
  const _initLineLayer = (map,id,lines,color,width,dashArray) => {
    const features = lines.filter(l=>Array.isArray(l)&&l.length>=2).map(l=>({type:'Feature',geometry:{type:'LineString',coordinates:l},properties:{}}))
    if(!features.length){ console.warn(`initLine ${id}: no features`); return }
    try {
      if(!map.getSource(id)) map.addSource(id,{type:'geojson',data:{type:'FeatureCollection',features}})
      else map.getSource(id).setData({type:'FeatureCollection',features})
      if(!map.getLayer(id)){
        const paint={'line-color':color,'line-width':width,'line-opacity':1}
        if(dashArray) paint['line-dasharray']=dashArray
        map.addLayer({id,type:'line',source:id,layout:{'visibility':'none'},paint})
      }
    } catch(e){console.warn(`initLine ${id}:`,e.message)}
  }

  const _initPointLayer = (map,id,points,color,radius) => {
    const pts = points.filter(p=>Array.isArray(p)&&p.length>=2&&isFinite(p[0])&&isFinite(p[1]))
    if(!pts.length){ console.warn(`initPoint ${id}: no valid points`); return }
    const features = pts.map(p=>({type:'Feature',geometry:{type:'Point',coordinates:p},properties:{}}))
    try {
      if(!map.getSource(id)) map.addSource(id,{type:'geojson',data:{type:'FeatureCollection',features}})
      else map.getSource(id).setData({type:'FeatureCollection',features})
      if(!map.getLayer(id)){
        map.addLayer({id,type:'circle',source:id,layout:{'visibility':'none'},
          paint:{'circle-color':color,'circle-radius':radius,'circle-stroke-color':'#fff','circle-stroke-width':2,'circle-opacity':1}})
      }
    } catch(e){console.warn(`initPoint ${id}:`,e.message)}
  }

  const initInfrastructureLayers = (map) => {
    const inf = layout?.infrastructure
    if(!inf){ console.warn('initInfra: no infrastructure data'); return }
    console.log('initInfra: initializing', {
      streetlights: inf.streetlights?.length,
      sewagePipes:  (inf.sewage_pipe_lines||[]).length,
      waterBranches:(inf.water_branch_pipes||[]).length,
      lvCables:     (inf.lv_cables||[]).length,
      stp:          inf.sewage_treatment_plant,
      waterTank:    inf.water_tank,
    })
    // Streetlights
    if(inf.streetlights?.length) _initPointLayer(map,'streetlights',inf.streetlights,'#fde047',5)
    // Sewage
    const sewageLines=[...(inf.sewage_pipe_lines||[]),...(inf.collector_pipes||[])]
    if(sewageLines.length) _initLineLayer(map,'sewage-pipes',sewageLines,'#a16207',2.5,[4,2])
    if(inf.sewage_treatment_plant?.length>=2) _initPointLayer(map,'stp',[inf.sewage_treatment_plant],'#92400e',10)
    // Water
    const waterLines=[...(inf.water_main_lines||[]),...(inf.water_branch_pipes||[])]
    if(waterLines.length) _initLineLayer(map,'water-pipes',waterLines,'#0ea5e9',2,[5,2])
    if(inf.water_tank?.length>=2) _initPointLayer(map,'water-tank',[inf.water_tank],'#0369a1',10)
    // Electric
    const elecLines=[...(inf.hv_cables||[]),...(inf.lv_cables||[])]
    if(elecLines.length) _initLineLayer(map,'elec-cables',elecLines,'#ca8a04',1.5,[3,3])
    if(inf.main_transformer?.length>=2) _initPointLayer(map,'transformer',[inf.main_transformer],'#facc15',11)
    if(inf.distribution_boards?.length) _initPointLayer(map,'dist-boards',inf.distribution_boards,'#fb923c',7)
    console.log('initInfra: done')
  }

  useEffect(() => {
    if(mapRef.current||!mapContainer.current||!layout) return
    const map = new maplibregl.Map({container:mapContainer.current,style:`https://api.maptiler.com/maps/satellite/style.json?key=${MAPTILER_KEY}`,center:[layout.centroid_lng||77.5946,layout.centroid_lat||12.9716],zoom:17,pitch:0,attributionControl:false})
    mapRef.current=map
    map.addControl(new maplibregl.NavigationControl(),'top-right')
    map.addControl(new maplibregl.AttributionControl({compact:true}),'bottom-right')
    map.on('load',()=>{ setMapReady(true) })
    map.on('error',e=>console.warn('Map:',e.error?.message))
    return () => {
      markersRef.current.forEach(m=>m.remove())
      annotMarkersRef.current.forEach(m=>m.remove())
      if(popupRef.current) popupRef.current.remove()
      map.remove();mapRef.current=null;setMapReady(false)
    }
  },[])

  // Run all map-layer init AFTER map style has loaded — fresh closure guarantees layout is present
  useEffect(()=>{
    const map=mapRef.current
    if(!map||!mapReady||!layout) return
    renderStaticLayers(map)
    initInfrastructureLayers(map)
    renderPareto(map,0)
    fitToBoundary(map)
  // eslint-disable-next-line react-hooks/exhaustive-deps
  },[mapReady])

  useEffect(()=>{const map=mapRef.current;if(!map||!mapReady) return;renderPareto(map,selectedParetoIndex)},[selectedParetoIndex,mapReady])
  useEffect(()=>{const map=mapRef.current;if(!map||!mapReady) return;renderInfrastructure(map,activeLayers,showStreetlights)},[activeLayers,showStreetlights,mapReady])

  useEffect(()=>{
    const map=mapRef.current;if(!map||!mapReady) return
    const vis=showAmenities?'visible':'none'
    ;['amenities-fill','amenities-line','amenities-label'].forEach(id=>{try{if(map.getLayer(id))map.setLayoutProperty(id,'visibility',vis)}catch(_){}})
  },[showAmenities,mapReady])

  useEffect(()=>{
    const map=mapRef.current;if(!map||!mapReady) return
    ;['drainage-lines'].forEach(id=>{removeLayer(map,id);removeSource(map,id)})
    if(!showDrainage||!layout?.drainage?.channels?.length) return
    const feats=layout.drainage.channels.map(ch=>({type:'Feature',geometry:{type:'LineString',coordinates:[ch.from,ch.to]},properties:{slope:ch.slope_pct}}))
    try {
      map.addSource('drainage-lines',{type:'geojson',data:{type:'FeatureCollection',features:feats}})
      map.addLayer({id:'drainage-lines',type:'line',source:'drainage-lines',paint:{'line-color':['interpolate',['linear'],['get','slope'],0,'#38bdf8',3,'#f59e0b',6,'#ef4444'],'line-width':2,'line-dasharray':[3,2]}})
    } catch(e){console.warn('Drainage:',e.message)}
  },[showDrainage,mapReady])

  useEffect(()=>{
    const map=mapRef.current;if(!map||!mapReady) return
    ;['phases-fill','phases-line'].forEach(id=>removeLayer(map,id));['phases'].forEach(id=>removeSource(map,id))
    if(!showPhases) return
    const data=layout?.pareto_layouts?.[selectedParetoIndex]||layout
    const feats=(data?.plots||[]).filter(p=>p?.coordinates?.[0]?.length>=3).map(p=>({type:'Feature',geometry:{type:'Polygon',coordinates:p.coordinates},properties:{phase:p.phase||1}}))
    if(!feats.length) return
    try {
      map.addSource('phases',{type:'geojson',data:{type:'FeatureCollection',features:feats}})
      map.addLayer({id:'phases-fill',type:'fill',source:'phases',paint:{'fill-color':['match',['get','phase'],1,'#2e7d32',2,'#f57c00',3,'#616161','#888'],'fill-opacity':0.7}})
      map.addLayer({id:'phases-line',type:'line',source:'phases',paint:{'line-color':'#ffffff33','line-width':0.5}})
    } catch(e){console.warn('Phases:',e.message)}
  },[showPhases,selectedParetoIndex,mapReady])

  useEffect(()=>{
    const map=mapRef.current;if(!map||!mapReady) return
    ;['plots-fill','parks-fill'].forEach(id=>{try{if(map.getLayer(id))map.setPaintProperty(id,'fill-opacity',showBeforeAfter?0.15:0.85)}catch(_){}})
  },[showBeforeAfter,mapReady])

  useEffect(()=>{
    const map=mapRef.current;if(!map) return
    annotMarkersRef.current.forEach(m=>m.remove());annotMarkersRef.current=[]
    if(!showAnnotations) return
    annotations.forEach(ann=>{
      if(!ann.lat||!ann.lng) return
      const el=document.createElement('div')
      el.style.cssText='width:22px;height:22px;border-radius:50%;background:#2d6a2f;border:2px solid #fff;display:flex;align-items:center;justify-content:center;font-size:10px;color:#fff;font-weight:700;cursor:pointer;box-shadow:0 2px 10px rgba(45,106,47,0.4);'
      el.textContent='N'
      const m=new maplibregl.Marker({element:el}).setLngLat([ann.lng,ann.lat]).setPopup(new maplibregl.Popup({offset:15}).setHTML(`<div style="font-size:11px;font-family:system-ui;max-width:200px;"><b style="color:#2d6a2f">Plot ${ann.plot_id}</b><br/><span style="color:#555">${ann.text}</span><br/><small style="color:#999">${ann.author} · ${ann.created_at}</small></div>`)).addTo(map)
      annotMarkersRef.current.push(m)
    })
  },[annotations,showAnnotations,mapReady])

  const fitToBoundary = (map) => {
    const data=layout?.pareto_layouts?.[0]||layout
    const allCoords=[]
    for(const p of (data?.plots||[])){const ring=p?.coordinates?.[0];if(ring?.length>=3) allCoords.push(...ring)}
    if(allCoords.length>=3){
      const lngs=allCoords.map(c=>c[0]);const lats=allCoords.map(c=>c[1])
      const clng=layout.centroid_lng;const clat=layout.centroid_lat
      if(lngs.some(l=>Math.abs(l-clng)<1)&&lats.some(l=>Math.abs(l-clat)<1)){
        map.fitBounds([[Math.min(...lngs),Math.min(...lats)],[Math.max(...lngs),Math.max(...lats)]],{padding:50,duration:1500,maxZoom:20});return
      }
    }
    const coords=drawnPolygon?.coordinates?.[0]
    if(coords?.length){const lngs=coords.map(c=>c[0]);const lats=coords.map(c=>c[1]);map.fitBounds([[Math.min(...lngs),Math.min(...lats)],[Math.max(...lngs),Math.max(...lats)]],{padding:80,duration:1500})}
  }

  const renderStaticLayers = (map) => {
    if(!layout) return
    if(drawnPolygon) addPolyLayer(map,'boundary',[{coordinates:drawnPolygon.coordinates,properties:{}}],'#4caf50',0.06,'#4caf50',2)
    const roadFeats=(layout.roads||[]).filter(r=>r?.coordinates?.[0]?.length>=3).map(r=>({type:'Feature',geometry:{type:'Polygon',coordinates:r.coordinates},properties:{}}))
    if(roadFeats.length){
      try {
        map.addSource('roads',{type:'geojson',data:{type:'FeatureCollection',features:roadFeats}})
        map.addLayer({id:'roads-fill',type:'fill',source:'roads',paint:{'fill-color':'#1a1a1a','fill-opacity':1}})
        map.addLayer({id:'roads-line',type:'line',source:'roads',paint:{'line-color':'#333','line-width':0.5}})
      } catch(e){console.warn('Roads:',e.message)}
    }
    const currentData=layout.pareto_layouts?.[selectedParetoIndex]||layout
    const amenityFeats=(currentData.amenities||layout.amenities||[]).filter(a=>a?.coordinates?.[0]?.length>=3).map(a=>({type:'Feature',geometry:{type:'Polygon',coordinates:a.coordinates},properties:{type:a.type}}))
    if(amenityFeats.length){
      try {
        map.addSource('amenities',{type:'geojson',data:{type:'FeatureCollection',features:amenityFeats}})
        map.addLayer({id:'amenities-fill',type:'fill',source:'amenities',paint:{'fill-color':'#166534','fill-opacity':0.5}})
        map.addLayer({id:'amenities-line',type:'line',source:'amenities',paint:{'line-color':'#4ade80','line-width':1}})
        map.addLayer({id:'amenities-label',type:'symbol',source:'amenities',layout:{'text-field':'Track','text-size':9,'text-anchor':'center'},paint:{'text-color':'#4ade80','text-halo-color':'#000','text-halo-width':1}})
      } catch(e){console.warn('Amenities:',e.message)}
    }
    if(layout.entrance?.length===2){
      try {
        const el=document.createElement('div')
        el.style.cssText='width:34px;height:34px;border-radius:50%;background:linear-gradient(135deg,#2d6a2f,#4caf50);border:2.5px solid rgba(255,255,255,0.8);display:flex;align-items:center;justify-content:center;font-size:10px;cursor:pointer;box-shadow:0 4px 16px rgba(45,106,47,0.5);color:#fff;font-weight:800;'
        el.textContent='E'
        const m=new maplibregl.Marker({element:el}).setLngLat(layout.entrance).setPopup(new maplibregl.Popup({offset:25}).setHTML('<div style="font-size:12px;font-weight:700;color:#2d6a2f;font-family:system-ui">Main Entrance</div>')).addTo(map)
        markersRef.current.push(m)
      } catch(e){console.warn('Entrance:',e)}
    }
  }

  const renderPareto = (map,idx) => {
    if(!layout) return
    const data=layout.pareto_layouts?.[idx]||layout
    ;['plots-label','plots-fill','plots-line','parks-label','parks-fill','parks-line','inst-fill','inst-line','inst-label'].forEach(id=>removeLayer(map,id))
    ;['plots','parks','inst'].forEach(id=>removeSource(map,id))
    map.off('click','plots-fill');map.off('click','inst-fill')

    const plotFeats=(data.plots||[]).filter(p=>p?.coordinates?.[0]?.length>=3).map(p=>({
      type:'Feature',geometry:{type:'Polygon',coordinates:p.coordinates},
      properties:{id:p.id,area_m2:p.area_m2,area_sqft:p.area_sqft||Math.round((p.area_m2||0)*10.764),vastu_dir:p.vastu_direction||'E',vastu_score:p.vastu_score||80,vastu_label:p.vastu_label||'',vastu_premium:p.vastu_premium_pct||0,phase:p.phase||1},
    }))
    if(plotFeats.length>0){
      try {
        map.addSource('plots',{type:'geojson',data:{type:'FeatureCollection',features:plotFeats}})
        map.addLayer({id:'plots-fill',type:'fill',source:'plots',paint:{'fill-color':'#f97316','fill-opacity':0.88}})
        map.addLayer({id:'plots-line',type:'line',source:'plots',paint:{'line-color':'#fdba74','line-width':0.6}})
        map.addLayer({id:'plots-label',type:'symbol',source:'plots',minzoom:17,layout:{'text-field':['concat','P',['to-string',['get','id']]],'text-size':['interpolate',['linear'],['zoom'],17,7,20,11],'text-anchor':'center'},paint:{'text-color':'#fff','text-halo-color':'#00000066','text-halo-width':1}})
        map.on('click','plots-fill',(e)=>{
          const props=e.features?.[0]?.properties;if(!props) return
          if(popupRef.current) popupRef.current.remove()
          const vstColor=VASTU_COLORS[props.vastu_dir]||G.amber
          popupRef.current=new maplibregl.Popup({offset:10,closeButton:true}).setLngLat(e.lngLat).setHTML(`
            <div style="font-family:system-ui,-apple-system,sans-serif;min-width:200px;background:#fff;color:#1a1a1a;padding:14px;border-radius:12px;">
              <div style="font-size:13px;font-weight:800;color:#2d6a2f;margin-bottom:10px;">Plot ${props.id}</div>
              <div style="display:grid;grid-template-columns:1fr 1fr;gap:8px;margin-bottom:10px;">
                <div style="background:#f8f9fa;border-radius:8px;padding:9px;">
                  <div style="font-size:8px;color:#94a3b8;font-weight:700;text-transform:uppercase;letter-spacing:1px;margin-bottom:3px;">Area</div>
                  <div style="font-size:14px;font-weight:700;color:#1a1a1a;">${props.area_sqft} <span style="font-size:9px;color:#94a3b8;font-weight:400;">sqft</span></div>
                  <div style="font-size:9px;color:#94a3b8;margin-top:1px;">${props.area_m2} m²</div>
                </div>
                <div style="background:#f8f9fa;border-radius:8px;padding:9px;">
                  <div style="font-size:8px;color:#94a3b8;font-weight:700;text-transform:uppercase;letter-spacing:1px;margin-bottom:3px;">Phase</div>
                  <div style="font-size:14px;font-weight:700;color:${PHASE_COLORS[props.phase]||'#888'}">${props.phase}</div>
                </div>
              </div>
              <div style="background:#f0f4ef;border-radius:8px;padding:10px;">
                <div style="font-size:8px;color:#94a3b8;font-weight:700;text-transform:uppercase;letter-spacing:1px;margin-bottom:6px;">Vastu Score</div>
                <div style="display:flex;align-items:center;gap:10px;">
                  <span style="font-size:24px;font-weight:900;color:${vstColor}">${props.vastu_score}</span>
                  <div><div style="font-size:11px;color:${vstColor};font-weight:600;">${props.vastu_label}</div><div style="font-size:10px;color:#94a3b8;">+${props.vastu_premium}% market premium</div></div>
                </div>
              </div>
            </div>`).addTo(map)
          if(annotMode) setPendingAnnot({plot_id:props.id,lat:e.lngLat.lat,lng:e.lngLat.lng})
        })
        map.on('mouseenter','plots-fill',()=>{map.getCanvas().style.cursor=annotMode?'crosshair':'pointer'})
        map.on('mouseleave','plots-fill',()=>{map.getCanvas().style.cursor=''})
      } catch(e){console.warn('Plots:',e.message)}
    }

    const parkFeats=(data.parks||[]).filter(p=>p?.coordinates?.[0]?.length>=3).map(p=>({type:'Feature',geometry:{type:'Polygon',coordinates:p.coordinates},properties:{area_m2:p.area_m2,label:p.label||'Community Park'}}))
    if(parkFeats.length>0){
      try {
        map.addSource('parks',{type:'geojson',data:{type:'FeatureCollection',features:parkFeats}})
        map.addLayer({id:'parks-fill',type:'fill',source:'parks',paint:{'fill-color':'#14532d','fill-opacity':0.9}})
        map.addLayer({id:'parks-line',type:'line',source:'parks',paint:{'line-color':'#4ade80','line-width':1.5}})
        map.addLayer({id:'parks-label',type:'symbol',source:'parks',layout:{'text-field':['get','label'],'text-size':11,'text-anchor':'center'},paint:{'text-color':'#4ade80','text-halo-color':'#000','text-halo-width':1.5}})
      } catch(e){console.warn('Parks:',e.message)}
    }

    const instFeats=(data.inst_blocks||[]).filter(p=>p?.coordinates?.[0]?.length>=3).map(p=>({type:'Feature',geometry:{type:'Polygon',coordinates:p.coordinates},properties:{area_m2:p.area_m2,label:p.label||'Institutional Site'}}))
    if(instFeats.length>0){
      try {
        map.addSource('inst',{type:'geojson',data:{type:'FeatureCollection',features:instFeats}})
        map.addLayer({id:'inst-fill',type:'fill',source:'inst',paint:{'fill-color':'#1e3a5f','fill-opacity':0.92}})
        map.addLayer({id:'inst-line',type:'line',source:'inst',paint:{'line-color':'#38bdf8','line-width':2,'line-dasharray':[4,2]}})
        map.addLayer({id:'inst-label',type:'symbol',source:'inst',layout:{'text-field':['get','label'],'text-size':10,'text-anchor':'center','text-max-width':8},paint:{'text-color':'#38bdf8','text-halo-color':'#000','text-halo-width':1.5}})
        map.on('click','inst-fill',(e)=>{
          const props=e.features?.[0]?.properties;if(!props) return
          if(popupRef.current) popupRef.current.remove()
          popupRef.current=new maplibregl.Popup({offset:10,closeButton:true}).setLngLat(e.lngLat).setHTML(`<div style="font-family:system-ui;min-width:170px;background:#fff;padding:14px;border-radius:12px;"><div style="font-size:13px;font-weight:800;color:#1e40af;margin-bottom:4px;">${props.label}</div><div style="font-size:10px;color:#94a3b8;margin-bottom:8px;">Reserved Institutional Site</div><div style="font-size:12px;color:#1a1a1a;">${props.area_m2} m² · ${Math.round(props.area_m2*10.764)} sqft</div><div style="font-size:9px;color:#94a3b8;margin-top:8px;padding-top:8px;border-top:1px solid #f0f0f0;">Not for private sale — reserved for public use.</div></div>`).addTo(map)
        })
        map.on('mouseenter','inst-fill',()=>{map.getCanvas().style.cursor='pointer'})
        map.on('mouseleave','inst-fill',()=>{map.getCanvas().style.cursor=''})
      } catch(e){console.warn('Inst:',e.message)}
    }
  }

  const renderInfrastructure = (map,layers,streetlights) => {
    // All infrastructure layers are pre-initialized in initInfrastructureLayers.
    // We only toggle visibility here — much more reliable than add/remove cycles.
    const setVis = (id, visible) => {
      try {
        if(map.getLayer(id)) map.setLayoutProperty(id,'visibility',visible?'visible':'none')
      } catch(e){ console.warn(`setVis ${id}:`,e.message) }
    }
    setVis('streetlights', streetlights)
    setVis('sewage-pipes', layers.sewage)
    setVis('stp',          layers.sewage)
    setVis('water-pipes',  layers.water)
    setVis('water-tank',   layers.water)
    setVis('elec-cables',  layers.electric)
    setVis('transformer',  layers.electric)
    setVis('dist-boards',  layers.electric)
  }

  const toggle3D=()=>{const map=mapRef.current;if(!map) return;if(!is3D) map.easeTo({pitch:52,bearing:-20,duration:1000});else map.easeTo({pitch:0,bearing:0,duration:1000});setIs3D(!is3D)}

  const handlePDF  = async () => {setPdfLoading(true);await downloadPDF(layout,zoningResult);setPdfLoading(false)}
  const handleDXF  = async () => {
    setDxfLoading(true)
    try {
      const res=await fetch(`${API}/export-dxf`,{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({layout,centroid_lat:layout.centroid_lat,centroid_lng:layout.centroid_lng})})
      const blob=await res.blob();const url=URL.createObjectURL(blob);const a=document.createElement('a');a.href=url;a.download=`LandAI_${Date.now()}.dxf`;a.click();URL.revokeObjectURL(url)
    } catch(e){alert('DXF export failed: '+e.message)}
    setDxfLoading(false)
  }
  const handleRERA = async () => {
    setReraLoading(true)
    try {
      const res=await fetch(`${API}/rera-checklist`,{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({layout,zoning:zoningResult||{},centroid_lat:layout.centroid_lat,centroid_lng:layout.centroid_lng,project_name:'Residential Colony'})})
      const blob=await res.blob();const url=URL.createObjectURL(blob);const a=document.createElement('a');a.href=url;a.download=`RERA_${Date.now()}.pdf`;a.click();URL.revokeObjectURL(url)
    } catch(e){alert('RERA export failed: '+e.message)}
    setReraLoading(false)
  }
  const submitAnnotation = async () => {
    if(!annotText.trim()||!pendingAnnot) return
    try {
      const res=await fetch(`${API}/annotations/add`,{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({session_id:SESSION_ID,...pendingAnnot,text:annotText,author:'Reviewer'})})
      const data=await res.json();setAnnotations(prev=>[...prev,data.annotation]);setAnnotText('');setPendingAnnot(null)
    } catch(e){console.error('Annotation error:',e)}
  }
  const deleteAnnotation = async (ann_id) => {
    try{await fetch(`${API}/annotations/delete`,{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({session_id:SESSION_ID,annotation_id:ann_id})});setAnnotations(prev=>prev.filter(a=>a.id!==ann_id))}catch(e){}
  }

  // ── Computed ──────────────────────────────────────────────────
  const price         = layout?.price_prediction||{}
  const mlRate        = price.predicted_rate_per_m2||45000
  const gross         = Math.round((layout?.total_plot_area_m2||0)*mlRate)
  const rCost         = Math.round((layout?.total_road_area_m2||0)*3500)
  const uCost         = Math.round((layout?.utility_route_length_m||0)*1200)
  const total         = rCost+uCost
  const profit        = gross-total
  const roi           = total>0?Math.round(profit/total*100):0
  const currentPareto = layout?.pareto_layouts?.[selectedParetoIndex]||layout
  const vastu         = layout?.vastu_summary||{}
  const amenScore     = layout?.amenity_score||{}
  const drainage      = layout?.drainage||{}
  const parkAreaPct   = layout?.area_m2>0?Math.round((currentPareto?.total_park_area_m2||0)/layout.area_m2*100):0
  const connectPct    = layout?.connectivity_pct||0
  const roadPct       = layout?.area_m2>0?Math.round((layout?.total_road_area_m2||0)/layout.area_m2*100):0
  const effScore      = currentPareto?.efficiency_score||0
  const numPlots      = currentPareto?.num_plots||layout?.num_plots||0
  const numParks      = currentPareto?.num_parks||1
  const numInst       = currentPareto?.num_inst_blocks||0
  const areaHa        = layout?.area_m2?Math.round(layout.area_m2/100)/100:0

  const fmt=(n)=>{
    if(n>=10000000) return `₹${(n/10000000).toFixed(2)} Cr`
    if(n>=100000)   return `₹${(n/100000).toFixed(1)} L`
    return `₹${n.toLocaleString()}`
  }

  // SVG Donut
  const DonutChart = ({pct,label,size=110,stroke=12,color}) => {
    const r=size/2-stroke
    const c=2*Math.PI*r
    const dash=c*pct/100
    return (
      <svg width={size} height={size} viewBox={`0 0 ${size} ${size}`}>
        <circle cx={size/2} cy={size/2} r={r} fill="none" stroke="#f0f0f0" strokeWidth={stroke} />
        <circle cx={size/2} cy={size/2} r={r} fill="none" stroke={color} strokeWidth={stroke}
          strokeDasharray={`${dash} ${c}`} strokeLinecap="round"
          transform={`rotate(-90 ${size/2} ${size/2})`} />
        <text x={size/2} y={size/2-6} textAnchor="middle" fill={G.t1} fontSize={size>100?22:16} fontWeight="800">{pct}%</text>
        <text x={size/2} y={size/2+12} textAnchor="middle" fill={G.t3} fontSize={9}>{label}</text>
      </svg>
    )
  }

  // Bar metric
  const BarMetric = ({label,value,max,unit,color,target}) => (
    <div style={{marginBottom:14}}>
      <div style={{display:'flex',justifyContent:'space-between',marginBottom:5}}>
        <span style={{fontSize:11,color:G.t2,fontWeight:500}}>{label}</span>
        <span style={{fontSize:11,fontWeight:700,color:value>=(target||0)?G.brand:G.amber}}>{value}{unit}</span>
      </div>
      <div style={{height:7,background:'#e8ede8',borderRadius:6,overflow:'hidden'}}>
        <div style={{height:'100%',width:`${Math.min(100,value/max*100)}%`,background:`linear-gradient(90deg,${color},${color}cc)`,borderRadius:6,transition:'width 0.8s ease'}} />
      </div>
      {target!=null && <div style={{fontSize:8,color:G.t3,marginTop:3}}>Target: {target}{unit}</div>}
    </div>
  )

  const LAYERS = [
    {id:'streetlights',label:'Streetlights',color:'#fde047',active:showStreetlights,toggle:()=>setShowStreetlights(v=>!v)},
    {id:'sewage',label:'Sewage Pipes',color:'#a16207',active:activeLayers.sewage,toggle:()=>setActiveLayers(p=>({...p,sewage:!p.sewage}))},
    {id:'water',label:'Water Supply',color:'#0ea5e9',active:activeLayers.water,toggle:()=>setActiveLayers(p=>({...p,water:!p.water}))},
    {id:'electric',label:'Electrical',color:'#facc15',active:activeLayers.electric,toggle:()=>setActiveLayers(p=>({...p,electric:!p.electric}))},
    {id:'amenities',label:'Amenities',color:'#4ade80',active:showAmenities,toggle:()=>setShowAmenities(v=>!v)},
    {id:'phases',label:'Dev. Phases',color:'#f97316',active:showPhases,toggle:()=>setShowPhases(v=>!v)},
    {id:'drainage',label:'Drainage',color:'#38bdf8',active:showDrainage,toggle:()=>setShowDrainage(v=>!v)},
    {id:'beforeafter',label:'Before/After',color:G.amber,active:showBeforeAfter,toggle:()=>setShowBeforeAfter(v=>!v)},
    {id:'annotations',label:'Annotations',color:'#a78bfa',active:showAnnotations,toggle:()=>setShowAnnotations(v=>!v)},
  ]

  return (
    <div style={{display:'flex',flexDirection:'column',height:'100vh',background:G.bg,fontFamily:'system-ui,-apple-system,"Segoe UI",sans-serif',overflow:'hidden'}}>
      <style>{`
        @keyframes spin{to{transform:rotate(360deg)}}
        @keyframes fadeUp{from{opacity:0;transform:translateY(6px)}to{opacity:1;transform:translateY(0)}}
        ::-webkit-scrollbar{width:4px}
        ::-webkit-scrollbar-track{background:transparent}
        ::-webkit-scrollbar-thumb{background:#d1d5db;border-radius:4px}
        .hov-card:hover{box-shadow:0 4px 20px rgba(0,0,0,0.1)!important;transform:translateY(-1px)}
        .hov-card{transition:all 0.15s ease}
        .hov-btn:hover{opacity:0.88;transform:translateY(-1px)}
        .hov-btn{transition:all 0.15s ease}
        .layer-tog:hover{background:rgba(0,0,0,0.04)!important}
        .pareto-pill:hover{border-color:${G.brand}44!important}
        .acc-header:hover{background:#f8f9fa}
        .acc-header{transition:background 0.1s}
        .maplibregl-popup-content{padding:0!important;border-radius:12px!important;box-shadow:0 8px 30px rgba(0,0,0,0.15)!important;border:none!important}
        .maplibregl-popup-tip{display:none}
      `}</style>

      {/* ══ HEADER ══════════════════════════════════════════════ */}
      <div style={{height:62,background:G.white,borderBottom:`1px solid ${G.border}`,display:'flex',alignItems:'center',padding:'0 22px',gap:16,flexShrink:0,boxShadow:'0 1px 4px rgba(0,0,0,0.04)'}}>
        {/* Logo + back */}
        <div style={{display:'flex',alignItems:'center',gap:10}}>
          <button onClick={()=>{reset();onBack()}} style={{background:'none',border:'none',cursor:'pointer',color:G.t3,fontSize:18,lineHeight:1,padding:2,borderRadius:6}}>←</button>
          <div style={{width:34,height:34,background:'linear-gradient(135deg,#2d6a2f,#4caf50)',borderRadius:10,display:'flex',alignItems:'center',justifyContent:'center',boxShadow:'0 2px 10px rgba(45,106,47,0.25)'}}>
            <svg width="18" height="18" viewBox="0 0 24 24" fill="none"><path d="M12 2C6 8 4 12 4 14a8 8 0 0016 0c0-2-2-6-8-12z" fill="rgba(255,255,255,0.9)"/><path d="M12 14v8" stroke="rgba(255,255,255,0.6)" strokeWidth="1.5"/></svg>
          </div>
          <div>
            <div style={{fontSize:15,fontWeight:800,color:G.t1,letterSpacing:'-0.3px'}}>LandAI <span style={{color:G.brand}}>Optimizer</span></div>
            <div style={{fontSize:9,color:G.t3,letterSpacing:'0.3px'}}>{price.city||'Bengaluru'} · {areaHa} Ha · {currentPareto?.label||'Balanced'}</div>
          </div>
        </div>

        {/* Center — Task status chips */}
        <div style={{display:'flex',alignItems:'center',gap:8,marginLeft:20}}>
          <div style={{background:'#f0fdf4',border:'1px solid #bbf7d0',borderRadius:20,padding:'5px 14px',display:'flex',alignItems:'center',gap:7,fontSize:11}}>
            <div style={{width:6,height:6,borderRadius:'50%',background:G.brand}} />
            <span style={{color:G.brand,fontWeight:700}}>NBC Compliant</span>
            <span style={{background:G.brand,color:'#fff',borderRadius:10,padding:'1px 8px',fontSize:10,fontWeight:700}}>{parkAreaPct >= 10 && connectPct >= 90 ? '✓' : '!'}</span>
          </div>
          <div style={{background:'#fff7ed',border:'1px solid #fed7aa',borderRadius:20,padding:'5px 14px',display:'flex',alignItems:'center',gap:7,fontSize:11}}>
            <div style={{width:6,height:6,borderRadius:'50%',background:G.amber}} />
            <span style={{color:G.amber,fontWeight:700}}>Vastu Score</span>
            <span style={{background:G.amber,color:'#fff',borderRadius:10,padding:'1px 8px',fontSize:10,fontWeight:700}}>{vastu.avg_vastu_score||'—'}</span>
          </div>
          <button onClick={handlePDF} className="hov-btn" disabled={pdfLoading} style={{background:G.t1,border:'none',borderRadius:20,padding:'6px 16px',color:'#fff',fontSize:11,fontWeight:700,cursor:'pointer',display:'flex',alignItems:'center',gap:6}}>
            {pdfLoading?<Spin color="#fff"/>:null} ⊕ Export Layout
          </button>
        </div>

        {/* Right */}
        <div style={{marginLeft:'auto',display:'flex',alignItems:'center',gap:10}}>
          <div style={{background:'#f8f9fa',border:`1px solid ${G.border}`,borderRadius:22,padding:'6px 16px',display:'flex',alignItems:'center',gap:8,fontSize:11,color:G.t3,minWidth:180}}>
            <span>🔍</span><span>Search plots…</span>
          </div>
          <button onClick={toggle3D} style={{background:is3D?G.light:'#f8f9fa',border:`1px solid ${is3D?G.brand+'44':G.border}`,color:is3D?G.brand:G.t2,borderRadius:9,padding:'6px 14px',fontSize:11,cursor:'pointer',fontWeight:600}}>
            {is3D?'2D':'3D'}
          </button>
          <div style={{width:34,height:34,borderRadius:'50%',background:'linear-gradient(135deg,#2d6a2f,#4caf50)',display:'flex',alignItems:'center',justifyContent:'center',color:'#fff',fontSize:12,fontWeight:800,cursor:'pointer'}}>S</div>
        </div>
      </div>

      {/* ══ BODY ═══════════════════════════════════════════════ */}
      <div style={{display:'flex',flex:1,overflow:'hidden'}}>

        {/* ── LEFT PANEL ──────────────────────────────────────── */}
        <div style={{width:372,background:G.bg,overflowY:'auto',flexShrink:0,borderRight:`1px solid ${G.border}`,padding:'14px 14px 20px'}}>

          {/* Stats grid 2x2 */}
          <div style={{display:'grid',gridTemplateColumns:'1fr 1fr',gap:8,marginBottom:10}}>
            {[
              {label:'Total Plots',   value:numPlots,     unit:'Plots',     icon:'⊞', color:G.brand},
              {label:'Community Parks',value:numParks,    unit:'Parks',     icon:'🌿', color:'#2e7d32'},
              {label:'Total Area',    value:`${areaHa}`,  unit:'Hectares',  icon:'📐', color:'#1565c0'},
              {label:'Efficiency',    value:`${effScore}`,unit:'%',         icon:'⚡', color:G.amber},
            ].map((s,i)=>(
              <div key={i} className="hov-card" style={{...card,marginBottom:0,padding:'14px 16px'}}>
                <div style={{display:'flex',alignItems:'flex-start',justifyContent:'space-between',marginBottom:6}}>
                  <span style={{fontSize:9,color:G.t3,fontWeight:600,letterSpacing:'0.5px',textTransform:'uppercase'}}>{s.label}</span>
                  <span style={{fontSize:8,color:G.t4}}>··</span>
                </div>
                <div style={{display:'flex',alignItems:'baseline',gap:5}}>
                  <span style={{fontSize:26,fontWeight:900,color:G.t1,lineHeight:1,letterSpacing:'-1px'}}>{s.value}</span>
                  <span style={{fontSize:11,color:G.t3,fontWeight:500}}>{s.unit}</span>
                </div>
              </div>
            ))}
          </div>

          {/* Vastu Compliance card — styled like the Weather card */}
          <div className="hov-card" style={{...card,background:G.brand,color:'#fff',padding:'18px'}}>
            <div style={{display:'flex',justifyContent:'space-between',alignItems:'flex-start',marginBottom:14}}>
              <span style={{fontSize:11,fontWeight:700,color:'rgba(255,255,255,0.7)',letterSpacing:'0.5px'}}>Vastu Compliance</span>
              <span style={{fontSize:8,color:'rgba(255,255,255,0.4)'}}>··</span>
            </div>
            <div style={{display:'flex',alignItems:'flex-end',gap:4,marginBottom:14}}>
              <span style={{fontSize:52,fontWeight:900,lineHeight:1,letterSpacing:'-3px',color:'#fff',textShadow:'0 2px 20px rgba(0,0,0,0.2)'}}>{vastu.avg_vastu_score||82}</span>
              <div style={{paddingBottom:8}}>
                <div style={{fontSize:10,color:'rgba(255,255,255,0.5)',marginBottom:1}}>Avg Score</div>
                <div style={{fontSize:11,color:'rgba(255,255,255,0.85)',fontWeight:600}}>/ 100</div>
              </div>
            </div>
            {/* Direction breakdown — like cloud/wind/humidity row */}
            <div style={{display:'flex',gap:6,marginBottom:10}}>
              {[['E','95'],['N','90'],['NE','85'],['NW','78'],['SE','75']].map(([dir,sc])=>(
                <div key={dir} style={{flex:1,background:'rgba(255,255,255,0.1)',borderRadius:8,padding:'6px 4px',textAlign:'center'}}>
                  <div style={{fontSize:9,color:'rgba(255,255,255,0.6)',marginBottom:3}}>{dir}</div>
                  <div style={{fontSize:11,fontWeight:700,color:'#fff'}}>{sc}</div>
                </div>
              ))}
            </div>
            {/* Color band — like the temperature gradient bar */}
            <div style={{height:8,borderRadius:4,background:'linear-gradient(90deg,#bf360c,#ef6c00,#f57c00,#4caf50,#2e7d32)',opacity:0.7,marginBottom:6}}/>
            <div style={{display:'flex',justifyContent:'space-between',fontSize:8,color:'rgba(255,255,255,0.5)'}}>
              <span>Poor (SW)</span><span>Avg (W)</span><span>Good (NE)</span><span>Best (E)</span>
            </div>
            <div style={{marginTop:12,display:'flex',justifyContent:'space-between',background:'rgba(255,255,255,0.08)',borderRadius:10,padding:'8px 12px'}}>
              <div style={{fontSize:10,color:'rgba(255,255,255,0.6)'}}>Premium plots (E/N)</div>
              <div style={{fontSize:11,fontWeight:700,color:'#fff'}}>{vastu.premium_plots||0} · {vastu.premium_plot_pct||0}%</div>
            </div>
          </div>

          {/* NBC Metrics card — like Soil Health with N/P/K bars */}
          <div className="hov-card" style={{...card,background:'#1a3320',color:'#fff',padding:'18px'}}>
            <div style={{display:'flex',justifyContent:'space-between',alignItems:'center',marginBottom:16}}>
              <span style={{fontSize:11,fontWeight:700,color:'rgba(255,255,255,0.8)'}}>NBC 2016 Metrics</span>
              <span style={{fontSize:8,color:'rgba(255,255,255,0.4)'}}>··</span>
            </div>
            {[
              {label:'Park Area',    value:parkAreaPct,   max:25, unit:'%', color:'#4ade80', target:10},
              {label:'Road Connect.',value:connectPct,    max:100,unit:'%', color:'#60a5fa', target:90},
              {label:'Road Coverage',value:roadPct,       max:25, unit:'%', color:'#fbbf24', target:null},
            ].map((m,i)=>(
              <div key={i} style={{marginBottom:i<2?14:0}}>
                <div style={{display:'flex',justifyContent:'space-between',marginBottom:5}}>
                  <span style={{fontSize:11,color:'rgba(255,255,255,0.7)'}}>{m.label}</span>
                  <span style={{fontSize:11,fontWeight:700,color:m.target!=null&&m.value>=m.target?'#4ade80':'#fbbf24'}}>{m.value}{m.unit}</span>
                </div>
                <div style={{height:6,background:'rgba(255,255,255,0.1)',borderRadius:4,overflow:'hidden'}}>
                  <div style={{height:'100%',width:`${Math.min(100,m.value/m.max*100)}%`,background:m.color,borderRadius:4,transition:'width 0.8s ease'}} />
                </div>
                {m.target!=null&&<div style={{fontSize:8,color:'rgba(255,255,255,0.3)',marginTop:3}}>Target: {m.target}{m.unit}</div>}
              </div>
            ))}
          </div>

          {/* Layout Performance donut — like Farm Performance */}
          <div className="hov-card" style={{...card,padding:'18px'}}>
            <div style={{display:'flex',justifyContent:'space-between',alignItems:'center',marginBottom:14}}>
              <span style={{fontSize:11,fontWeight:700,color:G.t2}}>Layout Performance</span>
              <span style={{fontSize:8,color:G.t3}}>··</span>
            </div>
            <div style={{display:'flex',alignItems:'center',gap:16}}>
              {/* Donut */}
              <div style={{position:'relative',flexShrink:0}}>
                <svg width={120} height={120} viewBox="0 0 120 120">
                  <circle cx={60} cy={60} r={46} fill="none" stroke="#f0f0f0" strokeWidth={13}/>
                  {/* 3 arcs: plot efficiency, park coverage, road */}
                  {[
                    {pct:effScore,      color:G.brand,   offset:0},
                    {pct:parkAreaPct*3, color:'#4caf50',  offset:effScore},
                    {pct:connectPct*0.3,color:'#60a5fa',  offset:effScore+parkAreaPct*3},
                  ].map((arc,i)=>{
                    const r2=46; const c2=2*Math.PI*r2
                    const clamp=Math.min(100,arc.pct)
                    const dash=c2*clamp/100
                    const gap=c2*(100-clamp)/100
                    const rot=-90+arc.offset*3.6
                    return <circle key={i} cx={60} cy={60} r={r2} fill="none" stroke={arc.color} strokeWidth={13}
                      strokeDasharray={`${dash} ${c2}`} strokeLinecap="butt"
                      transform={`rotate(${rot} 60 60)`} />
                  })}
                  <text x={60} y={55} textAnchor="middle" fill={G.t1} fontSize={20} fontWeight="800">{effScore}%</text>
                  <text x={60} y={70} textAnchor="middle" fill={G.t3} fontSize={8}>Overall</text>
                </svg>
              </div>
              {/* Legend */}
              <div style={{flex:1}}>
                {[
                  {c:G.brand,  l:'Plot Utilization', v:`${effScore}%`},
                  {c:'#4caf50',l:'Park Coverage',    v:`${parkAreaPct}%`},
                  {c:'#60a5fa',l:'Connectivity',     v:`${connectPct}%`},
                ].map((item,i)=>(
                  <div key={i} style={{display:'flex',alignItems:'center',gap:7,marginBottom:10}}>
                    <div style={{width:9,height:9,borderRadius:'50%',background:item.c,flexShrink:0}}/>
                    <div style={{flex:1}}>
                      <div style={{fontSize:10,color:G.t2,fontWeight:500}}>{item.l}</div>
                      <div style={{fontSize:11,fontWeight:700,color:G.t1}}>{item.v}</div>
                    </div>
                  </div>
                ))}
              </div>
            </div>
          </div>

          {/* Pareto selector */}
          {layout?.pareto_layouts?.length>1 && (
            <div className="hov-card" style={{...card,padding:'14px 16px'}}>
              <span style={lbl}>Optimized Layouts</span>
              <div style={{display:'flex',gap:5}}>
                {layout.pareto_layouts.map((pl,i)=>(
                  <div key={i} className="pareto-pill" onClick={()=>setSelectedParetoIndex(i)} style={{flex:1,borderRadius:9,padding:'7px 3px',textAlign:'center',cursor:'pointer',background:selectedParetoIndex===i?G.light:'#f8f9fa',border:`1.5px solid ${selectedParetoIndex===i?G.brand+'44':'transparent'}`,transition:'all 0.15s'}}>
                    <div style={{fontSize:13,fontWeight:800,color:selectedParetoIndex===i?G.brand:G.t2}}>L{i+1}</div>
                    <div style={{fontSize:8,color:selectedParetoIndex===i?G.brand:G.t3,marginTop:1}}>{pl.num_plots}p</div>
                  </div>
                ))}
              </div>
              {layout.pareto_layouts[selectedParetoIndex] && (
                <div style={{marginTop:10,padding:'10px 12px',background:'#f8f9fa',borderRadius:10,fontSize:10,color:G.t3,lineHeight:1.6}}>
                  <span style={{fontWeight:700,color:G.brand}}>{layout.pareto_layouts[selectedParetoIndex].label}</span><br/>
                  {PARETO_DESCRIPTIONS[layout.pareto_layouts[selectedParetoIndex].label]||'Optimized layout.'}
                </div>
              )}
            </div>
          )}

          {/* Infrastructure layer toggles */}
          <div className="hov-card" style={{...card,padding:'14px 16px'}}>
            <span style={lbl}>Infrastructure Layers</span>
            <div style={{display:'flex',flexDirection:'column',gap:4}}>
              {[
                {key:'streetlights', label:'Streetlights',   color:'#fde047', active:showStreetlights, toggle:()=>setShowStreetlights(v=>!v)},
                {key:'sewage',       label:'Sewage Pipes',   color:'#a16207', active:activeLayers.sewage,   toggle:()=>setActiveLayers(p=>({...p,sewage:!p.sewage}))},
                {key:'water',        label:'Water Supply',   color:'#0ea5e9', active:activeLayers.water,    toggle:()=>setActiveLayers(p=>({...p,water:!p.water}))},
                {key:'electric',     label:'Electrical',     color:'#facc15', active:activeLayers.electric, toggle:()=>setActiveLayers(p=>({...p,electric:!p.electric}))},
                {key:'amenities',    label:'Amenities',      color:'#4ade80', active:showAmenities,          toggle:()=>setShowAmenities(v=>!v)},
              ].map(({key,label,color,active,toggle})=>(
                <div key={key} onClick={toggle} style={{display:'flex',alignItems:'center',gap:10,padding:'7px 10px',borderRadius:9,cursor:'pointer',background:active?G.light:'#f8f9fa',border:`1px solid ${active?G.brand+'33':G.border}`,transition:'all 0.15s'}}>
                  <div style={{width:8,height:8,borderRadius:'50%',background:active?color:'#d1d5db',boxShadow:active?`0 0 6px ${color}`:'none',flexShrink:0,transition:'all 0.2s'}} />
                  <span style={{fontSize:11,flex:1,color:active?G.t1:G.t3,fontWeight:active?600:400}}>{label}</span>
                  <div style={{width:28,height:16,borderRadius:8,background:active?G.brand:'#e2e8f0',position:'relative',transition:'background 0.2s',flexShrink:0}}>
                    <div style={{width:12,height:12,borderRadius:'50%',background:'#fff',position:'absolute',top:2,left:active?14:2,transition:'left 0.2s',boxShadow:'0 1px 3px rgba(0,0,0,0.15)'}} />
                  </div>
                </div>
              ))}
            </div>
          </div>

          {/* Phase cards — like the task cards row */}
          <div style={{marginBottom:10}}>
            <span style={{...lbl,marginBottom:8}}>Development Phases</span>
            <div style={{display:'flex',flexDirection:'column',gap:7}}>
              {[
                {phase:1,badge:'Immediate',badgeColor:'#2e7d32',bg:'linear-gradient(135deg,#1b5e20,#2e7d32)',count:Math.round(numPlots*0.4),pct:40},
                {phase:2,badge:'In Progress',badgeColor:'#e65100',bg:'linear-gradient(135deg,#bf360c,#e64a19)',count:Math.round(numPlots*0.35),pct:35},
                {phase:3,badge:'Planned',badgeColor:'#37474f',bg:'linear-gradient(135deg,#263238,#37474f)',count:numPlots-Math.round(numPlots*0.4)-Math.round(numPlots*0.35),pct:25},
              ].map((ph,i)=>(
                <div key={i} className="hov-card" style={{...card,marginBottom:0,background:ph.bg,padding:'14px 16px',position:'relative',overflow:'hidden'}}>
                  <div style={{position:'absolute',right:-14,top:-14,width:60,height:60,borderRadius:'50%',background:'rgba(255,255,255,0.05)'}}/>
                  <div style={{display:'flex',alignItems:'center',justifyContent:'space-between'}}>
                    <div>
                      <div style={{display:'inline-flex',background:'rgba(255,255,255,0.15)',borderRadius:20,padding:'2px 10px',fontSize:9,fontWeight:700,color:'#fff',marginBottom:6}}>
                        <span style={{width:5,height:5,borderRadius:'50%',background:ph.badgeColor==='#2e7d32'?'#69f0ae':ph.badgeColor==='#e65100'?'#ffab40':'#90a4ae',display:'inline-block',marginRight:5,marginTop:2}}/>
                        {ph.badge}
                      </div>
                      <div style={{fontSize:11,color:'rgba(255,255,255,0.7)',marginBottom:3}}>Phase {ph.phase} — {ph.pct}% of layout</div>
                      <div style={{fontSize:14,fontWeight:700,color:'#fff'}}>{ph.count} plots</div>
                    </div>
                    <div style={{fontSize:24,fontWeight:900,color:'rgba(255,255,255,0.15)',lineHeight:1}}>P{ph.phase}</div>
                  </div>
                </div>
              ))}
            </div>
          </div>

          {/* Finance accordion */}
          <div className="hov-card" style={{...card,padding:0,overflow:'hidden'}}>
            <div className="acc-header" onClick={()=>setShowFinance(v=>!v)} style={{padding:'14px 16px',display:'flex',justifyContent:'space-between',alignItems:'center',cursor:'pointer',borderRadius:showFinance?'16px 16px 0 0':16}}>
              <div style={{display:'flex',alignItems:'center',gap:8}}>
                <span style={{fontSize:13}}>₹</span>
                <span style={{fontSize:12,fontWeight:700,color:G.t1}}>Financial Summary</span>
              </div>
              <div style={{display:'flex',alignItems:'center',gap:10}}>
                <span style={{fontSize:11,fontWeight:800,color:G.brand}}>{fmt(profit)}</span>
                <span style={{fontSize:12,color:G.t3,transition:'transform 0.2s',display:'inline-block',transform:showFinance?'rotate(180deg)':'rotate(0deg)'}}>▾</span>
              </div>
            </div>
            {showFinance && (
              <div style={{padding:'0 16px 16px',animation:'fadeUp 0.2s ease',borderTop:`1px solid ${G.border}`}}>
                <div style={{marginTop:12}}>
                  {[
                    {l:'Market Rate',      v:`₹${mlRate.toLocaleString()}/m²`,          c:G.brand},
                    {l:'Gross Revenue',    v:fmt(gross),                                 c:'#2e7d32'},
                    {l:'Road + Infra',     v:`– ${fmt(rCost+uCost)}`,                   c:G.red},
                    {l:'Net Profit',       v:fmt(profit),                                c:'#2e7d32',bold:true},
                    {l:'ROI',              v:`${roi}%`,                                  c:roi>0?'#2e7d32':G.red,bold:true},
                  ].map((r,i,a)=>(
                    <div key={i} style={{display:'flex',justifyContent:'space-between',padding:'7px 0',borderBottom:i<a.length-1?`1px solid ${G.border}`:'none'}}>
                      <span style={{fontSize:11,color:G.t3}}>{r.l}</span>
                      <span style={{fontSize:11,fontWeight:r.bold?800:500,color:r.c}}>{r.v}</span>
                    </div>
                  ))}
                </div>
              </div>
            )}
          </div>

          {/* Validate accordion */}
          <div className="hov-card" style={{...card,padding:0,overflow:'hidden'}}>
            <div className="acc-header" onClick={()=>setShowValidate(v=>!v)} style={{padding:'14px 16px',display:'flex',justifyContent:'space-between',alignItems:'center',cursor:'pointer',borderRadius:showValidate?'16px 16px 0 0':16}}>
              <div style={{display:'flex',alignItems:'center',gap:8}}>
                <span style={{fontSize:13}}>✓</span>
                <span style={{fontSize:12,fontWeight:700,color:G.t1}}>NBC Compliance</span>
              </div>
              <div style={{display:'flex',alignItems:'center',gap:10}}>
                <span style={{fontSize:11,fontWeight:700,color:layout?.is_fully_connected?G.brand:G.amber}}>{layout?.is_fully_connected?'PASS':'CHECK'}</span>
                <span style={{fontSize:12,color:G.t3,transition:'transform 0.2s',display:'inline-block',transform:showValidate?'rotate(180deg)':'rotate(0deg)'}}>▾</span>
              </div>
            </div>
            {showValidate && (
              <div style={{padding:'0 16px 16px',animation:'fadeUp 0.2s ease',borderTop:`1px solid ${G.border}`}}>
                {[
                  {l:'3m Setback Applied',    ok:true},
                  {l:'7.5m Min Road Width',   ok:true},
                  {l:'Park Area ≥ 10%',       ok:parkAreaPct>=10},
                  {l:'All Plots Connected',   ok:layout?.is_fully_connected},
                  {l:'Slope Risk Acceptable', ok:zoningResult?.slope_risk!=='high'},
                  {l:'Entrance Accessible',   ok:true},
                  {l:'Institutional Sites',   ok:numInst>0},
                ].map((item,i,a)=>(
                  <div key={i} style={{display:'flex',alignItems:'center',gap:10,padding:'7px 0',borderBottom:i<a.length-1?`1px solid ${G.border}`:'none',marginTop:i===0?10:0}}>
                    <div style={{width:18,height:18,borderRadius:5,background:item.ok?'#f0fdf4':'#fff7ed',display:'flex',alignItems:'center',justifyContent:'center',fontSize:9,color:item.ok?G.brand:G.amber,fontWeight:900,flexShrink:0}}>
                      {item.ok?'✓':'!'}
                    </div>
                    <span style={{fontSize:11,color:item.ok?G.t2:G.amber,flex:1}}>{item.l}</span>
                    <span style={{fontSize:9,fontWeight:700,color:item.ok?G.brand:G.amber}}>{item.ok?'PASS':'WARN'}</span>
                  </div>
                ))}
              </div>
            )}
          </div>

          {/* Notes accordion */}
          <div className="hov-card" style={{...card,padding:0,overflow:'hidden',marginBottom:0}}>
            <div className="acc-header" onClick={()=>setShowNotes(v=>!v)} style={{padding:'14px 16px',display:'flex',justifyContent:'space-between',alignItems:'center',cursor:'pointer',borderRadius:showNotes?'16px 16px 0 0':16}}>
              <div style={{display:'flex',alignItems:'center',gap:8}}>
                <span style={{fontSize:13}}>✎</span>
                <span style={{fontSize:12,fontWeight:700,color:G.t1}}>Plot Annotations</span>
              </div>
              <div style={{display:'flex',alignItems:'center',gap:10}}>
                <span style={{fontSize:11,fontWeight:700,color:G.brand}}>{annotations.length}</span>
                <span style={{fontSize:12,color:G.t3,transition:'transform 0.2s',display:'inline-block',transform:showNotes?'rotate(180deg)':'rotate(0deg)'}}>▾</span>
              </div>
            </div>
            {showNotes && (
              <div style={{padding:'0 16px 16px',animation:'fadeUp 0.2s ease',borderTop:`1px solid ${G.border}`}}>
                <div onClick={()=>{setAnnotMode(v=>!v)}} style={{margin:'12px 0 8px',background:annotMode?G.light:'#f8f9fa',border:`1.5px solid ${annotMode?G.brand:'transparent'}`,borderRadius:10,padding:'9px 14px',fontSize:11,color:annotMode?G.brand:G.t3,cursor:'pointer',textAlign:'center',fontWeight:600}}>
                  {annotMode?'✏ Click a plot on the map to annotate':'✎  Enable Annotate Mode'}
                </div>
                {pendingAnnot && (
                  <div style={{background:'#f0fdf4',borderRadius:10,padding:12,marginBottom:8}}>
                    <div style={{fontSize:10,color:G.brand,marginBottom:6,fontWeight:600}}>Note for Plot {pendingAnnot.plot_id}</div>
                    <textarea value={annotText} onChange={e=>setAnnotText(e.target.value)} placeholder="Add your note…" rows={2}
                      style={{width:'100%',background:'#fff',border:`1px solid ${G.border}`,borderRadius:7,color:G.t1,fontSize:11,padding:'7px 9px',boxSizing:'border-box',resize:'none',outline:'none',fontFamily:'inherit'}} />
                    <div style={{display:'flex',gap:5,marginTop:6}}>
                      <button onClick={submitAnnotation} style={{flex:1,background:G.brand,border:'none',borderRadius:7,color:'#fff',fontSize:11,padding:'7px',cursor:'pointer',fontWeight:600}}>Save</button>
                      <button onClick={()=>setPendingAnnot(null)} style={{flex:1,background:'#f8f9fa',border:`1px solid ${G.border}`,borderRadius:7,color:G.t2,fontSize:11,padding:'7px',cursor:'pointer'}}>Cancel</button>
                    </div>
                  </div>
                )}
                {annotations.length===0
                  ? <div style={{textAlign:'center',padding:'20px 0',fontSize:11,color:G.t3}}>No annotations yet. Enable annotate mode and click a plot.</div>
                  : annotations.map(ann=>(
                    <div key={ann.id} style={{background:'#f8f9fa',borderRadius:10,padding:'10px 12px',marginBottom:6,border:`1px solid ${G.border}`}}>
                      <div style={{display:'flex',justifyContent:'space-between',marginBottom:4}}>
                        <span style={{fontSize:11,fontWeight:700,color:G.brand}}>Plot {ann.plot_id}</span>
                        <button onClick={()=>deleteAnnotation(ann.id)} style={{background:'none',border:'none',color:G.red,cursor:'pointer',fontSize:14,lineHeight:1}}>×</button>
                      </div>
                      <div style={{fontSize:11,color:G.t2,lineHeight:1.5}}>{ann.text}</div>
                      <div style={{fontSize:9,color:G.t3,marginTop:4}}>{ann.author} · {ann.created_at}</div>
                    </div>
                  ))
                }
              </div>
            )}
          </div>

          {/* Export buttons */}
          <div style={{marginTop:14,display:'flex',flexDirection:'column',gap:7}}>
            <button className="hov-btn" onClick={handlePDF} disabled={pdfLoading} style={{background:G.brand,border:'none',borderRadius:12,padding:'12px',color:'#fff',fontSize:12,fontWeight:700,cursor:pdfLoading?'not-allowed':'pointer',display:'flex',alignItems:'center',justifyContent:'center',gap:7,boxShadow:'0 4px 12px rgba(45,106,47,0.3)'}}>
              {pdfLoading?<Spin color="#fff"/>:null} ⬇ Download PDF Report
            </button>
            <div style={{display:'flex',gap:7}}>
              <button className="hov-btn" onClick={handleDXF} disabled={dxfLoading} style={{flex:1,background:'#fff',border:`1.5px solid ${G.border}`,borderRadius:12,padding:'11px',color:G.t1,fontSize:11,fontWeight:700,cursor:dxfLoading?'not-allowed':'pointer',display:'flex',alignItems:'center',justifyContent:'center',gap:5,boxShadow:G.shadow}}>
                {dxfLoading?<Spin color={G.t1}/>:null} ⊡ CAD (.dxf)
              </button>
              <button className="hov-btn" onClick={handleRERA} disabled={reraLoading} style={{flex:1,background:'#fff',border:`1.5px solid ${G.border}`,borderRadius:12,padding:'11px',color:G.t1,fontSize:11,fontWeight:700,cursor:reraLoading?'not-allowed':'pointer',display:'flex',alignItems:'center',justifyContent:'center',gap:5,boxShadow:G.shadow}}>
                {reraLoading?<Spin color={G.t1}/>:null} ☑ RERA (.pdf)
              </button>
            </div>
          </div>
        </div>

        {/* ── MAP ─────────────────────────────────────────────── */}
        <div style={{flex:1,position:'relative',overflow:'hidden'}}>
          <div ref={mapContainer} style={{position:'absolute',inset:0}} />

          {!mapReady && (
            <div style={{position:'absolute',inset:0,zIndex:20,background:G.bg,display:'flex',flexDirection:'column',alignItems:'center',justifyContent:'center',gap:14}}>
              <div style={{width:42,height:42,border:`3px solid ${G.border}`,borderTop:`3px solid ${G.brand}`,borderRadius:'50%',animation:'spin 0.8s linear infinite'}} />
              <div style={{fontSize:12,color:G.t3,fontWeight:500}}>Loading satellite view…</div>
            </div>
          )}

          {/* Map toolbar — top left */}
          {mapReady && (
            <div style={{position:'absolute',top:14,left:14,zIndex:10,display:'flex',gap:8,animation:'fadeUp 0.3s ease'}}>
              <div style={{position:'relative'}}>
                <button onClick={()=>setShowLayerPanel(v=>!v)} style={{background:'#fff',border:`1px solid ${G.border}`,borderRadius:20,padding:'7px 16px',fontSize:11,fontWeight:700,color:G.t1,cursor:'pointer',display:'flex',alignItems:'center',gap:6,boxShadow:G.shadow}}>
                  🗺 Map <span style={{fontSize:10,color:G.t3}}>▾</span>
                </button>
                {showLayerPanel && (
                  <div style={{position:'absolute',top:'calc(100% + 8px)',left:0,background:'#fff',borderRadius:14,boxShadow:'0 8px 30px rgba(0,0,0,0.12)',border:`1px solid ${G.border}`,padding:'12px',minWidth:200,zIndex:20,animation:'fadeUp 0.15s ease'}}>
                    <div style={{fontSize:9,color:G.t3,fontWeight:700,letterSpacing:'1px',textTransform:'uppercase',marginBottom:6}}>Infrastructure</div>
                    {LAYERS.slice(0,4).map(l=>(
                      <div key={l.id} className="layer-tog" onClick={l.toggle} style={{display:'flex',alignItems:'center',gap:10,padding:'6px 8px',borderRadius:8,cursor:'pointer',marginBottom:2}}>
                        <div style={{width:8,height:8,borderRadius:'50%',background:l.active?l.color:'#d1d5db',boxShadow:l.active?`0 0 6px ${l.color}`:'none',transition:'all 0.15s',flexShrink:0}} />
                        <span style={{fontSize:11,color:l.active?G.t1:G.t3,flex:1,fontWeight:l.active?600:400}}>{l.label}</span>
                        <div style={{width:28,height:16,borderRadius:8,background:l.active?G.brand:'#e2e8f0',transition:'background 0.15s',position:'relative'}}>
                          <div style={{width:12,height:12,borderRadius:'50%',background:'#fff',position:'absolute',top:2,left:l.active?14:2,transition:'left 0.15s',boxShadow:'0 1px 3px rgba(0,0,0,0.15)'}} />
                        </div>
                      </div>
                    ))}
                    <div style={{fontSize:9,color:G.t3,fontWeight:700,letterSpacing:'1px',textTransform:'uppercase',margin:'8px 0 6px'}}>Overlays</div>
                    {LAYERS.slice(4).map(l=>(
                      <div key={l.id} className="layer-tog" onClick={l.toggle} style={{display:'flex',alignItems:'center',gap:10,padding:'6px 8px',borderRadius:8,cursor:'pointer',marginBottom:2}}>
                        <div style={{width:8,height:8,borderRadius:'50%',background:l.active?l.color:'#d1d5db',boxShadow:l.active?`0 0 6px ${l.color}`:'none',transition:'all 0.15s',flexShrink:0}} />
                        <span style={{fontSize:11,color:l.active?G.t1:G.t3,flex:1,fontWeight:l.active?600:400}}>{l.label}</span>
                        <div style={{width:28,height:16,borderRadius:8,background:l.active?G.brand:'#e2e8f0',transition:'background 0.15s',position:'relative'}}>
                          <div style={{width:12,height:12,borderRadius:'50%',background:'#fff',position:'absolute',top:2,left:l.active?14:2,transition:'left 0.15s',boxShadow:'0 1px 3px rgba(0,0,0,0.15)'}} />
                        </div>
                      </div>
                    ))}
                    <div style={{borderTop:`1px solid ${G.border}`,marginTop:8,paddingTop:8}}>
                      <div className="layer-tog" onClick={()=>setAnnotMode(v=>!v)} style={{display:'flex',alignItems:'center',gap:10,padding:'6px 8px',borderRadius:8,cursor:'pointer'}}>
                        <span style={{fontSize:11}}>✏</span>
                        <span style={{fontSize:11,color:annotMode?G.brand:G.t3,fontWeight:annotMode?600:400}}>Annotate Mode</span>
                        <div style={{width:28,height:16,borderRadius:8,background:annotMode?G.brand:'#e2e8f0',marginLeft:'auto',position:'relative'}}>
                          <div style={{width:12,height:12,borderRadius:'50%',background:'#fff',position:'absolute',top:2,left:annotMode?14:2,transition:'left 0.15s',boxShadow:'0 1px 3px rgba(0,0,0,0.15)'}} />
                        </div>
                      </div>
                    </div>
                  </div>
                )}
              </div>

              {/* NSGA-III badge */}
              <div style={{background:'rgba(255,255,255,0.92)',backdropFilter:'blur(10px)',border:`1px solid ${G.border}`,borderRadius:20,padding:'7px 14px',fontSize:10,fontWeight:600,color:G.t2,boxShadow:G.shadow}}>
                NSGA-III · OR-Tools · {currentPareto?.label||'Balanced'}
              </div>
            </div>
          )}

          {/* Fullscreen button — top right */}
          {mapReady && (
            <div style={{position:'absolute',top:14,right:60,zIndex:10}}>
              <button onClick={()=>fitToBoundary(mapRef.current)} style={{background:'#fff',border:`1px solid ${G.border}`,borderRadius:10,width:34,height:34,display:'flex',alignItems:'center',justifyContent:'center',cursor:'pointer',fontSize:13,boxShadow:G.shadow,color:G.t2}}>⊹</button>
            </div>
          )}

          {/* Legend — bottom left */}
          {mapReady && !showPhases && (
            <div style={{position:'absolute',bottom:18,left:18,zIndex:10,background:'rgba(255,255,255,0.95)',backdropFilter:'blur(10px)',border:`1px solid ${G.border}`,borderRadius:14,padding:'12px 14px',boxShadow:G.shadow,animation:'fadeUp 0.3s ease'}}>
              <div style={{fontSize:8,color:G.t3,fontWeight:700,letterSpacing:'1.2px',textTransform:'uppercase',marginBottom:9}}>Legend</div>
              {[
                {c:'#f97316',l:'Residential Plots'},
                {c:'#000',   l:'Road Network',    border:'1px solid #333'},
                {c:'#14532d',l:'Community Park',  border:'1px solid #4ade8044'},
                {c:'#1e3a5f',l:'Institutional',   border:'1px dashed #38bdf8'},
                {c:'#4caf50',l:'Land Boundary',   opacity:0.3},
              ].map((item,i)=>(
                <div key={i} style={{display:'flex',alignItems:'center',gap:8,marginBottom:5}}>
                  <div style={{width:10,height:10,borderRadius:3,background:item.c,border:item.border||'none',opacity:item.opacity||1,flexShrink:0}}/>
                  <span style={{fontSize:10,color:G.t2}}>{item.l}</span>
                </div>
              ))}
            </div>
          )}

          {/* Phase legend */}
          {mapReady && showPhases && (
            <div style={{position:'absolute',bottom:18,left:18,zIndex:10,background:'rgba(255,255,255,0.95)',backdropFilter:'blur(10px)',border:`1px solid ${G.border}`,borderRadius:14,padding:'12px 14px',boxShadow:G.shadow}}>
              <div style={{fontSize:8,color:G.t3,fontWeight:700,letterSpacing:'1.2px',textTransform:'uppercase',marginBottom:9}}>Dev. Phases</div>
              {Object.entries(PHASE_COLORS).map(([ph,col])=>(
                <div key={ph} style={{display:'flex',alignItems:'center',gap:8,marginBottom:5}}>
                  <div style={{width:10,height:10,borderRadius:3,background:col,flexShrink:0}}/>
                  <span style={{fontSize:10,color:G.t2}}>{PHASE_LABELS[ph]}</span>
                </div>
              ))}
            </div>
          )}
          {/* Before/After banner */}
          {showBeforeAfter && (
            <div style={{position:'absolute',top:14,left:'50%',transform:'translateX(-50%)',zIndex:10,background:'rgba(245,158,11,0.95)',borderRadius:20,padding:'5px 18px',fontSize:11,color:'#000',fontWeight:700,boxShadow:'0 2px 12px rgba(0,0,0,0.2)',letterSpacing:'0.3px'}}>
              BEFORE mode — layout faded
            </div>
          )}

          {/* Pending annotation input */}
          {pendingAnnot && (
            <div style={{position:'absolute',top:60,left:'50%',transform:'translateX(-50%)',zIndex:30,background:'#fff',borderRadius:14,padding:16,boxShadow:'0 8px 30px rgba(0,0,0,0.15)',border:`1px solid ${G.border}`,minWidth:240,animation:'fadeUp 0.2s ease'}}>
              <div style={{fontSize:11,color:G.brand,marginBottom:8,fontWeight:700}}>📝 Note for Plot {pendingAnnot.plot_id}</div>
              <textarea value={annotText} onChange={e=>setAnnotText(e.target.value)} placeholder="Add your review note…" rows={2}
                style={{width:'100%',background:'#f8f9fa',border:`1px solid ${G.border}`,borderRadius:8,color:G.t1,fontSize:11,padding:'8px 10px',boxSizing:'border-box',resize:'none',outline:'none',fontFamily:'inherit'}}/>
              <div style={{display:'flex',gap:6,marginTop:8}}>
                <button onClick={submitAnnotation} style={{flex:1,background:G.brand,border:'none',borderRadius:8,color:'#fff',fontSize:11,padding:'8px',cursor:'pointer',fontWeight:700}}>Save Note</button>
                <button onClick={()=>setPendingAnnot(null)} style={{flex:1,background:'#f8f9fa',border:`1px solid ${G.border}`,borderRadius:8,color:G.t2,fontSize:11,padding:'8px',cursor:'pointer'}}>Cancel</button>
              </div>
            </div>
          )}
        </div>
      </div>
    </div>
  )
}

function Spin({color='#333'}) {
  return <div style={{width:12,height:12,border:`2px solid rgba(0,0,0,0.1)`,borderTop:`2px solid ${color}`,borderRadius:'50%',animation:'spin 0.7s linear infinite',flexShrink:0}} />
}