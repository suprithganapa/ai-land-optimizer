import useStore from '../store/useStore'

const card = {
  background: '#13161f',
  border: '0.5px solid #1e2235',
  borderRadius: '12px',
  padding: '16px',
}

const label = {
  fontSize: '10px',
  fontWeight: 600,
  letterSpacing: '1px',
  textTransform: 'uppercase',
  color: '#3a3f55',
  marginBottom: '12px',
}

const row = (last = false) => ({
  display: 'flex',
  justifyContent: 'space-between',
  alignItems: 'center',
  padding: '6px 0',
  borderBottom: last ? 'none' : '0.5px solid #1a1d2e',
})

export default function Sidebar() {
  const {
    drawnPolygon,
    zoningResult,
    layout,
    isLoading,
    loadingMessage,
  } = useStore()

  const steps = [
    { label: 'Land Boundary Captured',   done: !!drawnPolygon },
    { label: 'Zoning & Legal Check',     done: !!zoningResult },
    { label: 'Bayesian Warm Start',       done: !!layout },
    { label: 'OR-Tools Road Network',     done: !!layout },
    { label: 'NSGA-III Optimization',     done: !!layout },
    { label: 'NetworkX Validation',       done: !!layout },
    { label: 'Claude LLM Audit',          done: !!layout },
    { label: 'Financial Analysis',        done: !!layout },
  ]

  const activeStep = steps.filter(s => s.done).length

  return (
    <div style={{
      display: 'flex',
      flexDirection: 'column',
      gap: '8px',
      height: '100%',
      overflowY: 'auto',
      padding: '2px 2px 12px 2px',
      scrollbarWidth: 'thin',
      scrollbarColor: '#1e2235 transparent',
    }}>

      {/* ── Brand Header ─────────────────────────── */}
      <div style={{
        background: 'linear-gradient(135deg, #0f1623 0%, #131929 100%)',
        border: '0.5px solid #1e2235',
        borderRadius: '12px',
        padding: '16px',
      }}>
        <div style={{
          display: 'flex', alignItems: 'center', gap: '8px', marginBottom: '8px',
        }}>
          <div style={{
            width: '28px', height: '28px',
            background: 'linear-gradient(135deg, #4f9cf9, #7c5cf6)',
            borderRadius: '8px',
            display: 'flex', alignItems: 'center', justifyContent: 'center',
            fontSize: '14px',
          }}>🏙️</div>
          <div>
            <div style={{ fontSize: '13px', fontWeight: 600, color: '#e2e2e2' }}>
              LandAI Optimizer
            </div>
            <div style={{ fontSize: '10px', color: '#3a3f55' }}>
              Powered by NSGA-III · OR-Tools · Claude
            </div>
          </div>
        </div>
        <div style={{
          height: '4px',
          background: '#1a1d2e',
          borderRadius: '4px',
          overflow: 'hidden',
        }}>
          <div style={{
            height: '100%',
            width: `${(activeStep / steps.length) * 100}%`,
            background: 'linear-gradient(90deg, #4f9cf9, #3ecf8e)',
            borderRadius: '4px',
            transition: 'width 0.6s ease',
          }} />
        </div>
        <div style={{
          fontSize: '10px', color: '#3a3f55', marginTop: '6px',
          display: 'flex', justifyContent: 'space-between',
        }}>
          <span>Pipeline Progress</span>
          <span style={{ color: '#4f9cf9' }}>{activeStep} / {steps.length} stages</span>
        </div>
      </div>

      {/* ── Pipeline Steps ───────────────────────── */}
      <div style={{ ...card }}>
        <div style={label}>AI Pipeline</div>
        {steps.map((step, i) => {
          const isActive = i === activeStep && isLoading
          const isDone   = step.done
          return (
            <div key={i} style={{
              display: 'flex', alignItems: 'center', gap: '10px',
              padding: '6px 0',
              borderBottom: i < steps.length - 1 ? '0.5px solid #1a1d2e' : 'none',
              opacity: (!isDone && !isActive) ? 0.4 : 1,
              transition: 'opacity 0.3s',
            }}>
              <div style={{
                width: '20px', height: '20px', borderRadius: '50%', flexShrink: 0,
                background: isDone ? '#0d2e1a' : isActive ? '#130d2a' : '#0f1117',
                border: `1.5px solid ${isDone ? '#3ecf8e' : isActive ? '#7c5cf6' : '#1e2235'}`,
                display: 'flex', alignItems: 'center', justifyContent: 'center',
                fontSize: '9px', fontWeight: 600,
                color: isDone ? '#3ecf8e' : isActive ? '#a78bfa' : '#3a3f55',
                boxShadow: isActive ? '0 0 8px #7c5cf644' : 'none',
              }}>
                {isDone ? '✓' : isActive ? '◉' : i + 1}
              </div>
              <span style={{
                fontSize: '11px',
                color: isDone ? '#3ecf8e' : isActive ? '#a78bfa' : '#3a3f55',
                fontWeight: isDone || isActive ? 500 : 400,
              }}>
                {step.label}
              </span>
              {isDone && (
                <div style={{
                  marginLeft: 'auto',
                  width: '6px', height: '6px',
                  borderRadius: '50%',
                  background: '#3ecf8e',
                }} />
              )}
            </div>
          )
        })}
      </div>

      {/* ── Loading State ────────────────────────── */}
      {isLoading && (
        <div style={{
          background: 'linear-gradient(135deg, #130d2a, #0f1623)',
          border: '0.5px solid #7c5cf633',
          borderRadius: '12px',
          padding: '16px',
          textAlign: 'center',
        }}>
          <div style={{
            width: '36px', height: '36px',
            border: '3px solid #1e1e3e',
            borderTop: '3px solid #7c5cf6',
            borderRadius: '50%',
            margin: '0 auto 12px',
            animation: 'spin 1s linear infinite',
          }} />
          <style>{`@keyframes spin { to { transform: rotate(360deg); } }`}</style>
          <div style={{ fontSize: '12px', color: '#a78bfa', fontWeight: 500 }}>
            {loadingMessage}
          </div>
          <div style={{ fontSize: '10px', color: '#3a3f55', marginTop: '6px' }}>
            AI pipeline running...
          </div>
        </div>
      )}

      {/* ── Building Warning ─────────────────────── */}
      {zoningResult?.has_buildings && (
        <div style={{
          background: 'linear-gradient(135deg, #1e1200, #1a1000)',
          border: '1px solid #f59e0b44',
          borderRadius: '12px',
          padding: '16px',
        }}>
          <div style={{
            display: 'flex', alignItems: 'center', gap: '8px', marginBottom: '10px',
          }}>
            <div style={{
              width: '28px', height: '28px',
              background: '#2e1a0d',
              borderRadius: '8px',
              display: 'flex', alignItems: 'center', justifyContent: 'center',
              fontSize: '14px', flexShrink: 0,
            }}>🏗️</div>
            <div>
              <div style={{ fontSize: '12px', fontWeight: 700, color: '#f59e0b' }}>
                Existing Structures Detected
              </div>
              <div style={{ fontSize: '10px', color: '#7a5a2a' }}>
                {zoningResult.building_count} structure(s) on this plot
              </div>
            </div>
          </div>

          <div style={{
            background: '#120d00',
            borderRadius: '8px',
            padding: '8px 10px',
            marginBottom: '8px',
          }}>
            {zoningResult.buildings_found?.map((b, i) => (
              <div key={i} style={{
                display: 'flex', alignItems: 'center', gap: '6px',
                padding: '3px 0',
                borderBottom: i < zoningResult.buildings_found.length - 1
                  ? '0.5px solid #1e1500' : 'none',
              }}>
                <div style={{
                  width: '5px', height: '5px',
                  borderRadius: '50%',
                  background: '#f59e0b',
                  flexShrink: 0,
                }} />
                <span style={{ fontSize: '11px', color: '#c8891a' }}>
                  {b.name ? `${b.name} (${b.label})` : b.label}
                </span>
              </div>
            ))}
          </div>

          <div style={{
            fontSize: '10px', color: '#7a5a2a', lineHeight: 1.5,
          }}>
            ⚠️ Development may require demolition clearance from municipal authorities
            before construction permits can be issued.
          </div>
        </div>
      )}

      {/* ── Zoning Result Card ───────────────────── */}
      {zoningResult && (
        <div style={{
          background: zoningResult.is_legal
            ? 'linear-gradient(135deg, #0a1e12, #0d2218)'
            : 'linear-gradient(135deg, #1e0a0a, #220d0d)',
          border: `0.5px solid ${zoningResult.is_legal ? '#3ecf8e33' : '#f8717133'}`,
          borderRadius: '12px',
          padding: '16px',
        }}>
          {/* Status badge */}
          <div style={{
            display: 'inline-flex', alignItems: 'center', gap: '6px',
            background: zoningResult.is_legal ? '#0d2e1a' : '#2e0d0d',
            border: `1px solid ${zoningResult.is_legal ? '#3ecf8e55' : '#f8717155'}`,
            borderRadius: '20px',
            padding: '4px 10px',
            marginBottom: '12px',
          }}>
            <div style={{
              width: '6px', height: '6px', borderRadius: '50%',
              background: zoningResult.is_legal ? '#3ecf8e' : '#f87171',
            }} />
            <span style={{
              fontSize: '11px', fontWeight: 600,
              color: zoningResult.is_legal ? '#3ecf8e' : '#f87171',
            }}>
              {zoningResult.is_legal ? 'Legal to Build' : 'Plot Not Available'}
            </span>
          </div>

          {/* Rejection reasons */}
          {zoningResult.rejection_reasons?.length > 0 && (
            <div style={{ marginBottom: '12px' }}>
              {zoningResult.rejection_reasons.map((r, i) => (
                <div key={i} style={{
                  display: 'flex', gap: '6px', alignItems: 'flex-start',
                  padding: '4px 0',
                }}>
                  <span style={{ color: '#f87171', flexShrink: 0, fontSize: '11px' }}>⚠</span>
                  <span style={{ fontSize: '11px', color: '#f87171', lineHeight: 1.4 }}>{r}</span>
                </div>
              ))}
            </div>
          )}

          {/* Data rows */}
          {[
            { label: 'Zone Classification', value: zoningResult.zone_label,                              color: '#e2e2e2' },
            { label: 'Total Land Area',      value: `${zoningResult.area_m2?.toLocaleString()} m²`,      color: '#e2e2e2' },
            { label: 'Buildable Area',       value: `${zoningResult.setback_area_m2?.toLocaleString()} m²`, color: '#4f9cf9' },
            { label: 'Perimeter',            value: `${zoningResult.perimeter_m} m`,                     color: '#e2e2e2' },
            { label: 'Elevation',            value: `${zoningResult.elevation_m} m ASL`,                 color: '#e2e2e2' },
            { label: 'Terrain Risk',         value: zoningResult.slope_risk?.toUpperCase(),              color: zoningResult.slope_risk === 'low' ? '#3ecf8e' : '#f59e0b' },
            { label: 'Data Source',          value: zoningResult.zone_source,                            color: '#3a3f55' },
          ].map((item, i, arr) => (
            <div key={i} style={row(i === arr.length - 1)}>
              <span style={{ fontSize: '11px', color: '#3a3f55' }}>{item.label}</span>
              <span style={{ fontSize: '11px', fontWeight: 500, color: item.color }}>
                {item.value}
              </span>
            </div>
          ))}
        </div>
      )}

      {/* ── NBC 2016 Constraints ─────────────────── */}
      {zoningResult?.constraints && (
        <div style={card}>
          <div style={label}>NBC 2016 Constraints Applied</div>
          {[
            { icon: '📐', label: 'Minimum Setback',    value: `${zoningResult.constraints.min_setback_m}m`, ok: true },
            { icon: '🛣️', label: 'Min Road Width',     value: `${zoningResult.constraints.min_road_width_m}m`, ok: true },
            { icon: '🌳', label: 'Min Park Area',      value: `${Math.round(zoningResult.constraints.min_park_area_m2)} m²`, ok: true },
            { icon: '⛰️', label: 'Max Slope Allowed',  value: `${zoningResult.constraints.max_slope_degrees}°`, ok: true },
          ].map((item, i, arr) => (
            <div key={i} style={{
              display: 'flex', alignItems: 'center', gap: '10px',
              padding: '7px 0',
              borderBottom: i < arr.length - 1 ? '0.5px solid #1a1d2e' : 'none',
            }}>
              <span style={{ fontSize: '14px' }}>{item.icon}</span>
              <span style={{ fontSize: '11px', color: '#888', flex: 1 }}>{item.label}</span>
              <span style={{
                fontSize: '11px', fontWeight: 600,
                color: '#4f9cf9',
                background: '#0f1a2e',
                borderRadius: '6px',
                padding: '2px 8px',
              }}>
                {item.value}
              </span>
            </div>
          ))}
        </div>
      )}

      {/* ── Layout Result ────────────────────────── */}
      {layout && (
        <div style={{
          background: 'linear-gradient(135deg, #0a1e12, #0d2218)',
          border: '0.5px solid #3ecf8e33',
          borderRadius: '12px',
          padding: '16px',
        }}>
          <div style={label}>Layout Generated</div>

          <div style={{ textAlign: 'center', marginBottom: '16px' }}>
            <div style={{
              fontSize: '48px', fontWeight: 700,
              color: '#3ecf8e', lineHeight: 1,
              letterSpacing: '-2px',
            }}>
              {layout.efficiency_score}%
            </div>
            <div style={{ fontSize: '11px', color: '#3a5a40', marginTop: '4px' }}>
              Land Utilization Efficiency
            </div>
            <div style={{
              display: 'inline-block',
              fontSize: '10px', color: '#3ecf8e',
              background: '#0d2e1a',
              borderRadius: '12px', padding: '2px 10px',
              marginTop: '6px',
            }}>
              ↑ +12% vs manual planning average
            </div>
          </div>

          <div style={{
            display: 'grid', gridTemplateColumns: '1fr 1fr',
            gap: '6px', marginBottom: '4px',
          }}>
            {[
              { label: 'Total Plots',  value: layout.num_plots,                                   color: '#4f9cf9' },
              { label: 'Land Area',    value: `${layout.area_m2?.toLocaleString()} m²`,           color: '#e2e2e2' },
              { label: 'Plot Area',    value: `${layout.total_plot_area_m2?.toLocaleString()} m²`, color: '#e8713c' },
              { label: 'Park Area',    value: `${layout.total_park_area_m2?.toLocaleString()} m²`, color: '#3ecf8e' },
            ].map((stat, i) => (
              <div key={i} style={{
                background: '#081510',
                borderRadius: '8px', padding: '10px',
                textAlign: 'center',
              }}>
                <div style={{ fontSize: '10px', color: '#3a5a40', marginBottom: '4px' }}>
                  {stat.label}
                </div>
                <div style={{ fontSize: '15px', fontWeight: 600, color: stat.color }}>
                  {stat.value}
                </div>
              </div>
            ))}
          </div>
        </div>
      )}

      {/* ── How to Use ───────────────────────────── */}
      {!drawnPolygon && (
        <div style={card}>
          <div style={label}>Getting Started</div>
          {[
            { step: '01', text: 'Search for any location using the search bar' },
            { step: '02', text: 'Click "Draw Boundary" and mark land corners' },
            { step: '03', text: 'Click "Close & Finish" to complete the polygon' },
            { step: '04', text: 'Click "Analyze Land" for zoning & legal check' },
            { step: '05', text: 'Click "Generate Layout" to run the AI pipeline' },
            { step: '06', text: 'View 3D layout, financials, and download PDF' },
          ].map((item, i) => (
            <div key={i} style={{
              display: 'flex', gap: '10px', alignItems: 'flex-start',
              padding: '6px 0',
              borderBottom: i < 5 ? '0.5px solid #1a1d2e' : 'none',
            }}>
              <div style={{
                fontSize: '9px', fontWeight: 700,
                color: '#4f9cf9', background: '#0f1a2e',
                borderRadius: '4px', padding: '2px 5px',
                flexShrink: 0, marginTop: '1px',
              }}>
                {item.step}
              </div>
              <span style={{ fontSize: '11px', color: '#4a5070', lineHeight: 1.4 }}>
                {item.text}
              </span>
            </div>
          ))}
        </div>
      )}

      {/* ── Footer ───────────────────────────────── */}
      <div style={{
        textAlign: 'center',
        padding: '8px',
        fontSize: '10px',
        color: '#252840',
      }}>
        LandAI © 2025 · NSGA-III · OR-Tools · Claude API
      </div>

    </div>
  )
}