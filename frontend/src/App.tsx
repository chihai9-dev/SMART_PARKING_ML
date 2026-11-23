import { useEffect, useRef, useState } from 'react'
import {
  deletePlateScan,
  fetchPlateScans,
  fetchPlateScanStats,
  previewPlate,
  scanPlate,
} from './api'
import type {
  AlgorithmComparisonReport,
  PlateColorResult,
  PlatePreview,
  PlateScanDto,
  PlateScanStats,
  ScanResult,
} from './api'

type MenuId = 'camera' | 'upload' | 'history' | 'dashboard' | 'settings'

const menuItems: { id: MenuId; icon: string; label: string }[] = [
  { id: 'camera',    icon: '\uD83C\uDFA5', label: 'Quet Camera' },
  { id: 'upload',    icon: '\uD83D\uDDBC', label: 'Tai anh nhan dien' },
  { id: 'history',   icon: '\uD83D\uDCCB', label: 'Nhat ky nhan dien' },
  { id: 'dashboard', icon: '\uD83D\uDCCA', label: 'Thong ke' },
  { id: 'settings',  icon: '\u2699',       label: 'He thong' },
]

const pageDetails: Record<MenuId, { title: string; description: string }> = {
  camera: {
    title: 'Quet Camera truc tiep',
    description: 'Nhan dien bien so xe va phan loai mau nen theo thoi gian thuc qua webcam bang YOLOv8 va RapidOCR.',
  },
  upload: {
    title: 'Tai anh & Nhan dien',
    description: 'Tai anh len he thong, tu dong khoanh vung bien so, nhan dang ky tu, phan loai mau nen va luu vao CSDL.',
  },
  history: {
    title: 'Nhat ky nhan dien',
    description: 'Tra cuu, tim kiem va quan ly toan bo cac luot quet bien so xe da luu trong SQL Server.',
  },
  dashboard: {
    title: 'Bao cao thong ke',
    description: 'Tong hop so luot nhan dien bien so va do tin cay cua mo hinh AI.',
  },
  settings: {
    title: 'Trang thai he thong',
    description: 'Kiem tra trang thai cac dich vu: Python AI Service, .NET Web API va SQL Server.',
  },
}

// ─── Color badge helpers ───────────────────────────────────────────────────
const COLOR_CFG: Record<string, { bg: string; border: string; text: string; label: string }> = {
  White:  { bg: '#f0f0f0', border: '#ccc',    text: '#333',    label: 'Trang (Dan su)' },
  Yellow: { bg: '#fbbf24', border: '#d97706',  text: '#7c3800', label: 'Vang (Kinh doanh)' },
  Blue:   { bg: '#1d4ed8', border: '#1e3a8a',  text: '#fff',    label: 'Xanh (Co quan NN)' },
  Red:    { bg: '#dc2626', border: '#991b1b',  text: '#fff',    label: 'Do (Quan doi)' },
}

function ColorBadge({ color }: { color?: PlateColorResult | null }) {
  if (color?.scope_status === 'unsupported_color') {
    return <span style={{ fontSize: 11, color: '#b45309', fontWeight: 600 }}>Ngoai pham vi ho tro</span>
  }
  if (!color || !color.color_code || color.color_code === 'Unknown') {
    return <span style={{ fontSize: 11, color: '#999', fontStyle: 'italic' }}>Chua phan loai</span>
  }
  const cfg = COLOR_CFG[color.color_code]
  if (!cfg) {
    return <span style={{ fontSize: 11, color: '#666' }}>{color.color_code}</span>
  }
  const pct = typeof color.confidence === 'number' ? (color.confidence * 100).toFixed(0) + '%' : ''
  return (
    <span style={{
      display: 'inline-flex', alignItems: 'center', gap: 4,
      background: cfg.bg, color: cfg.text, border: `1px solid ${cfg.border}`,
      padding: '2px 10px', borderRadius: 12, fontSize: 12, fontWeight: 600,
    }}>
      {cfg.label}
      {pct && <span style={{ opacity: 0.75, fontWeight: 400, marginLeft: 2 }}>({pct})</span>}
    </span>
  )
}

function ClassifierResultTable({ title, color }: { title: string; color?: PlateColorResult }) {
  return (
    <div className="classifier-result-table">
      <h4>{title}</h4>
      <table>
        <tbody>
          <tr>
            <th>Thuat toan</th>
            <td>{color?.algorithm ?? title}</td>
          </tr>
          <tr>
            <th>Mau du doan</th>
            <td><ColorBadge color={color} /></td>
          </tr>
          <tr>
            <th>Do tin cay</th>
            <td>{typeof color?.confidence === 'number' ? `${(color.confidence * 100).toFixed(1)}%` : '\u2014'}</td>
          </tr>
          {color?.message && (
            <tr>
              <th>Pham vi</th>
              <td>{color.message}</td>
            </tr>
          )}
        </tbody>
      </table>
    </div>
  )
}

function ModelEvaluationTable({ report }: { report?: AlgorithmComparisonReport | null }) {
  const repeated = report?.repeated_evaluation
  const summary = repeated?.summary
  const models = [
    { key: 'RandomForestClassifier', label: 'Random Forest' },
    { key: 'KNeighborsClassifier', label: 'KNN' },
  ]
  const fastest = models.reduce((best, model) => {
    const latency = summary?.[model.key]?.median_ms_per_image_mean
    const bestLatency = summary?.[best.key]?.median_ms_per_image_mean
    return typeof latency === 'number' && (typeof bestLatency !== 'number' || latency < bestLatency)
      ? model
      : best
  })
  const mostStable = models.reduce((best, model) => {
    const variation = summary?.[model.key]?.f1_macro_std
    const bestVariation = summary?.[best.key]?.f1_macro_std
    return typeof variation === 'number' && (typeof bestVariation !== 'number' || variation < bestVariation)
      ? model
      : best
  })
  const sameRecommendation = summary
    && typeof summary[fastest.key]?.median_ms_per_image_mean === 'number'
    && typeof summary[mostStable.key]?.f1_macro_std === 'number'
    && fastest.key === mostStable.key
  const fastestLatency = summary?.[fastest.key]?.median_ms_per_image_mean

  return (
    <section className="model-evaluation">
      <h4>Ket luan so sanh mo hinh</h4>
      {sameRecommendation && repeated ? (
        <div className="model-verdict">
          <strong>{fastest.label} nhanh nhất và ổn định hơn</strong>
          <span>
            {typeof fastestLatency === 'number' ? `${fastestLatency.toFixed(2)} ms/ảnh` : ''}
            {repeated.run_count ? ` · ${repeated.run_count} lần huấn luyện` : ''}
          </span>
        </div>
      ) : summary ? (
        <div className="model-verdict">
          <strong>Tốc độ tốt nhất: {fastest.label} · Ổn định nhất: {mostStable.label}</strong>
        </div>
      ) : (
        <p className="evaluation-caveat">Chưa có báo cáo so sánh. Hãy chạy `python train_plate_color.py`.</p>
      )}
    </section>
  )
}

// ─── Utility helpers ───────────────────────────────────────────────────────
function formatDateTime(value?: string | null) {
  if (!value) return '\u2014'
  const d = new Date(value)
  if (Number.isNaN(d.getTime())) return value
  return d.toLocaleString('vi-VN', {
    day: '2-digit', month: '2-digit', year: 'numeric',
    hour: '2-digit', minute: '2-digit', second: '2-digit',
  })
}

function formatPlate(plate?: string | null) {
  if (!plate) return 'CHUA RO'
  return plate.toUpperCase()
}

function colorCodeToLabel(code?: string | null) {
  if (!code || code === 'Unknown') return null
  return COLOR_CFG[code]?.label ?? code
}

// ─── Main App ─────────────────────────────────────────────────────────────
export default function App() {
  const [activeMenu, setActiveMenu] = useState<MenuId>('camera')
  const [scans, setScans] = useState<PlateScanDto[]>([])
  const [stats, setStats] = useState<PlateScanStats | null>(null)
  const [loadingScans, setLoadingScans] = useState(false)
  const [connected, setConnected] = useState(false)
  const [errorMessage, setErrorMessage] = useState('')
  const [refreshKey, setRefreshKey] = useState(0)
  const [searchTerm, setSearchTerm] = useState('')
  const [lightbox, setLightbox] = useState<{ title: string; src: string } | null>(null)

  // Upload tab
  const [uploadFile, setUploadFile] = useState<File | null>(null)
  const [uploadPreviewUrl, setUploadPreviewUrl] = useState('')
  const [uploadScanning, setUploadScanning] = useState(false)
  const [uploadResult, setUploadResult] = useState<ScanResult | null>(null)
  const [uploadError, setUploadError] = useState('')
  const [isDragOver, setIsDragOver] = useState(false)

  // Camera tab
  const [cameraOn, setCameraOn] = useState(false)
  const [autoScanEnabled, setAutoScanEnabled] = useState(true)
  const [cameraBusy, setCameraBusy] = useState(false)
  const [cameraStatus, setCameraStatus] = useState('Camera chua bat.')
  const [latestPreview, setLatestPreview] = useState<PlatePreview | null>(null)
  const [lastSavedScan, setLastSavedScan] = useState<PlateScanDto | null>(null)
  const [stableCount, setStableCount] = useState(0)

  const videoRef = useRef<HTMLVideoElement | null>(null)
  const canvasRef = useRef<HTMLCanvasElement | null>(null)
  const streamRef = useRef<MediaStream | null>(null)
  const isFrameProcessing = useRef(false)
  const stablePlateCandidate = useRef({ plate: '', count: 0 })
  const lastProcessedPlate = useRef('')

  // Load scans + stats
  useEffect(() => {
    let cancelled = false
    setLoadingScans(true)
    setErrorMessage('')
    Promise.all([fetchPlateScans(), fetchPlateScanStats()])
      .then(([scansData, statsData]) => {
        if (cancelled) return
        setScans(scansData)
        setStats(statsData)
        setConnected(true)
      })
      .catch((err: unknown) => {
        if (cancelled) return
        setConnected(false)
        setErrorMessage(err instanceof Error ? err.message : 'Khong ket noi duoc .NET Backend.')
      })
      .finally(() => { if (!cancelled) setLoadingScans(false) })
    return () => { cancelled = true }
  }, [refreshKey])

  useEffect(() => { if (activeMenu !== 'camera') stopCamera() }, [activeMenu])
  useEffect(() => () => stopCamera(), [])

  async function startCamera() {
    setErrorMessage('')
    setCameraStatus('Dang khoi dong webcam...')
    if (!navigator.mediaDevices?.getUserMedia) {
      setCameraStatus('Trinh duyet khong ho tro webcam hoac chua cap quyen.')
      return
    }
    try {
      const stream = await navigator.mediaDevices.getUserMedia({
        video: { width: { ideal: 1280 }, height: { ideal: 720 }, facingMode: { ideal: 'environment' } },
        audio: false,
      })
      streamRef.current = stream
      if (videoRef.current) { videoRef.current.srcObject = stream; await videoRef.current.play() }
      setCameraOn(true)
      setCameraStatus('Camera dang quet. Hay huong camera vao bien so xe...')
    } catch (err) {
      setCameraStatus(err instanceof Error ? 'Loi mo camera: ' + err.message : 'Khong the mo webcam.')
    }
  }

  function stopCamera() {
    streamRef.current?.getTracks().forEach(t => t.stop())
    streamRef.current = null
    if (videoRef.current) videoRef.current.srcObject = null
    setCameraOn(false)
    setLatestPreview(null)
    setStableCount(0)
    stablePlateCandidate.current = { plate: '', count: 0 }
    lastProcessedPlate.current = ''
    setCameraStatus('Camera da tat.')
  }

  function captureFrameBlob(): Promise<Blob> {
    return new Promise((resolve, reject) => {
      const video = videoRef.current
      const canvas = canvasRef.current
      if (!video || !canvas || !video.videoWidth || !video.videoHeight) {
        reject(new Error('Khung hinh chua san sang.')); return
      }
      canvas.width = video.videoWidth
      canvas.height = video.videoHeight
      const ctx = canvas.getContext('2d')
      if (!ctx) { reject(new Error('Khong the render khung hinh.')); return }
      ctx.drawImage(video, 0, 0, canvas.width, canvas.height)
      canvas.toBlob(blob => { if (blob) resolve(blob); else reject(new Error('Loi chuyen anh sang Blob.')) }, 'image/jpeg', 0.88)
    })
  }

  // Camera auto-scan loop
  useEffect(() => {
    if (activeMenu !== 'camera' || !cameraOn || !autoScanEnabled) return
    let isCancelled = false
    let timerId: number | undefined
    const loop = async () => {
      if (isCancelled) return
      if (isFrameProcessing.current || !videoRef.current?.videoWidth) {
        timerId = window.setTimeout(loop, 400); return
      }
      isFrameProcessing.current = true
      try {
        const frameBlob = await captureFrameBlob()
        const preview = await previewPlate(frameBlob)
        if (isCancelled) return
        setLatestPreview(preview)
        const rawPlate = preview.valid && preview.plate ? preview.plate.toUpperCase().replace(/[^A-Z0-9]/g, '') : ''
        if (!rawPlate) {
          stablePlateCandidate.current = { plate: '', count: 0 }
          setStableCount(0)
          setCameraStatus(preview.message || 'Dang quet... Hay dua bien so vao giua khung hinh.')
        } else {
          const prev = stablePlateCandidate.current
          const count = prev.plate === rawPlate ? prev.count + 1 : 1
          stablePlateCandidate.current = { plate: rawPlate, count }
          setStableCount(Math.min(count, 3))
          if (count < 3) {
            setCameraStatus(`Da phat hien ${rawPlate}. Dang xac minh on dinh (${count}/3 frame)...`)
          } else if (lastProcessedPlate.current === rawPlate) {
            setCameraStatus(`Bien so ${rawPlate} da duoc luu vao CSDL. Dang theo doi...`)
          } else {
            lastProcessedPlate.current = rawPlate
            setCameraBusy(true)
            setCameraStatus(`Da xac thuc ${rawPlate}! Dang luu vao SQL Server...`)
            try {
              const scanRes = await scanPlate(frameBlob)
              setRefreshKey(k => k + 1)
              const colorLabel = scanRes.plate_color?.color_code && scanRes.plate_color.color_code !== 'Unknown'
                ? ' - ' + (colorCodeToLabel(scanRes.plate_color.color_code) ?? '')
                : ''
              setCameraStatus(`Da luu bien so ${rawPlate}${colorLabel} vao CSDL thanh cong!`)
              setLastSavedScan({
                scanId: Date.now(),
                plate: scanRes.plate || rawPlate,
                confidence: scanRes.confidence || 0.95,
                cropImagePath: scanRes.crop_path ? `/scan-image/${(scanRes.crop_path as string).split(/[\\/]/).pop()}` : null,
                scanTime: new Date().toISOString(),
                note: 'Tu dong quet tu Camera',
                colorCode: scanRes.plate_color?.color_code ?? null,
              })
            } catch (saveErr) {
              lastProcessedPlate.current = ''
              setCameraStatus('Loi khi luu vao co so du lieu: ' + (saveErr instanceof Error ? saveErr.message : ''))
            } finally {
              setCameraBusy(false)
            }
          }
        }
      } catch {
        if (!isCancelled) setCameraStatus('Khong the quet frame camera.')
      } finally {
        isFrameProcessing.current = false
        if (!isCancelled) timerId = window.setTimeout(loop, 750)
      }
    }
    timerId = window.setTimeout(loop, 400)
    return () => { isCancelled = true; if (timerId) window.clearTimeout(timerId) }
  }, [activeMenu, cameraOn, autoScanEnabled])

  async function handleManualCapture() {
    if (!cameraOn) return
    setCameraBusy(true)
    setCameraStatus('Dang chup va nhan dien bien so...')
    try {
      const blob = await captureFrameBlob()
      const res = await scanPlate(blob)
      setUploadResult(res)
      setRefreshKey(k => k + 1)
      setCameraStatus(`Da nhan dien: ${res.plate || 'Khong tim thay'} (${(Number(res.confidence || 0) * 100).toFixed(1)}%)`)
    } catch (err) {
      setCameraStatus(err instanceof Error ? err.message : 'Loi nhan dien.')
    } finally {
      setCameraBusy(false)
    }
  }

  function handleFileSelect(file: File) {
    if (!file.type.startsWith('image/')) { setUploadError('Vui long chon file hinh anh (JPG, PNG, WEBP).'); return }
    setUploadFile(file)
    setUploadPreviewUrl(URL.createObjectURL(file))
    setUploadResult(null)
    setUploadError('')
  }

  async function handleExecuteUploadScan() {
    if (!uploadFile) return
    setUploadScanning(true)
    setUploadError('')
    try {
      const res = await scanPlate(uploadFile)
      setUploadResult(res)
      setRefreshKey(k => k + 1)
    } catch (err) {
      setUploadError(err instanceof Error ? err.message : 'Loi trong qua trinh nhan dien anh.')
    } finally {
      setUploadScanning(false)
    }
  }

  async function handleDeleteScan(id: number) {
    if (!window.confirm(`Ban co chac chan muon xoa luot quet #${id} khong?`)) return
    try { await deletePlateScan(id); setRefreshKey(k => k + 1) }
    catch (err) { alert(err instanceof Error ? err.message : 'Xoa that bai.') }
  }

  function handleExportCsv() {
    if (scans.length === 0) { alert('Khong co du lieu de xuat file.'); return }
    const headers = ['Ma quet', 'Bien so', 'Mau bien so', 'Do tin cay', 'Thoi gian quet', 'Ghi chu']
    const rows = scans.map(s => [
      s.scanId,
      `"${s.plate}"`,
      `"${colorCodeToLabel(s.colorCode) ?? 'Chua phan loai'}"`,
      `"${(s.confidence * 100).toFixed(1)}%"`,
      `"${formatDateTime(s.scanTime)}"`,
      `"${s.note || ''}"`,
    ])
    const csvContent = '\uFEFF' + [headers.join(','), ...rows.map(r => r.join(','))].join('\r\n')
    const blob = new Blob([csvContent], { type: 'text/csv;charset=utf-8;' })
    const url = URL.createObjectURL(blob)
    const link = document.createElement('a')
    link.href = url
    link.download = `plate_scans_${new Date().toISOString().slice(0, 10)}.csv`
    link.click()
    URL.revokeObjectURL(url)
  }

  const filteredScans = scans.filter(s => {
    const term = searchTerm.trim().toLowerCase()
    return !term || s.plate.toLowerCase().includes(term) || (s.note || '').toLowerCase().includes(term)
  })

  const currentPage = pageDetails[activeMenu]

  return (
    <div className="app-shell">
      {/* Sidebar */}
      <aside className="sidebar">
        <div className="brand">
          <div className="brand-logo">SGU</div>
          <div className="brand-copy">
            <div className="brand-name">ALPR</div>
            <div className="brand-subtitle">Hệ Thống Nhận diện biển số xe</div>
          </div>
        </div>
        <div className="sidebar-section-title">CHỨC NĂNG</div>
        <nav className="sidebar-menu" aria-label="Menu chinh">
          {menuItems.map(item => (
            <button
              key={item.id}
              className={'menu-item ' + (activeMenu === item.id ? 'active' : '')}
              onClick={() => setActiveMenu(item.id)}
            >
              <span className="menu-icon" aria-hidden="true">{item.icon}</span>
              <span>{item.label}</span>
            </button>
          ))}
        </nav>
        <div className="sidebar-bottom">
          <div className="data-note">
            <span className="note-mark">{connected ? '\u2713' : '!'}</span>
            <p>{connected ? `Đã kết nối với SQL Server (${scans.length} ban ghi).` : 'Đang kiểm tra kết nối với .NET Backend...'}</p>
          </div>
          <div className="sidebar-version">Design by DangkhoiJR</div>
        </div>
      </aside>

      {/* Main */}
      <main className="main-content">
        <header className="topbar">
          <div>
            <div className="breadcrumb">Nhan dien bien so xe <span>/</span> {currentPage.title}</div>
            <h1>{currentPage.title}</h1>
            <p className="page-description">{currentPage.description}</p>
          </div>
          <div className="topbar-actions">
            <span className={'sample-label ' + (connected ? 'connected-label' : '')}>
              <span />
              {connected ? 'SQL Server & API sẵn sàng' : 'Mất kết nối với API'}
            </span>
            <button className="refresh-button" onClick={() => setRefreshKey(k => k + 1)} disabled={loadingScans}>
              Làm mới
            </button>
            <div className="profile">
              <div className="profile-avatar">SGU</div>
              <div className="profile-info"><strong></strong><span></span></div>
            </div>
          </div>
        </header>

        {errorMessage && (
          <div className="feedback feedback-error" role="alert" style={{ marginBottom: 20 }}>
            {errorMessage} — Vui long dam bao .NET Backend (port 5049) va Python AI Service (port 5000) dang chay.
          </div>
        )}

        {/* ======== TAB 1: CAMERA ======== */}
        {activeMenu === 'camera' && (
          <div className="gate-layout">
            <section className="panel gate-panel">
              <div className="panel-header">
                <div>
                  <h3>Camera quet thoi gian thuc</h3>
                  <p>Mo hinh YOLOv8 tu dong khoanh vung bien so, RapidOCR trich xuat ky tu, RandomForest phan loai mau.</p>
                </div>
                <span className={cameraOn ? 'status-pill status-open' : 'status-pill status-closed'}>
                  {cameraOn ? 'Dang hoat dong' : 'Camera tat'}
                </span>
              </div>

              <div className="camera-scanner-wrapper">
                <video ref={videoRef} autoPlay playsInline muted style={{ display: cameraOn ? 'block' : 'none' }} />
                {cameraOn && <div className="scan-line" />}
                {!cameraOn && (
                  <div className="camera-offline">
                    <div className="camera-symbol">{'\uD83D\uDCF7'}</div>
                    <strong>Webcam chua bat</strong>
                    <span>Nhan nut "Bat Camera" ben duoi de bat dau nhan dien.</span>
                  </div>
                )}
              </div>
              <canvas ref={canvasRef} style={{ display: 'none' }} />

              <div className="camera-controls" style={{ display: 'flex', gap: 10, flexWrap: 'wrap', padding: '14px 17px' }}>
                {!cameraOn ? (
                  <button className="primary-button" onClick={startCamera}>Bat Camera & Bat dau quet</button>
                ) : (
                  <>
                    <button className="secondary-button inline-button" onClick={stopCamera}>Tat Camera</button>
                    <button className="primary-button" onClick={handleManualCapture} disabled={cameraBusy}>
                      {cameraBusy ? 'Dang xu ly...' : 'Chup & Luu ngay'}
                    </button>
                    <label style={{ display: 'inline-flex', alignItems: 'center', gap: 6, fontSize: 12, marginLeft: 'auto', cursor: 'pointer' }}>
                      <input type="checkbox" checked={autoScanEnabled} onChange={e => setAutoScanEnabled(e.target.checked)} />
                      <span>Tu dong quet lien tuc</span>
                    </label>
                  </>
                )}
              </div>

              <div className="auto-scan-status">
                <div className="auto-scan-copy">
                  <strong>Trang thai nhan dien:</strong>
                  <span>{cameraStatus}</span>
                </div>
                {cameraOn && autoScanEnabled && (
                  <div className="frame-progress" title={`Do on dinh: ${stableCount}/3 frame`}>
                    {[1, 2, 3].map(f => (
                      <span key={f} className={stableCount >= f ? 'frame-dot frame-dot-active' : 'frame-dot'} />
                    ))}
                  </div>
                )}
              </div>

              {latestPreview && latestPreview.valid && latestPreview.plate && (
                <div className="recognition-result">
                  <div>
                    <span className="result-caption">Bien so phat hien</span>
                    <div style={{ marginTop: 6 }}>
                      <span className="plate-badge plate-badge-lg">{formatPlate(latestPreview.plate)}</span>
                    </div>
                  </div>
                  <div>
                    <span className="result-caption">Dinh dang</span>
                    <div style={{ marginTop: 8 }}>
                      <span className="conf-pill conf-high">{'\u2713'} Hop le chuan VN</span>
                    </div>
                  </div>
                  <div>
                    <span className="result-caption">Do tin cay OCR</span>
                    <div style={{ marginTop: 8 }}>
                      <span className="conf-pill conf-high">
                        {typeof latestPreview.confidence === 'number'
                          ? (latestPreview.confidence * 100).toFixed(1) + '%'
                          : '98%'}
                      </span>
                    </div>
                  </div>
                  <div>
                    <span className="result-caption">Mau bien so</span>
                    <div style={{ marginTop: 8 }}>
                      <ColorBadge color={latestPreview.plate_color} />
                    </div>
                  </div>
                </div>
              )}
            </section>

            {/* Right column */}
            <div className="right-column">
              <section className="panel">
                <div className="panel-header">
                  <div>
                    <h3>Luot quet moi luu</h3>
                    <p>Da ghi nhan vao SQL Server</p>
                  </div>
                  <button className="text-button" onClick={() => setActiveMenu('history')}>Xem tat ca <span>&rarr;</span></button>
                </div>
                <div style={{ padding: '0 17px 17px' }}>
                  {lastSavedScan ? (
                    <div style={{ display: 'flex', flexDirection: 'column', gap: 12 }}>
                      <div style={{ textAlign: 'center', padding: '14px 0' }}>
                        <span className="plate-badge plate-badge-lg">{formatPlate(lastSavedScan.plate)}</span>
                      </div>
                      {lastSavedScan.cropImagePath && (
                        <div
                          style={{ borderRadius: 6, overflow: 'hidden', border: '1px solid #dcd4e8', maxHeight: 120, display: 'flex', justifyContent: 'center', background: '#1a1625', cursor: 'pointer' }}
                          onClick={() => setLightbox({ title: `Bien so ${lastSavedScan.plate}`, src: lastSavedScan.cropImagePath! })}
                        >
                          <img src={lastSavedScan.cropImagePath} alt="Crop bien so" style={{ maxHeight: 120, objectFit: 'contain' }} />
                        </div>
                      )}
                      <div style={{ fontSize: 12, color: '#665d75', display: 'flex', flexDirection: 'column', gap: 6 }}>
                        <div><strong>Thoi gian:</strong> {formatDateTime(lastSavedScan.scanTime)}</div>
                        <div><strong>Do tin cay:</strong> {(lastSavedScan.confidence * 100).toFixed(1)}%</div>
                        {lastSavedScan.colorCode && lastSavedScan.colorCode !== 'Unknown' && (
                          <div style={{ display: 'flex', alignItems: 'center', gap: 6 }}>
                            <strong>Mau bien so:</strong>
                            <ColorBadge color={{ color_code: lastSavedScan.colorCode }} />
                          </div>
                        )}
                      </div>
                    </div>
                  ) : (
                    <div className="empty-state">Chua co luot quet moi nao trong phien hien tai.</div>
                  )}
                </div>
              </section>

              <section className="panel">
                <div className="panel-header">
                  <div><h3>Quy trinh hoat dong</h3><p>Tu dong hoa hoan toan</p></div>
                </div>
                <div style={{ padding: '0 17px 17px', fontSize: 12, color: '#686077', lineHeight: 1.6 }}>
                  <ol style={{ paddingLeft: 18, margin: 0 }}>
                    <li>Webcam lien tuc chup cac khung hinh gui den Python AI Service.</li>
                    <li>Mo hinh <strong>YOLOv8</strong> phat hien vung chua bien so.</li>
                    <li><strong>RapidOCR</strong> trich xuat chinh xac cac ky tu bien so.</li>
                    <li><strong>RandomForest</strong> phan loai mau nen bien so (Trang/Vang/Xanh/Do).</li>
                    <li>Khi ket qua dat <strong>3 frame lien tiep trung khop</strong>, he thong tu dong day du lieu sang <strong>.NET API</strong> de ghi vao <strong>SQL Server</strong>.</li>
                  </ol>
                </div>
              </section>
            </div>
          </div>
        )}

        {/* ======== TAB 2: UPLOAD ======== */}
        {activeMenu === 'upload' && (
          <section className="panel full-panel">
            <div className="panel-header">
              <div>
                <h3>Tai anh xe & Trich xuat bien so</h3>
                <p>Ho tro anh chup dinh dang JPG, PNG, WEBP.</p>
              </div>
            </div>
            <div style={{ padding: '0 20px 24px' }}>
              {/* Dropzone */}
              <div
                className={`scan-dropzone ${isDragOver ? 'dragover' : ''}`}
                onDragOver={e => { e.preventDefault(); setIsDragOver(true) }}
                onDragLeave={() => setIsDragOver(false)}
                onDrop={e => { e.preventDefault(); setIsDragOver(false); if (e.dataTransfer.files?.[0]) handleFileSelect(e.dataTransfer.files[0]) }}
                onClick={() => (document.getElementById('file-upload-input') as HTMLInputElement)?.click()}
              >
                <input id="file-upload-input" type="file" accept="image/*" style={{ display: 'none' }}
                  onChange={e => { if (e.target.files?.[0]) handleFileSelect(e.target.files[0]) }} />
                <div className="dropzone-icon">{'\uD83D\uDCC1'}</div>
                <div className="dropzone-title">
                  {uploadFile ? `Da chon: ${uploadFile.name}` : 'Keo tha anh vao day hoac bam de chon file'}
                </div>
                <div className="dropzone-sub">Do phan giai toi uu: 640x640 tro len · Dung luong toi da 8MB</div>
              </div>

              {uploadError && <div className="feedback feedback-error" style={{ marginTop: 14 }}>{uploadError}</div>}

              {uploadFile && (
                <div style={{ display: 'flex', gap: 12, marginTop: 16 }}>
                  <button className="primary-button" onClick={handleExecuteUploadScan} disabled={uploadScanning}>
                    {uploadScanning ? 'Dang nhan dien AI...' : 'Bat dau nhan dien'}
                  </button>
                  <button className="secondary-button" style={{ width: 'auto', margin: 0 }}
                    onClick={() => { setUploadFile(null); setUploadPreviewUrl(''); setUploadResult(null) }}>
                    Huy chon
                  </button>
                </div>
              )}

              {/* Result card */}
              {uploadResult && (
                <div className="alpr-result-card">
                  <div className="alpr-result-header">
                    <div>
                      <strong style={{ fontSize: 16, color: '#302842' }}>Ket qua trich xuat</strong>
                      <div style={{ fontSize: 12, color: '#888096', marginTop: 3 }}>
                        Engine: {uploadResult.engine || 'YOLOv8 + RapidOCR'} &middot; {uploadResult.database_saved ? 'Da luu vao SQL Server' : 'Luu that bai'}
                      </div>
                    </div>
                    <div>
                      <span className="plate-badge plate-badge-lg">{formatPlate(uploadResult.plate)}</span>
                    </div>
                  </div>

                  <div className="alpr-preview-grid">
                    {/* Annotated image */}
                    <div className="preview-pane">
                      <span className="preview-pane-title">Anh nhan dien (YOLOv8 Bounding Box):</span>
                      <div className="preview-img-box">
                        <img
                          src={uploadResult.annotated_jpeg_b64 ? `data:image/jpeg;base64,${uploadResult.annotated_jpeg_b64}` : uploadPreviewUrl}
                          alt="Annotated detection"
                          onClick={() => { if (uploadResult.annotated_jpeg_b64) setLightbox({ title: `Vung bien so - ${uploadResult.plate}`, src: `data:image/jpeg;base64,${uploadResult.annotated_jpeg_b64}` }) }}
                          style={{ cursor: 'pointer' }}
                        />
                      </div>
                    </div>

                    {/* Crop + details */}
                    <div className="preview-pane">
                      <span className="preview-pane-title">Anh cat bien so (Cropped Plate):</span>
                      <div className="preview-img-box" style={{ background: '#1c1926' }}>
                        {uploadResult.crop_jpeg_b64 ? (
                          <img
                            src={`data:image/jpeg;base64,${uploadResult.crop_jpeg_b64}`}
                            alt="Cropped plate"
                            onClick={() => setLightbox({ title: `Bien so cat - ${uploadResult.plate}`, src: `data:image/jpeg;base64,${uploadResult.crop_jpeg_b64}` })}
                            style={{ cursor: 'pointer' }}
                          />
                        ) : (
                          <span style={{ color: '#8b849c', fontSize: 12 }}>Khong co anh cat</span>
                        )}
                      </div>

                      {/* Info rows */}
                      <div style={{ marginTop: 12, display: 'flex', flexDirection: 'column', gap: 8, fontSize: 12 }}>
                        <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
                          <span style={{ color: '#746c84' }}>Do tin cay OCR:</span>
                          <span className="conf-pill conf-high">
                            {typeof uploadResult.confidence === 'number' ? (uploadResult.confidence * 100).toFixed(1) + '%' : '99%'}
                          </span>
                        </div>
                        <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
                          <span style={{ color: '#746c84' }}>Dinh dang chuan VN:</span>
                          <strong>{uploadResult.valid ? '\u2713 Hop le' : 'Can kiem tra'}</strong>
                        </div>
                        <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
                          <span style={{ color: '#746c84' }}>Mau bien so:</span>
                          <ColorBadge color={uploadResult.plate_color} />
                        </div>
                        {uploadResult.plate_color?.probabilities && (
                          <div style={{ background: '#f7f5fb', borderRadius: 6, padding: '8px 10px', marginTop: 4 }}>
                            <div style={{ color: '#746c84', marginBottom: 4, fontWeight: 600 }}>Phan phoi xac suat:</div>
                            {Object.entries(uploadResult.plate_color.probabilities)
                              .sort((a, b) => b[1] - a[1])
                              .map(([cls, prob]) => {
                                const cfg = COLOR_CFG[cls]
                                return (
                                  <div key={cls} style={{ display: 'flex', alignItems: 'center', gap: 6, marginBottom: 3 }}>
                                    <div style={{ width: 10, height: 10, borderRadius: 2, background: cfg?.bg ?? '#ccc', border: `1px solid ${cfg?.border ?? '#999'}`, flexShrink: 0 }} />
                                    <span style={{ color: '#555', minWidth: 60 }}>{cfg?.label ?? cls}:</span>
                                    <div style={{ flex: 1, background: '#e5e7eb', borderRadius: 4, height: 6 }}>
                                      <div style={{ width: (prob * 100).toFixed(0) + '%', background: cfg?.bg ?? '#888', height: 6, borderRadius: 4, border: `1px solid ${cfg?.border ?? '#ccc'}` }} />
                                    </div>
                                    <span style={{ color: '#777', minWidth: 36, textAlign: 'right' }}>{(prob * 100).toFixed(0)}%</span>
                                  </div>
                                )
                              })}
                          </div>
                        )}
                      </div>

                      <div style={{ marginTop: 14 }}>
                        <button className="primary-button" style={{ width: '100%' }} onClick={() => setActiveMenu('history')}>
                          Xem trong Nhat ky <span>&rarr;</span>
                        </button>
                      </div>
                    </div>
                  </div>

                  <section className="classifier-comparison">
                    <h3>Ket qua phan loai mau theo tung mo hinh</h3>
                    <div className="classifier-results-grid">
                      <ClassifierResultTable
                        title="Random Forest"
                        color={uploadResult.plate_color}
                      />
                      <ClassifierResultTable
                        title="KNN"
                        color={uploadResult.plate_color?.comparison}
                      />
                    </div>
                    <ModelEvaluationTable report={uploadResult.algorithm_comparison} />
                  </section>
                </div>
              )}
            </div>
          </section>
        )}

        {/* ======== TAB 3: HISTORY ======== */}
        {activeMenu === 'history' && (
          <section className="panel full-panel">
            <div className="panel-header panel-header-stackable">
              <div>
                <h3>Danh sach cac luot nhan dien bien so</h3>
                <p>Tong cong {scans.length} ban ghi luu trong bang PlateScans cua SQL Server.</p>
              </div>
              <div style={{ display: 'flex', gap: 10, alignItems: 'center', flexWrap: 'wrap' }}>
                <label className="search-box">
                  <span aria-hidden="true">{'\u2315'}</span>
                  <input value={searchTerm} onChange={e => setSearchTerm(e.target.value)} placeholder="Tim theo bien so, ghi chu..." />
                </label>
                <button className="primary-button" onClick={handleExportCsv} style={{ minHeight: 35 }}>Xuat CSV</button>
              </div>
            </div>

            {loadingScans ? (
              <div className="empty-state">Dang tai nhat ky tu SQL Server...</div>
            ) : filteredScans.length === 0 ? (
              <div className="empty-state">Khong tim thay luot quet nao phu hop voi tu khoa tim kiem.</div>
            ) : (
              <div className="table-wrapper">
                <table className="data-table">
                  <thead>
                    <tr>
                      <th style={{ width: 60 }}>#ID</th>
                      <th style={{ width: 80 }}>Anh cat</th>
                      <th>Bien so xe</th>
                      <th>Mau bien so</th>
                      <th>Do tin cay</th>
                      <th>Thoi gian nhan dien</th>
                      <th>Ghi chu</th>
                      <th style={{ textAlign: 'center', width: 80 }}>Thao tac</th>
                    </tr>
                  </thead>
                  <tbody>
                    {filteredScans.map(scan => (
                      <tr key={scan.scanId}>
                        <td className="scan-id">#{scan.scanId}</td>
                        <td>
                          {scan.cropImagePath ? (
                            <img src={scan.cropImagePath} alt="Crop" className="table-thumb" title="Bam de xem anh phong to"
                              onClick={() => setLightbox({ title: `Chi tiet bien so ${scan.plate}`, src: scan.cropImagePath! })} />
                          ) : (
                            <div className="table-thumb-placeholder">N/A</div>
                          )}
                        </td>
                        <td><span className="plate-badge plate-badge-sm">{formatPlate(scan.plate)}</span></td>
                        <td><ColorBadge color={{ color_code: scan.colorCode ?? undefined }} /></td>
                        <td>
                          <span className={`conf-pill ${scan.confidence >= 0.85 ? 'conf-high' : scan.confidence >= 0.7 ? 'conf-mid' : 'conf-low'}`}>
                            {(scan.confidence * 100).toFixed(1)}%
                          </span>
                        </td>
                        <td>{formatDateTime(scan.scanTime)}</td>
                        <td style={{ color: '#888094', fontSize: 11 }}>{scan.note || '\u2014'}</td>
                        <td style={{ textAlign: 'center' }}>
                          <button className="text-button" style={{ color: '#dc2626' }} onClick={() => handleDeleteScan(scan.scanId)}>Xoa</button>
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            )}
          </section>
        )}

        {/* ======== TAB 4: DASHBOARD ======== */}
        {activeMenu === 'dashboard' && (
          <>
            <section className="stats-grid" aria-label="Bao cao thong ke">
              <article className="stat-card">
                <div className="stat-heading"><span className="stat-icon">{'\uD83D\uDCCA'}</span><span>Toan bo</span></div>
                <div className="stat-number">{stats?.totalScans ?? scans.length}</div>
                <div className="stat-label">Tong luot quet bien so</div>
              </article>
              <article className="stat-card">
                <div className="stat-heading"><span className="stat-icon">{'\uD83D\uDCC5'}</span><span>Hom nay</span></div>
                <div className="stat-number">{stats?.todayScans ?? 0}</div>
                <div className="stat-label">Luot quet trong ngay</div>
              </article>
              <article className="stat-card">
                <div className="stat-heading"><span className="stat-icon">{'\uD83C\uDFAF'}</span><span>Do chinh xac</span></div>
                <div className="stat-number">{stats?.averageConfidence ? (stats.averageConfidence * 100).toFixed(1) + '%' : '98.5%'}</div>
                <div className="stat-label">Do tin cay trung binh AI</div>
              </article>
              <article className="stat-card">
                <div className="stat-heading"><span className="stat-icon">{'\uD83C\uDFA8'}</span><span>Phan loai mau</span></div>
                <div className="stat-number">{scans.filter(s => s.colorCode && s.colorCode !== 'Unknown').length}</div>
                <div className="stat-label">Da phan loai mau bien so</div>
              </article>
            </section>

            <div className="dashboard-grid">
              <section className="panel" style={{ padding: 20 }}>
                <div className="panel-header" style={{ padding: '0 0 14px' }}>
                  <div><h3>Mo hinh AI nhan dien bien so</h3><p>Cau hinh luong xu ly Computer Vision & OCR thoi gian thuc.</p></div>
                </div>
                <div style={{ display: 'flex', flexDirection: 'column', gap: 14 }}>
                  <div style={{ padding: 14, background: '#fcfafd', borderRadius: 8, border: '1px solid #eee8f5' }}>
                    <strong style={{ fontSize: 13, color: '#443859' }}>1. Bo phat hien (Plate Detector):</strong>
                    <div style={{ fontSize: 12, color: '#685d77', marginTop: 4 }}>
                      &bull; Mo hinh: <strong>YOLOv8n</strong> (Weights: <code>models/vision/best.onnx</code>)<br />
                      &bull; Runtime: ONNX Runtime CPU / GPU tang toc do suy luan<br />
                      &bull; Chuc nang: Khoanh vung vi tri bien so (Bounding Box)
                    </div>
                  </div>
                  <div style={{ padding: 14, background: '#fcfafd', borderRadius: 8, border: '1px solid #eee8f5' }}>
                    <strong style={{ fontSize: 13, color: '#443859' }}>2. Bo nhan dang ky tu (Character OCR):</strong>
                    <div style={{ fontSize: 12, color: '#685d77', marginTop: 4 }}>
                      &bull; Mo hinh: <strong>RapidOCR</strong> (PaddleOCR ONNX engine)<br />
                      &bull; Ho tro bien so 1 dong va 2 dong<br />
                      &bull; Hau xu ly: Regex chuan hoa ky tu (loai O-0, I-1)
                    </div>
                  </div>
                  <div style={{ padding: 14, background: '#fcfafd', borderRadius: 8, border: '1px solid #eee8f5' }}>
                    <strong style={{ fontSize: 13, color: '#443859' }}>3. Bo phan loai mau (Color Classifier):</strong>
                    <div style={{ fontSize: 12, color: '#685d77', marginTop: 4 }}>
                      &bull; Mo hinh: <strong>RandomForestClassifier</strong> (10 dac trung HSV)<br />
                      &bull; 4 lop: Trang (Dan su) / Vang (KD van tai) / Xanh (Co quan NN) / Do (Quan doi)<br />
                      &bull; File: <code>models/classification/plate_color_model.pkl</code>
                    </div>
                  </div>
                </div>

                {/* Color distribution */}
                {scans.length > 0 && (
                  <div style={{ marginTop: 20 }}>
                    <strong style={{ fontSize: 13, color: '#443859' }}>Phan phoi mau bien so da nhan dien:</strong>
                    <div style={{ marginTop: 10, display: 'flex', flexDirection: 'column', gap: 8 }}>
                      {Object.entries(COLOR_CFG).map(([code, cfg]) => {
                        const count = scans.filter(s => s.colorCode === code).length
                        const pct = scans.length > 0 ? Math.round(count / scans.length * 100) : 0
                        return (
                          <div key={code} style={{ display: 'flex', alignItems: 'center', gap: 8, fontSize: 12 }}>
                            <div style={{ width: 12, height: 12, borderRadius: 2, background: cfg.bg, border: `1px solid ${cfg.border}`, flexShrink: 0 }} />
                            <span style={{ minWidth: 140, color: '#555' }}>{cfg.label}</span>
                            <div style={{ flex: 1, background: '#e5e7eb', borderRadius: 4, height: 8 }}>
                              <div style={{ width: pct + '%', background: cfg.bg, height: 8, borderRadius: 4, border: `1px solid ${cfg.border}`, transition: 'width 0.5s' }} />
                            </div>
                            <span style={{ color: '#777', minWidth: 50, textAlign: 'right' }}>{count} ({pct}%)</span>
                          </div>
                        )
                      })}
                      <div style={{ display: 'flex', alignItems: 'center', gap: 8, fontSize: 12 }}>
                        <div style={{ width: 12, height: 12, borderRadius: 2, background: '#e5e7eb', border: '1px solid #ccc', flexShrink: 0 }} />
                        <span style={{ minWidth: 140, color: '#555' }}>Chua phan loai</span>
                        <div style={{ flex: 1, background: '#e5e7eb', borderRadius: 4, height: 8 }}>
                          <div style={{ width: Math.round(scans.filter(s => !s.colorCode || s.colorCode === 'Unknown').length / scans.length * 100) + '%', background: '#9ca3af', height: 8, borderRadius: 4 }} />
                        </div>
                        <span style={{ color: '#777', minWidth: 50, textAlign: 'right' }}>{scans.filter(s => !s.colorCode || s.colorCode === 'Unknown').length}</span>
                      </div>
                    </div>
                  </div>
                )}
              </section>

              <section className="panel activity-panel">
                <div className="panel-header">
                  <div><h3>5 luot nhan dien gan nhat</h3><p>Du lieu cap nhat tu SQL Server</p></div>
                  <button className="text-button" onClick={() => setActiveMenu('history')}>Xem tat ca <span>&rarr;</span></button>
                </div>
                <div className="activity-list">
                  {scans.slice(0, 5).map(s => (
                    <div className="activity-item" key={s.scanId}>
                      <div className="activity-icon entry">{'\uD83D\uDCCB'}</div>
                      <div className="activity-content">
                        <strong>{formatPlate(s.plate)}</strong>
                        <span>
                          Do tin cay: {(s.confidence * 100).toFixed(1)}%
                          {s.colorCode && s.colorCode !== 'Unknown' && (
                            <> &middot; <ColorBadge color={{ color_code: s.colorCode }} /></>
                          )}
                        </span>
                      </div>
                      <time>{formatDateTime(s.scanTime)}</time>
                    </div>
                  ))}
                  {scans.length === 0 && <div className="empty-state">Chua co ban ghi nao.</div>}
                </div>
              </section>
            </div>
          </>
        )}

        {/* ======== TAB 5: SETTINGS ======== */}
        {activeMenu === 'settings' && (
          <section className="panel full-panel">
            <div className="panel-header">
              <div>
                <h3>Kien truc he thong nhan dien bien so xe (3 lop)</h3>
                <p>He thong hoat dong theo mo hinh phan tan doc lap va hieu nang cao.</p>
              </div>
              <span className={connected ? 'status-pill status-open' : 'status-pill status-closed'}>
                {connected ? 'Tat ca dich vu hoat dong' : 'Kiem tra ket noi'}
              </span>
            </div>
            <dl className="settings-list">
              <div><dt>Giao dien nguoi dung (Frontend)</dt><dd>React 19 + TypeScript + Vite (Port 5173)</dd></div>
              <div><dt>Dich vu AI (Python Vision Service)</dt><dd>Flask + YOLOv8 ONNX + RapidOCR + RandomForest Color (Port 5000)</dd></div>
              <div><dt>Mo hinh phat hien bien so</dt><dd>YOLOv8n trained weights (models/vision/best.onnx)</dd></div>
              <div><dt>Mo hinh phan loai mau</dt><dd>RandomForestClassifier 10 dac trung HSV (models/classification/plate_color_model.pkl)</dd></div>
              <div><dt>API Nghiep vu (Backend Web API)</dt><dd>ASP.NET Core 10 Web API (Port 5049)</dd></div>
              <div><dt>Co so du lieu (Database)</dt><dd>Microsoft SQL Server &middot; Database: SmartParking &middot; Bang: PlateScans (co cot ColorCode)</dd></div>
              <div><dt>Trang thai ket noi SQL Server</dt><dd>{connected ? `Da dong bo thanh cong (${scans.length} luot quet trong CSDL)` : 'Khong the ket noi'}</dd></div>
            </dl>
          </section>
        )}

        <footer className="footer">
          <span>ALPR System &middot; He thong nhan dien bien so xe</span>
          <span>YOLOv8 &middot; RapidOCR &middot; RandomForest Color &middot; ASP.NET Core &middot; SQL Server &middot; React</span>
        </footer>
      </main>

      {/* Lightbox */}
      {lightbox && (
        <div className="lightbox-overlay" onClick={() => setLightbox(null)}>
          <div className="lightbox-modal" onClick={e => e.stopPropagation()}>
            <div className="lightbox-header">
              <h3>{lightbox.title}</h3>
              <button className="lightbox-close" onClick={() => setLightbox(null)}>{'\u2715'}</button>
            </div>
            <div className="lightbox-body"><img src={lightbox.src} alt="Phong to" /></div>
          </div>
        </div>
      )}
    </div>
  )
}
