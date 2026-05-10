import Map from '../components/Map'
import Sidebar from '../components/Sidebar'

export default function MapView({ onNavigate }) {
  return (
    <div style={{
      display: 'grid',
      gridTemplateColumns: '1fr 300px',
      gridTemplateRows: '52px 1fr',
      gap: '10px',
      padding: '10px',
      height: '100vh',
      background: '#0f1117',
      boxSizing: 'border-box',
    }}>

      {/* Top Bar */}
      <div style={{
        gridColumn: '1 / -1',
        display: 'flex',
        alignItems: 'center',
        justifyContent: 'space-between',
        background: '#13161f',
        borderRadius: '10px',
        padding: '0 18px',
        border: '0.5px solid #1e2235',
      }}>
        {/* Logo */}
        <div style={{ display: 'flex', alignItems: 'center', gap: 10 }}>
          <div style={{
            width: 30, height: 30,
            background: 'linear-gradient(135deg, #4f9cf9, #7c5cf6)',
            borderRadius: 8, display: 'flex',
            alignItems: 'center', justifyContent: 'center', fontSize: 15,
          }}>🏙️</div>
          <div>
            <div style={{ fontSize: 13, fontWeight: 700, color: '#e2e2e2' }}>
              LandAI <span style={{ color: '#4f9cf9' }}>Optimizer</span>
            </div>
            <div style={{ fontSize: 9, color: '#3a3f55' }}>
              NSGA-III · OR-Tools · Claude AI
            </div>
          </div>
        </div>

        {/* Steps */}
        <div style={{ display: 'flex', gap: 4, alignItems: 'center' }}>
          {[
            '01 Select Land',
            '02 Analyze',
            '03 Generate',
            '04 Results',
          ].map((tab, i) => (
            <div key={i} style={{
              fontSize: 11, padding: '5px 14px',
              borderRadius: 6,
              color: i === 0 ? '#4f9cf9' : '#3a3f55',
              background: i === 0 ? '#0f1a2e' : 'transparent',
              border: i === 0 ? '0.5px solid #4f9cf933' : 'none',
              fontWeight: i === 0 ? 600 : 400,
            }}>
              {tab}
            </div>
          ))}
        </div>

        {/* Status */}
        <div style={{
          display: 'flex', alignItems: 'center', gap: 6,
          background: '#0a1e12',
          border: '0.5px solid #3ecf8e33',
          borderRadius: 20, padding: '5px 14px',
        }}>
          <div style={{
            width: 6, height: 6, borderRadius: '50%',
            background: '#3ecf8e',
            boxShadow: '0 0 6px #3ecf8e',
          }} />
          <span style={{ fontSize: 11, color: '#3ecf8e', fontWeight: 600 }}>
            System Ready
          </span>
        </div>
      </div>

      {/* Map area */}
      <div style={{
        background: '#0d1014',
        borderRadius: '10px',
        border: '0.5px solid #1e2235',
        overflow: 'hidden',
      }}>
        <Map />
      </div>

      {/* Sidebar */}
      <div style={{
        borderRadius: '10px',
        overflow: 'hidden',
        overflowY: 'auto',
      }}>
        <Sidebar />
      </div>

    </div>
  )
}