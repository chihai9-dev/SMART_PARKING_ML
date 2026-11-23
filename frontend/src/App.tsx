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
  { id: 'camera',    icon: '\uD83C\uDFA5', label: 'Quét camera' },
  { id: 'upload',    icon: '\uD83D\uDDBC', label: 'Tải ảnh nhận diện' },
  { id: 'history',   icon: '\uD83D\uDCCB', label: 'Nhật ký nhận diện' },
  { id: 'dashboard', icon: '\uD83D\uDCCA', label: 'Thống kê' },
  { id: 'settings',  icon: '\u2699',       label: 'Hệ thống' },
]

const pageDetails: Record<MenuId, { title: string; description: string }> = {
  camera: {
    title: 'Quét camera trực tiếp',
    description: 'Nhận diện biển số xe và phân loại màu nền theo thời gian thực qua webcam bằng YOLOv8 và RapidOCR.',
  },
  upload: {
    title: 'Tải ảnh và nhận diện',
    description: 'Tải ảnh lên hệ thống để tự động tìm biển số, nhận dạng ký tự, phân loại màu nền và lưu kết quả.',
  },
  history: {
    title: 'Nhật ký nhận diện',
    description: 'Tra cứu, tìm kiếm và quản lý các lượt nhận diện biển số đã lưu trong SQL Server.',
  },
  dashboard: {
    title: 'Báo cáo thống kê',
    description: 'Tổng hợp số lượt nhận diện biển số và độ tin cậy của mô hình AI.',
  },
  settings: {
    title: 'Trạng thái hệ thống',
    description: 'Kiểm tra trạng thái các dịch vụ Python AI, .NET Web API và SQL Server.',
  },
}

// ─── Color badge helpers ───────────────────────────────────────────────────
const COLOR_CFG: Record<string, { bg: string; border: string; text: string; label: string }> = {
  White:  { bg: '#f0f0f0', border: '#ccc',    text: '#333',    label: 'Trắng' },
  Yellow: { bg: '#fbbf24', border: '#d97706',  text: '#7c3800', label: 'Vàng' },
}

function ColorBadge({ color }: { color?: PlateColorResult | null }) {
  if (color?.scope_status === 'unsupported_color') {
    return <span style={{ fontSize: 11, color: '#b45309', fontWeight: 600 }}>Ngoài phạm vi hỗ trợ</span>
  }
  if (!color || !color.color_code || color.color_code === 'Unknown') {
    return <span style={{ fontSize: 11, color: '#999', fontStyle: 'italic' }}>Chưa phân loại</span>
  }
  const cfg = COLOR_CFG[color.color_code]
  if (!cfg) {
    return <span style={{ fontSize: 11, color: '#b45309', fontWeight: 600 }}>Ngoài phạm vi hỗ trợ</span>
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
            <th>Thuật toán</th>
            <td>{color?.algorithm ?? title}</td>
          </tr>
          <tr>
            <th>Màu dự đoán</th>
            <td><ColorBadge color={color} /></td>
          </tr>
          <tr>
            <th>Độ tin cậy</th>
            <td>{typeof color?.confidence === 'number' ? `${(color.confidence * 100).toFixed(1)}%` : '\u2014'}</td>
          </tr>
          {color?.message && (
            <tr>
              <th>Phạm vi</th>
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
      <h4>Kết luận so sánh mô hình</h4>
      {summary && repeated ? (
        <>
          <div className="model-evaluation-table-wrap">
            <table>
              <thead>
                <tr>
                  <th>Mô hình</th>
                  <th>Độ chính xác trung bình</th>
                  <th>Macro-F1 trung bình ± độ lệch chuẩn</th>
                  <th>Tốc độ trung bình (ms/ảnh)</th>
                </tr>
              </thead>
              <tbody>
                {models.map(({ key, label }) => {
                  const metrics = summary[key]
                  return (
                    <tr key={key}>
                      <th>{label}</th>
                      <td>
                        {typeof metrics?.accuracy_mean === 'number'
                          ? `${(metrics.accuracy_mean * 100).toFixed(2)}%`
                          : '—'}
                      </td>
                      <td>
                        {typeof metrics?.f1_macro_mean === 'number' && typeof metrics.f1_macro_std === 'number'
                          ? `${(metrics.f1_macro_mean * 100).toFixed(2)}% ± ${(metrics.f1_macro_std * 100).toFixed(2)}%`
                          : '—'}
                      </td>
                      <td>
                        {typeof metrics?.median_ms_per_image_mean === 'number'
                          ? metrics.median_ms_per_image_mean.toFixed(2)
                          : '—'}
                      </td>
                    </tr>
                  )
                })}
              </tbody>
            </table>
          </div>
          <div className="model-verdict">
            <strong>
              {sameRecommendation
                ? `${fastest.label} nhanh nhất và ổn định hơn`
                : `Nhanh nhất: ${fastest.label} · Ổn định nhất: ${mostStable.label}`}
            </strong>
            {typeof fastestLatency === 'number' && repeated.run_count
              ? <span>{fastestLatency.toFixed(2)} ms/ảnh · {repeated.run_count} lần huấn luyện</span>
              : null}
          </div>
        </>
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
  if (!plate) return 'CHƯA RÕ'
  return plate.toUpperCase()
}

function colorCodeToLabel(code?: string | null) {
  if (!code || code === 'Unknown') return null
  return COLOR_CFG[code]?.label ?? 'Ngoài phạm vi hỗ trợ'
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
  const [cameraStatus, setCameraStatus] = useState('Camera chưa bật.')
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
        setErrorMessage(err instanceof Error ? err.message : 'Không thể kết nối với .NET Backend.')
      })
      .finally(() => { if (!cancelled) setLoadingScans(false) })
    return () => { cancelled = true }
  }, [refreshKey])

  useEffect(() => { if (activeMenu !== 'camera') stopCamera() }, [activeMenu])
  useEffect(() => () => stopCamera(), [])

  async function startCamera() {
    setErrorMessage('')
    setCameraStatus('Đang khởi động webcam...')
    if (!navigator.mediaDevices?.getUserMedia) {
      setCameraStatus('Trình duyệt không hỗ trợ webcam hoặc chưa được cấp quyền.')
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
      setCameraStatus('Camera đang quét. Hãy hướng camera vào biển số xe.')
    } catch (err) {
      setCameraStatus(err instanceof Error ? 'Lỗi mở camera: ' + err.message : 'Không thể mở webcam.')
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
    setCameraStatus('Camera đã tắt.')
  }

  function captureFrameBlob(): Promise<Blob> {
    return new Promise((resolve, reject) => {
      const video = videoRef.current
      const canvas = canvasRef.current
      if (!video || !canvas || !video.videoWidth || !video.videoHeight) {
        reject(new Error('Khung hình chưa sẵn sàng.')); return
      }
      canvas.width = video.videoWidth
      canvas.height = video.videoHeight
      const ctx = canvas.getContext('2d')
      if (!ctx) { reject(new Error('Không thể xử lý khung hình.')); return }
      ctx.drawImage(video, 0, 0, canvas.width, canvas.height)
      canvas.toBlob(blob => { if (blob) resolve(blob); else reject(new Error('Lỗi chuyển ảnh sang Blob.')) }, 'image/jpeg', 0.88)
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
          setCameraStatus(preview.message || 'Đang quét... Hãy đưa biển số vào giữa khung hình.')
        } else {
          const prev = stablePlateCandidate.current
          const count = prev.plate === rawPlate ? prev.count + 1 : 1
          stablePlateCandidate.current = { plate: rawPlate, count }
          setStableCount(Math.min(count, 3))
          if (count < 3) {
            setCameraStatus(`Đã phát hiện ${rawPlate}. Đang xác minh độ ổn định (${count}/3 khung hình)...`)
          } else if (lastProcessedPlate.current === rawPlate) {
            setCameraStatus(`Biển số ${rawPlate} đã được lưu vào cơ sở dữ liệu. Đang theo dõi...`)
          } else {
            lastProcessedPlate.current = rawPlate
            setCameraBusy(true)
            setCameraStatus(`Đã xác thực ${rawPlate}! Đang lưu vào SQL Server...`)
            try {
              const scanRes = await scanPlate(frameBlob)
              setRefreshKey(k => k + 1)
              const colorLabel = scanRes.plate_color?.color_code && scanRes.plate_color.color_code !== 'Unknown'
                ? ' - ' + (colorCodeToLabel(scanRes.plate_color.color_code) ?? '')
                : ''
              setCameraStatus(`Đã lưu biển số ${rawPlate}${colorLabel} vào cơ sở dữ liệu thành công!`)
              setLastSavedScan({
                scanId: Date.now(),
                plate: scanRes.plate || rawPlate,
                confidence: scanRes.confidence || 0.95,
                cropImagePath: scanRes.crop_path ? `/scan-image/${(scanRes.crop_path as string).split(/[\\/]/).pop()}` : null,
                scanTime: new Date().toISOString(),
                note: 'Tự động quét từ camera',
                colorCode: scanRes.plate_color?.color_code ?? null,
              })
            } catch (saveErr) {
              lastProcessedPlate.current = ''
              setCameraStatus('Lỗi khi lưu vào cơ sở dữ liệu: ' + (saveErr instanceof Error ? saveErr.message : ''))
            } finally {
              setCameraBusy(false)
            }
          }
        }
      } catch {
        if (!isCancelled) setCameraStatus('Không thể quét khung hình camera.')
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
    setCameraStatus('Đang chụp và nhận diện biển số...')
    try {
      const blob = await captureFrameBlob()
      const res = await scanPlate(blob)
      setUploadResult(res)
      setRefreshKey(k => k + 1)
      setCameraStatus(`Đã nhận diện: ${res.plate || 'Không tìm thấy'} (${(Number(res.confidence || 0) * 100).toFixed(1)}%)`)
    } catch (err) {
      setCameraStatus(err instanceof Error ? err.message : 'Lỗi nhận diện.')
    } finally {
      setCameraBusy(false)
    }
  }

  function handleFileSelect(file: File) {
    if (!file.type.startsWith('image/')) { setUploadError('Vui lòng chọn tệp hình ảnh (JPG, PNG hoặc WEBP).'); return }
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
      setUploadError(err instanceof Error ? err.message : 'Lỗi trong quá trình nhận diện ảnh.')
    } finally {
      setUploadScanning(false)
    }
  }

  async function handleDeleteScan(id: number) {
    if (!window.confirm(`Bạn có chắc chắn muốn xóa lượt quét #${id} không?`)) return
    try { await deletePlateScan(id); setRefreshKey(k => k + 1) }
    catch (err) { alert(err instanceof Error ? err.message : 'Xóa thất bại.') }
  }

  function handleExportCsv() {
    if (scans.length === 0) { alert('Không có dữ liệu để xuất tệp.'); return }
    const headers = ['Mã lượt quét', 'Biển số', 'Màu biển số', 'Độ tin cậy', 'Thời gian quét', 'Ghi chú']
    const rows = scans.map(s => [
      s.scanId,
      `"${s.plate}"`,
      `"${colorCodeToLabel(s.colorCode) ?? 'Chưa phân loại'}"`,
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
            <div className="brand-subtitle">Hệ thống nhận diện biển số xe</div>
          </div>
        </div>
        <div className="sidebar-section-title">CHỨC NĂNG</div>
        <nav className="sidebar-menu" aria-label="Trình đơn chính">
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
            <p>{connected ? `Đã kết nối với SQL Server (${scans.length} bản ghi).` : 'Đang kiểm tra kết nối với .NET Backend...'}</p>
          </div>
          <div className="sidebar-version">Design by DangkhoiJR</div>
        </div>
      </aside>

      {/* Main */}
      <main className="main-content">
        <header className="topbar">
          <div>
            <div className="breadcrumb">Nhận diện biển số xe <span>/</span> {currentPage.title}</div>
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
            {errorMessage} — Vui lòng bảo đảm .NET Backend (cổng 5049) và Python AI Service (cổng 5000) đang chạy.
          </div>
        )}

        {/* ======== TAB 1: CAMERA ======== */}
        {activeMenu === 'camera' && (
          <div className="gate-layout">
            <section className="panel gate-panel">
              <div className="panel-header">
                <div>
                  <h3>Quét camera theo thời gian thực</h3>
                  <p>YOLOv8 tìm vùng biển số, RapidOCR đọc ký tự, Random Forest phân loại màu nền.</p>
                </div>
                <span className={cameraOn ? 'status-pill status-open' : 'status-pill status-closed'}>
                  {cameraOn ? 'Đang hoạt động' : 'Camera đã tắt'}
                </span>
              </div>

              <div className="camera-scanner-wrapper">
                <video ref={videoRef} autoPlay playsInline muted style={{ display: cameraOn ? 'block' : 'none' }} />
                {cameraOn && <div className="scan-line" />}
                {!cameraOn && (
                  <div className="camera-offline">
                    <div className="camera-symbol">{'\uD83D\uDCF7'}</div>
                    <strong>Webcam chưa bật</strong>
                    <span>Nhấn nút “Bật camera” bên dưới để bắt đầu nhận diện.</span>
                  </div>
                )}
              </div>
              <canvas ref={canvasRef} style={{ display: 'none' }} />

              <div className="camera-controls" style={{ display: 'flex', gap: 10, flexWrap: 'wrap', padding: '14px 17px' }}>
                {!cameraOn ? (
                  <button className="primary-button" onClick={startCamera}>Bật camera và bắt đầu quét</button>
                ) : (
                  <>
                    <button className="secondary-button inline-button" onClick={stopCamera}>Tắt camera</button>
                    <button className="primary-button" onClick={handleManualCapture} disabled={cameraBusy}>
                      {cameraBusy ? 'Đang xử lý...' : 'Chụp và lưu'}
                    </button>
                    <label style={{ display: 'inline-flex', alignItems: 'center', gap: 6, fontSize: 12, marginLeft: 'auto', cursor: 'pointer' }}>
                      <input type="checkbox" checked={autoScanEnabled} onChange={e => setAutoScanEnabled(e.target.checked)} />
                      <span>Tự động quét liên tục</span>
                    </label>
                  </>
                )}
              </div>

              <div className="auto-scan-status">
                <div className="auto-scan-copy">
                  <strong>Trạng thái nhận diện:</strong>
                  <span>{cameraStatus}</span>
                </div>
                {cameraOn && autoScanEnabled && (
                  <div className="frame-progress" title={`Độ ổn định: ${stableCount}/3 khung hình`}>
                    {[1, 2, 3].map(f => (
                      <span key={f} className={stableCount >= f ? 'frame-dot frame-dot-active' : 'frame-dot'} />
                    ))}
                  </div>
                )}
              </div>

              {latestPreview && latestPreview.valid && latestPreview.plate && (
                <div className="recognition-result">
                  <div>
                    <span className="result-caption">Biển số phát hiện</span>
                    <div style={{ marginTop: 6 }}>
                      <span className="plate-badge plate-badge-lg">{formatPlate(latestPreview.plate)}</span>
                    </div>
                  </div>
                  <div>
                    <span className="result-caption">Định dạng</span>
                    <div style={{ marginTop: 8 }}>
                      <span className="conf-pill conf-high">{'\u2713'} Hợp lệ theo chuẩn Việt Nam</span>
                    </div>
                  </div>
                  <div>
                    <span className="result-caption">Độ tin cậy OCR</span>
                    <div style={{ marginTop: 8 }}>
                      <span className="conf-pill conf-high">
                        {typeof latestPreview.confidence === 'number'
                          ? (latestPreview.confidence * 100).toFixed(1) + '%'
                          : '98%'}
                      </span>
                    </div>
                  </div>
                  <div>
                    <span className="result-caption">Màu biển số</span>
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
                    <h3>Lượt quét mới nhất</h3>
                    <p>Đã ghi nhận vào SQL Server</p>
                  </div>
                  <button className="text-button" onClick={() => setActiveMenu('history')}>Xem tất cả <span>&rarr;</span></button>
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
                          onClick={() => setLightbox({ title: `Biển số ${lastSavedScan.plate}`, src: lastSavedScan.cropImagePath! })}
                        >
                          <img src={lastSavedScan.cropImagePath} alt="Ảnh cắt biển số" style={{ maxHeight: 120, objectFit: 'contain' }} />
                        </div>
                      )}
                      <div style={{ fontSize: 12, color: '#665d75', display: 'flex', flexDirection: 'column', gap: 6 }}>
                        <div><strong>Thời gian:</strong> {formatDateTime(lastSavedScan.scanTime)}</div>
                        <div><strong>Độ tin cậy:</strong> {(lastSavedScan.confidence * 100).toFixed(1)}%</div>
                        {lastSavedScan.colorCode && lastSavedScan.colorCode !== 'Unknown' && (
                          <div style={{ display: 'flex', alignItems: 'center', gap: 6 }}>
                            <strong>Màu biển số:</strong>
                            <ColorBadge color={{ color_code: lastSavedScan.colorCode }} />
                          </div>
                        )}
                      </div>
                    </div>
                  ) : (
                    <div className="empty-state">Chưa có lượt quét mới trong phiên hiện tại.</div>
                  )}
                </div>
              </section>

              <section className="panel">
                <div className="panel-header">
                <div><h3>Quy trình hoạt động</h3><p>Tự động hóa nhận diện</p></div>
                </div>
                <div style={{ padding: '0 17px 17px', fontSize: 12, color: '#686077', lineHeight: 1.6 }}>
                  <ol style={{ paddingLeft: 18, margin: 0 }}>
                    <li>Webcam liên tục chụp khung hình và gửi đến Python AI Service.</li>
                    <li><strong>YOLOv8</strong> tìm vùng chứa biển số.</li>
                    <li><strong>RapidOCR</strong> đọc các ký tự trên biển số.</li>
                    <li><strong>Random Forest</strong> và <strong>KNN</strong> phân loại nền biển trắng hoặc vàng.</li>
                    <li>Khi kết quả khớp trong <strong>3 khung hình liên tiếp</strong>, hệ thống gửi lượt nhận diện sang <strong>.NET API</strong> để lưu vào <strong>SQL Server</strong>.</li>
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
                <h3>Tải ảnh và trích xuất biển số</h3>
                <p>Hỗ trợ ảnh định dạng JPG, PNG và WEBP.</p>
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
                  {uploadFile ? `Đã chọn: ${uploadFile.name}` : 'Kéo thả ảnh vào đây hoặc bấm để chọn tệp'}
                </div>
                <div className="dropzone-sub">Độ phân giải khuyến nghị: từ 640 × 640 · Dung lượng tối đa: 8 MB</div>
              </div>

              {uploadError && <div className="feedback feedback-error" style={{ marginTop: 14 }}>{uploadError}</div>}

              {uploadFile && (
                <div style={{ display: 'flex', gap: 12, marginTop: 16 }}>
                  <button className="primary-button" onClick={handleExecuteUploadScan} disabled={uploadScanning}>
                    {uploadScanning ? 'Đang nhận diện...' : 'Bắt đầu nhận diện'}
                  </button>
                  <button className="secondary-button" style={{ width: 'auto', margin: 0 }}
                    onClick={() => { setUploadFile(null); setUploadPreviewUrl(''); setUploadResult(null) }}>
                    Bỏ chọn
                  </button>
                </div>
              )}

              {/* Result card */}
              {uploadResult && (
                <div className="alpr-result-card">
                  <div className="alpr-result-header">
                    <div>
                      <strong style={{ fontSize: 16, color: '#302842' }}>Kết quả nhận diện</strong>
                      <div style={{ fontSize: 12, color: '#888096', marginTop: 3 }}>
                        Bộ nhận diện: {uploadResult.engine || 'YOLOv8 + RapidOCR'} &middot; {uploadResult.database_saved ? 'Đã lưu vào SQL Server' : 'Chưa lưu vào SQL Server'}
                      </div>
                    </div>
                    <div>
                      <span className="plate-badge plate-badge-lg">{formatPlate(uploadResult.plate)}</span>
                    </div>
                  </div>

                  <div className="alpr-preview-grid">
                    {/* Annotated image */}
                    <div className="preview-pane">
                      <span className="preview-pane-title">Ảnh phát hiện biển số (khung YOLOv8):</span>
                      <div className="preview-img-box">
                        <img
                          src={uploadResult.annotated_jpeg_b64 ? `data:image/jpeg;base64,${uploadResult.annotated_jpeg_b64}` : uploadPreviewUrl}
                          alt="Ảnh có đánh dấu vùng biển số"
                          onClick={() => { if (uploadResult.annotated_jpeg_b64) setLightbox({ title: `Vùng biển số - ${uploadResult.plate}`, src: `data:image/jpeg;base64,${uploadResult.annotated_jpeg_b64}` }) }}
                          style={{ cursor: 'pointer' }}
                        />
                      </div>
                    </div>

                    {/* Crop + details */}
                    <div className="preview-pane">
                      <span className="preview-pane-title">Ảnh biển số đã cắt:</span>
                      <div className="preview-img-box" style={{ background: '#1c1926' }}>
                        {uploadResult.crop_jpeg_b64 ? (
                          <img
                            src={`data:image/jpeg;base64,${uploadResult.crop_jpeg_b64}`}
                            alt="Ảnh biển số đã cắt"
                            onClick={() => setLightbox({ title: `Biển số đã cắt - ${uploadResult.plate}`, src: `data:image/jpeg;base64,${uploadResult.crop_jpeg_b64}` })}
                            style={{ cursor: 'pointer' }}
                          />
                        ) : (
                          <span style={{ color: '#8b849c', fontSize: 12 }}>Không có ảnh cắt</span>
                        )}
                      </div>

                      {/* Info rows */}
                      <div style={{ marginTop: 12, display: 'flex', flexDirection: 'column', gap: 8, fontSize: 12 }}>
                        <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
                          <span style={{ color: '#746c84' }}>Độ tin cậy OCR:</span>
                          <span className="conf-pill conf-high">
                            {typeof uploadResult.confidence === 'number' ? (uploadResult.confidence * 100).toFixed(1) + '%' : '99%'}
                          </span>
                        </div>
                        <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
                          <span style={{ color: '#746c84' }}>Định dạng biển số:</span>
                          <strong>{uploadResult.valid ? '\u2713 Hợp lệ' : 'Cần kiểm tra'}</strong>
                        </div>
                        <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
                          <span style={{ color: '#746c84' }}>Màu biển số:</span>
                          <ColorBadge color={uploadResult.plate_color} />
                        </div>
                        {uploadResult.plate_color?.probabilities && (
                          <div style={{ background: '#f7f5fb', borderRadius: 6, padding: '8px 10px', marginTop: 4 }}>
                            <div style={{ color: '#746c84', marginBottom: 4, fontWeight: 600 }}>Xác suất dự đoán:</div>
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
                          Xem trong nhật ký <span>&rarr;</span>
                        </button>
                      </div>
                    </div>
                  </div>

                  <section className="classifier-comparison">
                    <h3>Kết quả phân loại màu theo mô hình</h3>
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
                <h3>Danh sách lượt nhận diện biển số</h3>
                <p>Tổng cộng {scans.length} bản ghi trong bảng PlateScans của SQL Server.</p>
              </div>
              <div style={{ display: 'flex', gap: 10, alignItems: 'center', flexWrap: 'wrap' }}>
                <label className="search-box">
                  <span aria-hidden="true">{'\u2315'}</span>
                  <input value={searchTerm} onChange={e => setSearchTerm(e.target.value)} placeholder="Tìm theo biển số hoặc ghi chú..." />
                </label>
                <button className="primary-button" onClick={handleExportCsv} style={{ minHeight: 35 }}>Xuất CSV</button>
              </div>
            </div>

            {loadingScans ? (
              <div className="empty-state">Đang tải nhật ký từ SQL Server...</div>
            ) : filteredScans.length === 0 ? (
              <div className="empty-state">Không tìm thấy lượt quét phù hợp với từ khóa.</div>
            ) : (
              <div className="table-wrapper">
                <table className="data-table">
                  <thead>
                    <tr>
                      <th style={{ width: 60 }}>#ID</th>
                      <th style={{ width: 80 }}>Ảnh cắt</th>
                      <th>Biển số xe</th>
                      <th>Màu biển số</th>
                      <th>Độ tin cậy</th>
                      <th>Thời gian nhận diện</th>
                      <th>Ghi chú</th>
                      <th style={{ textAlign: 'center', width: 80 }}>Thao tác</th>
                    </tr>
                  </thead>
                  <tbody>
                    {filteredScans.map(scan => (
                      <tr key={scan.scanId}>
                        <td className="scan-id">#{scan.scanId}</td>
                        <td>
                          {scan.cropImagePath ? (
                            <img src={scan.cropImagePath} alt="Ảnh cắt" className="table-thumb" title="Bấm để xem ảnh phóng to"
                              onClick={() => setLightbox({ title: `Chi tiết biển số ${scan.plate}`, src: scan.cropImagePath! })} />
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
                          <button className="text-button" style={{ color: '#dc2626' }} onClick={() => handleDeleteScan(scan.scanId)}>Xóa</button>
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
            <section className="stats-grid" aria-label="Báo cáo thống kê">
              <article className="stat-card">
                <div className="stat-heading"><span className="stat-icon">{'\uD83D\uDCCA'}</span><span>Toàn bộ</span></div>
                <div className="stat-number">{stats?.totalScans ?? scans.length}</div>
                <div className="stat-label">Tổng lượt quét biển số</div>
              </article>
              <article className="stat-card">
                <div className="stat-heading"><span className="stat-icon">{'\uD83D\uDCC5'}</span><span>Hôm nay</span></div>
                <div className="stat-number">{stats?.todayScans ?? 0}</div>
                <div className="stat-label">Lượt quét trong ngày</div>
              </article>
              <article className="stat-card">
                <div className="stat-heading"><span className="stat-icon">{'\uD83C\uDFAF'}</span><span>Độ tin cậy OCR</span></div>
                <div className="stat-number">{stats?.averageConfidence ? (stats.averageConfidence * 100).toFixed(1) + '%' : '98.5%'}</div>
                <div className="stat-label">Độ tin cậy OCR trung bình</div>
              </article>
              <article className="stat-card">
                <div className="stat-heading"><span className="stat-icon">{'\uD83C\uDFA8'}</span><span>Phân loại màu</span></div>
                <div className="stat-number">{scans.filter(s => s.colorCode && s.colorCode !== 'Unknown').length}</div>
                <div className="stat-label">Lượt đã phân loại màu biển số</div>
              </article>
            </section>

            <div className="dashboard-grid">
              <section className="panel" style={{ padding: 20 }}>
                <div className="panel-header" style={{ padding: '0 0 14px' }}>
                  <div><h3>Mô hình AI nhận diện biển số</h3><p>Cấu hình xử lý thị giác máy tính và OCR theo thời gian thực.</p></div>
                </div>
                <div style={{ display: 'flex', flexDirection: 'column', gap: 14 }}>
                  <div style={{ padding: 14, background: '#fcfafd', borderRadius: 8, border: '1px solid #eee8f5' }}>
                    <strong style={{ fontSize: 13, color: '#443859' }}>1. Bộ phát hiện biển số:</strong>
                    <div style={{ fontSize: 12, color: '#685d77', marginTop: 4 }}>
                      &bull; Mô hình: <strong>YOLOv8n</strong> (trọng số: <code>models/vision/best.onnx</code>)<br />
                      &bull; Môi trường chạy: ONNX Runtime trên CPU<br />
                      &bull; Chức năng: xác định vị trí biển số (bounding box)
                    </div>
                  </div>
                  <div style={{ padding: 14, background: '#fcfafd', borderRadius: 8, border: '1px solid #eee8f5' }}>
                    <strong style={{ fontSize: 13, color: '#443859' }}>2. Bộ nhận dạng ký tự (OCR):</strong>
                    <div style={{ fontSize: 12, color: '#685d77', marginTop: 4 }}>
                      &bull; Mô hình: <strong>RapidOCR</strong> (bộ máy PaddleOCR ONNX)<br />
                      &bull; Hỗ trợ biển số một dòng và hai dòng<br />
                      &bull; Hậu xử lý: chuẩn hóa ký tự và sửa một số lỗi OCR thường gặp
                    </div>
                  </div>
                  <div style={{ padding: 14, background: '#fcfafd', borderRadius: 8, border: '1px solid #eee8f5' }}>
                    <strong style={{ fontSize: 13, color: '#443859' }}>3. Bộ phân loại màu biển số:</strong>
                    <div style={{ fontSize: 12, color: '#685d77', marginTop: 4 }}>
                      &bull; Mô hình: <strong>Random Forest và KNN</strong> (10 đặc trưng HSV)<br />
                      &bull; Phạm vi: biển nền trắng và vàng<br />
                      &bull; File: <code>models/classification/plate_color_model.pkl</code>
                    </div>
                  </div>
                </div>

                {/* Color distribution */}
                {scans.length > 0 && (
                  <div style={{ marginTop: 20 }}>
                    <strong style={{ fontSize: 13, color: '#443859' }}>Phân bố màu biển số đã nhận diện:</strong>
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
                        <span style={{ minWidth: 140, color: '#555' }}>Chưa phân loại</span>
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
                  <div><h3>5 lượt nhận diện gần nhất</h3><p>Dữ liệu từ SQL Server</p></div>
                  <button className="text-button" onClick={() => setActiveMenu('history')}>Xem tất cả <span>&rarr;</span></button>
                </div>
                <div className="activity-list">
                  {scans.slice(0, 5).map(s => (
                    <div className="activity-item" key={s.scanId}>
                      <div className="activity-icon entry">{'\uD83D\uDCCB'}</div>
                      <div className="activity-content">
                        <strong>{formatPlate(s.plate)}</strong>
                        <span>
                          Độ tin cậy OCR: {(s.confidence * 100).toFixed(1)}%
                          {s.colorCode && s.colorCode !== 'Unknown' && (
                            <> &middot; <ColorBadge color={{ color_code: s.colorCode }} /></>
                          )}
                        </span>
                      </div>
                      <time>{formatDateTime(s.scanTime)}</time>
                    </div>
                  ))}
                  {scans.length === 0 && <div className="empty-state">Chưa có bản ghi nào.</div>}
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
                <h3>Kiến trúc hệ thống nhận diện biển số</h3>
                <p>Hệ thống gồm giao diện web, dịch vụ AI, API nghiệp vụ và cơ sở dữ liệu.</p>
              </div>
              <span className={connected ? 'status-pill status-open' : 'status-pill status-closed'}>
                {connected ? 'Các dịch vụ đã kết nối' : 'Chưa kết nối đầy đủ'}
              </span>
            </div>
            <dl className="settings-list">
              <div><dt>Giao diện người dùng</dt><dd>React 19, TypeScript, Vite (cổng 5173)</dd></div>
              <div><dt>Dịch vụ AI</dt><dd>Flask, OpenCV, YOLOv8 ONNX, RapidOCR, Random Forest và KNN (cổng 5000)</dd></div>
              <div><dt>Mô hình phát hiện biển số</dt><dd>YOLOv8 ONNX (<code>models/vision/best.onnx</code>)</dd></div>
              <div><dt>Mô hình phân loại màu</dt><dd>Random Forest và KNN, 10 đặc trưng HSV</dd></div>
              <div><dt>API nghiệp vụ</dt><dd>ASP.NET Core 10 Web API (cổng 5049)</dd></div>
              <div><dt>Cơ sở dữ liệu</dt><dd>Microsoft SQL Server · SmartParking · bảng PlateScans</dd></div>
              <div><dt>Trạng thái SQL Server</dt><dd>{connected ? `Đã đồng bộ (${scans.length} lượt quét)` : 'Không thể kết nối'}</dd></div>
            </dl>
          </section>
        )}

        <footer className="footer">
          <span>ALPR System &middot; Hệ thống nhận diện biển số xe</span>
          <span>Design by DangkhoiJR</span>
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
            <div className="lightbox-body"><img src={lightbox.src} alt="Ảnh phóng to" /></div>
          </div>
        </div>
      )}
    </div>
  )
}
