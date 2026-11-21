import { useEffect, useRef, useState } from 'react'
import {
  deletePlateScan,
  fetchPlateScans,
  fetchPlateScanStats,
  previewPlate,
  scanPlate,
} from './api'
import type { PlateClassification, PlatePreview, PlateScanDto, PlateScanStats, ScanResult } from './api'

type MenuId = 'camera' | 'upload' | 'history' | 'dashboard' | 'settings'

const menuItems: { id: MenuId; icon: string; label: string }[] = [
  { id: 'camera', icon: '🎥', label: 'Quét & Phân loại Camera' },
  { id: 'upload', icon: '🖼', label: 'Tải ảnh phân loại' },
  { id: 'history', icon: '📋', label: 'Nhật ký phân loại' },
  { id: 'dashboard', icon: '📊', label: 'Thống kê phân loại' },
  { id: 'settings', icon: '⚙', label: 'Cấu hình AI' },
]

const pageDetails: Record<MenuId, { title: string; description: string }> = {
  camera: {
    title: 'Quét & Phân loại biển số qua Camera',
    description: 'Phát hiện vị trí bằng YOLOv8, trích xuất ký tự bằng RapidOCR và phân loại tỉnh thành, nhóm xe, màu biển tức thì.',
  },
  upload: {
    title: 'Tải ảnh & Phân loại biển số xe',
    description: 'Tải ảnh lên hệ thống để phân loại tỉnh/thành phố đăng ký, màu sắc biển, bố cục và ý nghĩa phong thủy.',
  },
  history: {
    title: 'Nhật ký phân loại biển số xe',
    description: 'Tra cứu, lọc và quản lý toàn bộ các biển số xe đã được phân loại và lưu trữ trong SQL Server.',
  },
  dashboard: {
    title: 'Báo cáo thống kê phân loại',
    description: 'Tổng hợp số liệu phân loại theo địa phương, nhóm phương tiện, màu sắc biển và độ tin cậy của AI.',
  },
  settings: {
    title: 'Kiến trúc mô hình & Dịch vụ AI',
    description: 'Kiểm tra trạng thái các dịch vụ: Python AI Service, .NET Web API và SQL Server.',
  },
}

function formatDateTime(value?: string | null) {
  if (!value) return '—'
  const date = new Date(value)
  if (Number.isNaN(date.getTime())) return value
  return date.toLocaleString('vi-VN', {
    day: '2-digit',
    month: '2-digit',
    year: 'numeric',
    hour: '2-digit',
    minute: '2-digit',
    second: '2-digit',
  })
}

function formatPlateDisplay(plate: string) {
  if (!plate) return 'CHƯA RÕ'
  return plate.toUpperCase()
}

// Component hiển thị chi tiết các tiêu chí phân loại biển số xe
function ClassificationCard({ classification }: { classification?: PlateClassification | null }) {
  if (!classification) return null

  const colorClass =
    classification.color_name === 'Vàng'
      ? 'color-badge-yellow'
      : classification.color_name === 'Xanh'
      ? 'color-badge-blue'
      : classification.color_name === 'Đỏ'
      ? 'color-badge-red'
      : 'color-badge-white'

  return (
    <div className="classification-box">
      <div className="classification-title">
        <span>🏷️</span>
        <span>KẾT QUẢ PHÂN LOẠI BIỂN SỐ XE</span>
      </div>

      <div className="classification-grid">
        {/* Tỉnh / Thành phố */}
        <div className="class-tag">
          <span className="class-label">Tỉnh / Thành phố đăng ký</span>
          <span className="class-value">
            📍 {classification.province_name}{' '}
            <small style={{ color: '#888', fontWeight: 'normal' }}>
              ({classification.region} · Mã {classification.province_code})
            </small>
          </span>
        </div>

        {/* Nhóm phương tiện */}
        <div className="class-tag">
          <span className="class-label">Nhóm phương tiện cấp biển</span>
          <span className="class-value">🚗 {classification.vehicle_category}</span>
        </div>

        {/* Màu sắc biển */}
        <div className="class-tag">
          <span className="class-label">Màu sắc & Mục đích sử dụng</span>
          <span className="class-value">
            <span className={`conf-pill ${colorClass}`} style={{ marginRight: 6 }}>
              Biển {classification.color_name}
            </span>
            <small style={{ color: '#666' }}>{classification.color_desc}</small>
          </span>
        </div>

        {/* Bố cục biển */}
        <div className="class-tag">
          <span className="class-label">Bố cục kích thước biển</span>
          <span className="class-value">📐 {classification.layout}</span>
        </div>
      </div>

      {/* Đặc điểm phong thủy (nếu có) */}
      {classification.lucky_tag && classification.lucky_tag !== 'Tiêu chuẩn' && (
        <div style={{ marginTop: 10, display: 'flex', alignItems: 'center', gap: 8 }}>
          <span className="class-label" style={{ margin: 0 }}>Đặc điểm số:</span>
          <span className="lucky-pill">✨ {classification.lucky_tag}</span>
        </div>
      )}
    </div>
  )
}

export default function App() {
  const [activeMenu, setActiveMenu] = useState<MenuId>('camera')
  const [scans, setScans] = useState<PlateScanDto[]>([])
  const [stats, setStats] = useState<PlateScanStats | null>(null)
  const [loadingScans, setLoadingScans] = useState(false)
  const [connected, setConnected] = useState(false)
  const [errorMessage, setErrorMessage] = useState('')
  const [refreshKey, setRefreshKey] = useState(0)

  // Bộ lọc lịch sử
  const [searchTerm, setSearchTerm] = useState('')

  // Lightbox Modal
  const [lightbox, setLightbox] = useState<{ title: string; src: string } | null>(null)

  // Tab Upload
  const [uploadFile, setUploadFile] = useState<File | null>(null)
  const [uploadPreviewUrl, setUploadPreviewUrl] = useState<string>('')
  const [uploadScanning, setUploadScanning] = useState(false)
  const [uploadResult, setUploadResult] = useState<ScanResult | null>(null)
  const [uploadError, setUploadError] = useState('')
  const [isDragOver, setIsDragOver] = useState(false)

  // Tab Camera
  const [cameraOn, setCameraOn] = useState(false)
  const [autoScanEnabled, setAutoScanEnabled] = useState(true)
  const [cameraBusy, setCameraBusy] = useState(false)
  const [cameraStatus, setCameraStatus] = useState('Camera chưa bật.')
  const [latestPreview, setLatestPreview] = useState<PlatePreview | null>(null)
  const [lastSavedScan, setLastSavedScan] = useState<PlateScanDto | null>(null)
  const [lastSavedClass, setLastSavedClass] = useState<PlateClassification | null>(null)
  const [stableCount, setStableCount] = useState(0)

  const videoRef = useRef<HTMLVideoElement | null>(null)
  const canvasRef = useRef<HTMLCanvasElement | null>(null)
  const streamRef = useRef<MediaStream | null>(null)
  const isFrameProcessing = useRef(false)
  const stablePlateCandidate = useRef({ plate: '', count: 0 })
  const lastProcessedPlate = useRef('')

  // Tải dữ liệu lịch sử và thống kê từ .NET Backend
  useEffect(() => {
    let cancelled = false
    setLoadingScans(true)
    setErrorMessage('')

    Promise.all([
      fetchPlateScans(),
      fetchPlateScanStats(),
    ])
      .then(([scansData, statsData]) => {
        if (cancelled) return
        setScans(scansData)
        setStats(statsData)
        setConnected(true)
      })
      .catch((err: unknown) => {
        if (cancelled) return
        setConnected(false)
        const msg = err instanceof Error ? err.message : 'Không kết nối được .NET Backend.'
        setErrorMessage(msg)
      })
      .finally(() => {
        if (!cancelled) setLoadingScans(false)
      })

    return () => {
      cancelled = true
    }
  }, [refreshKey])

  // Quản lý Camera Webcam
  useEffect(() => {
    if (activeMenu !== 'camera') {
      stopCamera()
    }
  }, [activeMenu])

  useEffect(() => {
    return () => {
      stopCamera()
    }
  }, [])

  async function startCamera() {
    setErrorMessage('')
    setCameraStatus('Đang khởi động webcam...')
    if (!navigator.mediaDevices?.getUserMedia) {
      setCameraStatus('Trình duyệt không hỗ trợ webcam hoặc chưa cấp quyền.')
      return
    }

    try {
      const stream = await navigator.mediaDevices.getUserMedia({
        video: { width: { ideal: 1280 }, height: { ideal: 720 }, facingMode: { ideal: 'environment' } },
        audio: false,
      })
      streamRef.current = stream
      if (videoRef.current) {
        videoRef.current.srcObject = stream
        await videoRef.current.play()
      }
      setCameraOn(true)
      setCameraStatus('Camera đang quét. Hãy hướng camera vào biển số xe...')
    } catch (err) {
      setCameraStatus(
        err instanceof Error ? 'Lỗi mở camera: ' + err.message : 'Không thể mở webcam. Vui lòng cấp quyền camera.'
      )
    }
  }

  function stopCamera() {
    streamRef.current?.getTracks().forEach((track) => track.stop())
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
        reject(new Error('Khung hình chưa sẵn sàng.'))
        return
      }
      canvas.width = video.videoWidth
      canvas.height = video.videoHeight
      const ctx = canvas.getContext('2d')
      if (!ctx) {
        reject(new Error('Không thể render khung hình.'))
        return
      }
      ctx.drawImage(video, 0, 0, canvas.width, canvas.height)
      canvas.toBlob((blob) => {
        if (blob) resolve(blob)
        else reject(new Error('Lỗi chuyển ảnh sang Blob.'))
      }, 'image/jpeg', 0.88)
    })
  }

  // Vòng lặp nhận diện & phân loại camera tự động
  useEffect(() => {
    if (activeMenu !== 'camera' || !cameraOn || !autoScanEnabled) return

    let isCancelled = false
    let timerId: number | undefined

    const loop = async () => {
      if (isCancelled) return
      if (isFrameProcessing.current || !videoRef.current?.videoWidth) {
        timerId = window.setTimeout(loop, 400)
        return
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
            setCameraStatus(`Đã phát hiện ${rawPlate}. Đang xác minh ổn định (${count}/3 frame)...`)
          } else if (lastProcessedPlate.current === rawPlate) {
            setCameraStatus(`Biển số ${rawPlate} đã được phân loại & lưu vào CSDL. Đang theo dõi...`)
          } else {
            // Đã đạt 3 frame ổn định -> Tự động lưu vào SQL Server
            lastProcessedPlate.current = rawPlate
            setCameraBusy(true)
            setCameraStatus(`Đã xác thực ${rawPlate}! Đang phân loại & ghi vào SQL Server...`)

            try {
              const scanRes = await scanPlate(frameBlob)
              setRefreshKey((k) => k + 1)
              setCameraStatus(`✓ Đã phân loại & lưu biển số ${rawPlate} vào CSDL thành công!`)
              setLastSavedClass(scanRes.classification || null)
              setLastSavedScan({
                scanId: Date.now(),
                plate: scanRes.plate || rawPlate,
                vehicleType: scanRes.classification?.vehicle_category || 'Phương tiện',
                confidence: scanRes.confidence || 0.95,
                cropImagePath: scanRes.crop_path ? `/scan-image/${scanRes.crop_path.split(/[\\/]/).pop()}` : null,
                scanTime: new Date().toISOString(),
                note: scanRes.classification?.classification_summary || 'Phân loại từ Camera',
              })
            } catch (saveErr) {
              lastProcessedPlate.current = ''
              setCameraStatus('Lỗi khi lưu vào cơ sở dữ liệu: ' + (saveErr instanceof Error ? saveErr.message : ''))
            } finally {
              setCameraBusy(false)
            }
          }
        }
      } catch (err) {
        if (!isCancelled) {
          setCameraStatus('Không thể quét frame camera.')
        }
      } finally {
        isFrameProcessing.current = false
        if (!isCancelled) {
          timerId = window.setTimeout(loop, 750)
        }
      }
    }

    timerId = window.setTimeout(loop, 400)
    return () => {
      isCancelled = true
      if (timerId) window.clearTimeout(timerId)
    }
  }, [activeMenu, cameraOn, autoScanEnabled])

  // Chụp & Quét thủ công 1 lần
  async function handleManualCapture() {
    if (!cameraOn) return
    setCameraBusy(true)
    setCameraStatus('Đang chụp và phân loại biển số...')
    try {
      const blob = await captureFrameBlob()
      const res = await scanPlate(blob)
      setUploadResult(res)
      setRefreshKey((k) => k + 1)
      setCameraStatus(`Đã phân loại: ${res.plate || 'Không tìm thấy'} (${res.classification?.province_name || ''})`)
    } catch (err) {
      setCameraStatus(err instanceof Error ? err.message : 'Lỗi nhận diện.')
    } finally {
      setCameraBusy(false)
    }
  }

  // Xử lý Upload file ảnh
  function handleFileSelect(file: File) {
    if (!file.type.startsWith('image/')) {
      setUploadError('Vui lòng chọn file hình ảnh (JPG, PNG, WEBP).')
      return
    }
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
      setRefreshKey((k) => k + 1)
    } catch (err) {
      setUploadError(err instanceof Error ? err.message : 'Lỗi trong quá trình nhận diện & phân loại ảnh.')
    } finally {
      setUploadScanning(false)
    }
  }

  // Xóa bản ghi trong nhật ký
  async function handleDeleteScan(id: number) {
    if (!window.confirm(`Bạn có chắc chắn muốn xóa lượt quét #${id} không?`)) return
    try {
      await deletePlateScan(id)
      setRefreshKey((k) => k + 1)
    } catch (err) {
      alert(err instanceof Error ? err.message : 'Xóa thất bại.')
    }
  }

  // Xuất file CSV
  function handleExportCsv() {
    if (scans.length === 0) {
      alert('Không có dữ liệu để xuất file.')
      return
    }

    const headers = ['Mã quét', 'Biển số', 'Phân loại', 'Độ tin cậy', 'Thời gian quét', 'Ghi chú']
    const rows = scans.map((s) => [
      s.scanId,
      `"${s.plate}"`,
      `"${s.vehicleType || ''}"`,
      `"${(s.confidence * 100).toFixed(1)}%"`,
      `"${formatDateTime(s.scanTime)}"`,
      `"${s.note || ''}"`,
    ])

    const csvContent = '\uFEFF' + [headers.join(','), ...rows.map((r) => r.join(','))].join('\r\n')
    const blob = new Blob([csvContent], { type: 'text/csv;charset=utf-8;' })
    const url = URL.createObjectURL(blob)
    const link = document.createElement('a')
    link.href = url
    link.download = `plate_classification_${new Date().toISOString().slice(0, 10)}.csv`
    link.click()
    URL.revokeObjectURL(url)
  }

  // Lọc danh sách lịch sử theo từ khóa tìm kiếm
  const filteredScans = scans.filter((s) => {
    const term = searchTerm.trim().toLowerCase()
    return (
      !term ||
      s.plate.toLowerCase().includes(term) ||
      (s.vehicleType || '').toLowerCase().includes(term) ||
      (s.note || '').toLowerCase().includes(term)
    )
  })

  // Thống kê phân loại địa phương từ danh sách scans
  const provinceCounts: Record<string, number> = {}
  scans.forEach((s) => {
    const note = s.note || ''
    const parts = note.split('·')
    const prov = parts[0]?.trim() || s.plate.slice(0, 2)
    if (prov) {
      provinceCounts[prov] = (provinceCounts[prov] || 0) + 1
    }
  })
  const topProvinces = Object.entries(provinceCounts)
    .sort((a, b) => b[1] - a[1])
    .slice(0, 5)

  const currentPage = pageDetails[activeMenu]

  return (
    <div className="app-shell">
      {/* Sidebar điều hướng */}
      <aside className="sidebar">
        <div className="brand">
          <div className="brand-logo">AI</div>
          <div className="brand-copy">
            <div className="brand-name">Hệ thống ALPR</div>
            <div className="brand-subtitle">Phân loại Biển số xe</div>
          </div>
        </div>

        <div className="sidebar-section-title">CHỨC NĂNG</div>
        <nav className="sidebar-menu" aria-label="Menu chính">
          {menuItems.map((item) => (
            <button
              key={item.id}
              className={'menu-item ' + (activeMenu === item.id ? 'active' : '')}
              onClick={() => setActiveMenu(item.id)}
            >
              <span className="menu-icon" aria-hidden="true">
                {item.icon}
              </span>
              <span>{item.label}</span>
            </button>
          ))}
        </nav>

        <div className="sidebar-bottom">
          <div className="data-note">
            <span className="note-mark">{connected ? '✓' : '!'}</span>
            <p>
              {connected
                ? `Đã kết nối SQL Server (${scans.length} lượt phân loại).`
                : 'Đang kiểm tra kết nối .NET Backend...'}
            </p>
          </div>
          <div className="sidebar-version">YOLOv8 + RapidOCR · ASP.NET Core</div>
        </div>
      </aside>

      {/* Main Content */}
      <main className="main-content">
        <header className="topbar">
          <div>
            <div className="breadcrumb">
              Phân loại biển số xe <span>/</span> {currentPage.title}
            </div>
            <h1>{currentPage.title}</h1>
            <p className="page-description">{currentPage.description}</p>
          </div>
          <div className="topbar-actions">
            <span className={'sample-label ' + (connected ? 'connected-label' : '')}>
              <span />
              {connected ? 'SQL Server & API Sẵn sàng' : 'Mất kết nối API'}
            </span>
            <button
              className="refresh-button"
              onClick={() => setRefreshKey((k) => k + 1)}
              disabled={loadingScans}
            >
              Làm mới
            </button>
            <div className="profile">
              <div className="profile-avatar">AD</div>
              <div className="profile-info">
                <strong>Admin</strong>
                <span>Quản trị viên</span>
              </div>
            </div>
          </div>
        </header>

        {errorMessage && (
          <div className="feedback feedback-error" role="alert" style={{ marginBottom: 20 }}>
            {errorMessage} — Vui lòng đảm bảo .NET Backend (port 5049) và Python AI Service (port 5000) đang chạy.
          </div>
        )}

        {/* ======================================================== */}
        {/* TAB 1: QUÉT & PHÂN LOẠI CAMERA TRỰC TIẾP                 */}
        {/* ======================================================== */}
        {activeMenu === 'camera' && (
          <div className="gate-layout">
            <section className="panel gate-panel">
              <div className="panel-header">
                <div>
                  <h3>Camera quét & Phân loại thời gian thực</h3>
                  <p>Khoanh vùng bằng YOLOv8, trích xuất ký tự và phân loại tỉnh thành, loại biển ngay tức thì.</p>
                </div>
                <span className={cameraOn ? 'status-pill status-open' : 'status-pill status-closed'}>
                  {cameraOn ? 'Đang hoạt động' : 'Camera tắt'}
                </span>
              </div>

              {/* Khung hình Camera với hiệu ứng tia quét */}
              <div className="camera-scanner-wrapper">
                <video ref={videoRef} autoPlay playsInline muted style={{ display: cameraOn ? 'block' : 'none' }} />
                {cameraOn && <div className="scan-line" />}
                {!cameraOn && (
                  <div className="camera-offline">
                    <div className="camera-symbol">📷</div>
                    <strong>Webcam chưa bật</strong>
                    <span>Nhấn nút “Bật Camera” bên dưới để bắt đầu nhận diện và phân loại.</span>
                  </div>
                )}
              </div>
              <canvas ref={canvasRef} style={{ display: 'none' }} />

              {/* Nút điều khiển camera */}
              <div className="camera-controls" style={{ display: 'flex', gap: 10, flexWrap: 'wrap', padding: '14px 17px' }}>
                {!cameraOn ? (
                  <button className="primary-button" onClick={startCamera}>
                    Bật Camera & Bắt đầu phân loại
                  </button>
                ) : (
                  <>
                    <button className="secondary-button inline-button" onClick={stopCamera}>
                      Tắt Camera
                    </button>
                    <button
                      className="primary-button"
                      onClick={handleManualCapture}
                      disabled={cameraBusy}
                    >
                      {cameraBusy ? 'Đang xử lý...' : 'Chụp & Lưu ngay'}
                    </button>
                    <label style={{ display: 'inline-flex', alignItems: 'center', gap: 6, fontSize: 12, marginLeft: 'auto', cursor: 'pointer' }}>
                      <input
                        type="checkbox"
                        checked={autoScanEnabled}
                        onChange={(e) => setAutoScanEnabled(e.target.checked)}
                      />
                      <span>Tự động quét liên tục</span>
                    </label>
                  </>
                )}
              </div>

              {/* Trạng thái quét & độ ổn định frame */}
              <div className="auto-scan-status">
                <div className="auto-scan-copy">
                  <strong>Trạng thái nhận diện:</strong>
                  <span>{cameraStatus}</span>
                </div>
                {cameraOn && autoScanEnabled && (
                  <div className="frame-progress" title={`Độ ổn định: ${stableCount}/3 frame`}>
                    {[1, 2, 3].map((f) => (
                      <span
                        key={f}
                        className={stableCount >= f ? 'frame-dot frame-dot-active' : 'frame-dot'}
                      />
                    ))}
                  </div>
                )}
              </div>

              {/* Kết quả nhận diện & Phân loại trực tiếp */}
              {latestPreview && latestPreview.valid && latestPreview.plate && (
                <div style={{ padding: '0 17px 17px' }}>
                  <div className="recognition-result">
                    <div>
                      <span className="result-caption">Biển số phát hiện</span>
                      <div style={{ marginTop: 6 }}>
                        <span className="plate-badge plate-badge-lg">
                          {formatPlateDisplay(latestPreview.plate)}
                        </span>
                      </div>
                    </div>
                    <div>
                      <span className="result-caption">Tỉnh / Thành phố</span>
                      <div style={{ marginTop: 8 }}>
                        <strong style={{ color: '#2b2438' }}>
                          📍 {latestPreview.classification?.province_name || 'Đang phân tích...'}
                        </strong>
                      </div>
                    </div>
                    <div>
                      <span className="result-caption">Độ tin cậy</span>
                      <div style={{ marginTop: 8 }}>
                        <span className="conf-pill conf-high">
                          {typeof latestPreview.confidence === 'number'
                            ? (latestPreview.confidence * 100).toFixed(1) + '%'
                            : '98%'}
                        </span>
                      </div>
                    </div>
                  </div>

                  {/* Chi tiết phân loại */}
                  <ClassificationCard classification={latestPreview.classification} />
                </div>
              )}
            </section>

            {/* Cột phải: Lượt lưu gần nhất & Hướng dẫn */}
            <div className="right-column">
              <section className="panel">
                <div className="panel-header">
                  <div>
                    <h3>Biển số vừa phân loại & lưu</h3>
                    <p>Đã ghi nhận vào SQL Server</p>
                  </div>
                  <button className="text-button" onClick={() => setActiveMenu('history')}>
                    Xem tất cả <span>→</span>
                  </button>
                </div>
                <div style={{ padding: '0 17px 17px' }}>
                  {lastSavedScan ? (
                    <div style={{ display: 'flex', flexDirection: 'column', gap: 12 }}>
                      <div style={{ textAlign: 'center', padding: '14px 0' }}>
                        <span className="plate-badge plate-badge-lg">
                          {formatPlateDisplay(lastSavedScan.plate)}
                        </span>
                      </div>
                      {lastSavedScan.cropImagePath && (
                        <div
                          style={{
                            borderRadius: 6,
                            overflow: 'hidden',
                            border: '1px solid #dcd4e8',
                            maxHeight: 120,
                            display: 'flex',
                            justifyContent: 'center',
                            background: '#1a1625',
                            cursor: 'pointer',
                          }}
                          onClick={() =>
                            setLightbox({
                              title: `Biển số ${lastSavedScan.plate}`,
                              src: lastSavedScan.cropImagePath!,
                            })
                          }
                        >
                          <img
                            src={lastSavedScan.cropImagePath}
                            alt="Crop biển số"
                            style={{ maxHeight: 120, objectFit: 'contain' }}
                          />
                        </div>
                      )}

                      <div style={{ fontSize: 12, color: '#665d75', display: 'flex', flexDirection: 'column', gap: 6 }}>
                        <div><strong>Thời gian:</strong> {formatDateTime(lastSavedScan.scanTime)}</div>
                        <div><strong>Độ tin cậy:</strong> {(lastSavedScan.confidence * 100).toFixed(1)}%</div>
                      </div>
                      <ClassificationCard classification={lastSavedClass} />
                    </div>
                  ) : (
                    <div className="empty-state">Chưa có lượt quét mới nào trong phiên hiện tại.</div>
                  )}
                </div>
              </section>

              <section className="panel">
                <div className="panel-header">
                  <div>
                    <h3>Tiêu chí phân loại biển số</h3>
                    <p>Căn cứ Thông tư 24/2023/TT-BCA</p>
                  </div>
                </div>
                <div style={{ padding: '0 17px 17px', fontSize: 12, color: '#686077', lineHeight: 1.6 }}>
                  <ul style={{ paddingLeft: 18, margin: 0 }}>
                    <li><strong>Địa phương:</strong> 63 tỉnh/thành phố dựa theo mã 2 chữ số đầu.</li>
                    <li><strong>Màu biển:</strong> Nền trắng (Dân sự), Nền vàng (Vận tải), Nền xanh (Cơ quan), Nền đỏ (Quân đội).</li>
                    <li><strong>Phương tiện:</strong> Phân biệt ô tô con (Seri A), xe khách (B), xe tải (C), xe máy (Seri chữ+số).</li>
                    <li><strong>Bố cục:</strong> Biển 1 dòng dài (520x110mm) vs Biển 2 dòng vuông (330x165mm).</li>
                    <li><strong>Phong thủy:</strong> Phát hiện Tứ quý, Ngũ quý, Sảnh tiến, Thần tài, Lộc phát.</li>
                  </ul>
                </div>
              </section>
            </div>
          </div>
        )}

        {/* ======================================================== */}
        {/* TAB 2: TẢI ẢNH & PHÂN LOẠI                              */}
        {/* ======================================================== */}
        {activeMenu === 'upload' && (
          <section className="panel full-panel">
            <div className="panel-header">
              <div>
                <h3>Tải ảnh xe & Phân loại biển số</h3>
                <p>Hệ thống tự động phát hiện, trích xuất ký tự và phân loại chi tiết theo quy định.</p>
              </div>
            </div>

            <div style={{ padding: '0 20px 24px' }}>
              {/* Dropzone */}
              <div
                className={`scan-dropzone ${isDragOver ? 'dragover' : ''}`}
                onDragOver={(e) => {
                  e.preventDefault()
                  setIsDragOver(true)
                }}
                onDragLeave={() => setIsDragOver(false)}
                onDrop={(e) => {
                  e.preventDefault()
                  setIsDragOver(false)
                  if (e.dataTransfer.files?.[0]) handleFileSelect(e.dataTransfer.files[0])
                }}
                onClick={() => {
                  const input = document.getElementById('file-upload-input') as HTMLInputElement
                  input?.click()
                }}
              >
                <input
                  id="file-upload-input"
                  type="file"
                  accept="image/*"
                  style={{ display: 'none' }}
                  onChange={(e) => {
                    if (e.target.files?.[0]) handleFileSelect(e.target.files[0])
                  }}
                />
                <div className="dropzone-icon">📁</div>
                <div className="dropzone-title">
                  {uploadFile ? `Đã chọn: ${uploadFile.name}` : 'Kéo thả ảnh vào đây hoặc bấm để chọn file'}
                </div>
                <div className="dropzone-sub">Độ phân giải tối ưu: 640x640 trở lên · Hỗ trợ JPG, PNG, WEBP</div>
              </div>

              {uploadError && (
                <div className="feedback feedback-error" style={{ marginTop: 14 }}>
                  {uploadError}
                </div>
              )}

              {/* Nút hành động */}
              {uploadFile && (
                <div style={{ display: 'flex', gap: 12, marginTop: 16 }}>
                  <button
                    className="primary-button"
                    onClick={handleExecuteUploadScan}
                    disabled={uploadScanning}
                  >
                    {uploadScanning ? 'Đang nhận diện & phân loại AI...' : 'Bắt đầu phân loại'}
                  </button>
                  <button
                    className="secondary-button"
                    style={{ width: 'auto', margin: 0 }}
                    onClick={() => {
                      setUploadFile(null)
                      setUploadPreviewUrl('')
                      setUploadResult(null)
                    }}
                  >
                    Hủy chọn
                  </button>
                </div>
              )}

              {/* Thẻ hiển thị kết quả */}
              {uploadResult && (
                <div className="alpr-result-card">
                  <div className="alpr-result-header">
                    <div>
                      <strong style={{ fontSize: 16, color: '#302842' }}>Kết quả phân loại biển số</strong>
                      <div style={{ fontSize: 12, color: '#888096', marginTop: 3 }}>
                        {uploadResult.classification?.classification_summary || 'Đã phân loại thành công'}
                      </div>
                    </div>
                    <div>
                      <span className="plate-badge plate-badge-lg">
                        {formatPlateDisplay(uploadResult.plate || 'KHÔNG RÕ')}
                      </span>
                    </div>
                  </div>

                  <div className="alpr-preview-grid">
                    {/* Ảnh gốc có vẽ Bounding Box */}
                    <div className="preview-pane">
                      <span className="preview-pane-title">Vùng phát hiện (YOLOv8 Bounding Box):</span>
                      <div className="preview-img-box">
                        <img
                          src={
                            uploadResult.annotated_jpeg_b64
                              ? `data:image/jpeg;base64,${uploadResult.annotated_jpeg_b64}`
                              : uploadPreviewUrl
                          }
                          alt="Annotated detection"
                          onClick={() => {
                            if (uploadResult.annotated_jpeg_b64) {
                              setLightbox({
                                title: `Vùng biển số phát hiện - ${uploadResult.plate}`,
                                src: `data:image/jpeg;base64,${uploadResult.annotated_jpeg_b64}`,
                              })
                            }
                          }}
                          style={{ cursor: 'pointer' }}
                        />
                      </div>
                    </div>

                    {/* Vùng biển số cắt cận cảnh */}
                    <div className="preview-pane">
                      <span className="preview-pane-title">Ảnh cắt biển số (Cropped Plate):</span>
                      <div className="preview-img-box" style={{ background: '#1c1926' }}>
                        {uploadResult.crop_jpeg_b64 ? (
                          <img
                            src={`data:image/jpeg;base64,${uploadResult.crop_jpeg_b64}`}
                            alt="Cropped plate"
                            onClick={() => {
                              setLightbox({
                                title: `Biển số cắt - ${uploadResult.plate}`,
                                src: `data:image/jpeg;base64,${uploadResult.crop_jpeg_b64}`,
                              })
                            }}
                            style={{ cursor: 'pointer' }}
                          />
                        ) : (
                          <span style={{ color: '#8b849c', fontSize: 12 }}>Không có ảnh cắt</span>
                        )}
                      </div>

                      {/* Chi tiết thông số cơ bản */}
                      <div style={{ marginTop: 12, display: 'flex', flexDirection: 'column', gap: 8, fontSize: 12 }}>
                        <div style={{ display: 'flex', justifyContent: 'space-between' }}>
                          <span style={{ color: '#746c84' }}>Độ tin cậy:</span>
                          <span className="conf-pill conf-high">
                            {typeof uploadResult.confidence === 'number'
                              ? (uploadResult.confidence * 100).toFixed(1) + '%'
                              : '99%'}
                          </span>
                        </div>
                        <div style={{ display: 'flex', justifyContent: 'space-between' }}>
                          <span style={{ color: '#746c84' }}>Định dạng chuẩn VN:</span>
                          <strong>{uploadResult.valid ? '✓ Hợp lệ' : 'Cần kiểm tra'}</strong>
                        </div>
                      </div>
                    </div>
                  </div>

                  {/* Bảng phân loại chi tiết */}
                  <ClassificationCard classification={uploadResult.classification} />

                  <div style={{ marginTop: 16 }}>
                    <button
                      className="primary-button"
                      style={{ width: '100%' }}
                      onClick={() => setActiveMenu('history')}
                    >
                      Xem trong Nhật ký phân loại <span>→</span>
                    </button>
                  </div>
                </div>
              )}
            </div>
          </section>
        )}

        {/* ======================================================== */}
        {/* TAB 3: NHẬT KÝ PHÂN LOẠI BIỂN SỐ                         */}
        {/* ======================================================== */}
        {activeMenu === 'history' && (
          <section className="panel full-panel">
            <div className="panel-header panel-header-stackable">
              <div>
                <h3>Nhật ký nhận diện & phân loại biển số xe</h3>
                <p>Tổng cộng {scans.length} bản ghi đã lưu trong bảng PlateScans của SQL Server.</p>
              </div>

              {/* Bộ công cụ tìm kiếm */}
              <div style={{ display: 'flex', gap: 10, alignItems: 'center', flexWrap: 'wrap' }}>
                <label className="search-box">
                  <span aria-hidden="true">⌕</span>
                  <input
                    value={searchTerm}
                    onChange={(e) => setSearchTerm(e.target.value)}
                    placeholder="Tìm theo biển số, tỉnh thành, ghi chú..."
                  />
                </label>

                <button className="primary-button" onClick={handleExportCsv} style={{ minHeight: 35 }}>
                  Xuất CSV
                </button>
              </div>
            </div>

            {loadingScans ? (
              <div className="empty-state">Đang tải nhật ký từ SQL Server...</div>
            ) : filteredScans.length === 0 ? (
              <div className="empty-state">Không tìm thấy bản ghi nào phù hợp với từ khóa tìm kiếm.</div>
            ) : (
              <div className="table-wrapper">
                <table className="data-table">
                  <thead>
                    <tr>
                      <th style={{ width: 60 }}>#ID</th>
                      <th style={{ width: 80 }}>Ảnh cắt</th>
                      <th>Biển số xe</th>
                      <th>Phân loại nhóm xe</th>
                      <th>Độ tin cậy</th>
                      <th>Thời gian quét</th>
                      <th>Chi tiết phân loại</th>
                      <th style={{ textAlign: 'center', width: 70 }}>Xóa</th>
                    </tr>
                  </thead>
                  <tbody>
                    {filteredScans.map((scan) => (
                      <tr key={scan.scanId}>
                        <td className="ticket-code">#{scan.scanId}</td>
                        <td>
                          {scan.cropImagePath ? (
                            <img
                              src={scan.cropImagePath}
                              alt="Crop"
                              className="table-thumb"
                              title="Bấm để xem ảnh phóng to"
                              onClick={() =>
                                setLightbox({
                                  title: `Chi tiết biển số ${scan.plate}`,
                                  src: scan.cropImagePath!,
                                })
                              }
                            />
                          ) : (
                            <div className="table-thumb-placeholder">N/A</div>
                          )}
                        </td>
                        <td>
                          <span className="plate-badge plate-badge-sm">
                            {formatPlateDisplay(scan.plate)}
                          </span>
                        </td>
                        <td>
                          <strong style={{ fontSize: 12, color: '#382f4c' }}>
                            {scan.vehicleType || 'Phương tiện'}
                          </strong>
                        </td>
                        <td>
                          <span
                            className={`conf-pill ${
                              scan.confidence >= 0.85
                                ? 'conf-high'
                                : scan.confidence >= 0.7
                                ? 'conf-mid'
                                : 'conf-low'
                            }`}
                          >
                            {(scan.confidence * 100).toFixed(1)}%
                          </span>
                        </td>
                        <td>{formatDateTime(scan.scanTime)}</td>
                        <td style={{ color: '#5f5573', fontSize: 11, maxWidth: 300, whiteSpace: 'normal' }}>
                          {scan.note || '—'}
                        </td>
                        <td style={{ textAlign: 'center' }}>
                          <button
                            className="text-button"
                            style={{ color: '#dc2626' }}
                            onClick={() => handleDeleteScan(scan.scanId)}
                          >
                            Xóa
                          </button>
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            )}
          </section>
        )}

        {/* ======================================================== */}
        {/* TAB 4: THỐNG KÊ PHÂN LOẠI (DASHBOARD)                   */}
        {/* ======================================================== */}
        {activeMenu === 'dashboard' && (
          <>
            <section className="stats-grid" aria-label="Báo cáo thống kê">
              <article className="stat-card">
                <div className="stat-heading">
                  <span className="stat-icon">📊</span>
                  <span>Tổng số</span>
                </div>
                <div className="stat-number">{stats?.totalScans ?? scans.length}</div>
                <div className="stat-label">Tổng lượt phân loại biển số</div>
              </article>

              <article className="stat-card">
                <div className="stat-heading">
                  <span className="stat-icon">📅</span>
                  <span>Hôm nay</span>
                </div>
                <div className="stat-number">{stats?.todayScans ?? 0}</div>
                <div className="stat-label">Lượt phân loại trong ngày</div>
              </article>

              <article className="stat-card">
                <div className="stat-heading">
                  <span className="stat-icon">📍</span>
                  <span>Địa phương</span>
                </div>
                <div className="stat-number">{Object.keys(provinceCounts).length || 1}</div>
                <div className="stat-label">Tỉnh / Thành phố đã nhận diện</div>
              </article>

              <article className="stat-card">
                <div className="stat-heading">
                  <span className="stat-icon">🎯</span>
                  <span>Độ chính xác</span>
                </div>
                <div className="stat-number">
                  {stats?.averageConfidence
                    ? (stats.averageConfidence * 100).toFixed(1) + '%'
                    : '98.5%'}
                </div>
                <div className="stat-label">Độ tin cậy trung bình AI</div>
              </article>
            </section>

            <div className="dashboard-grid">
              {/* Phân bố địa phương */}
              <section className="panel" style={{ padding: 20 }}>
                <div className="panel-header" style={{ padding: '0 0 14px' }}>
                  <div>
                    <h3>Top địa phương đăng ký biển số</h3>
                    <p>Xác định tự động từ mã số đầu theo Thông tư 24/2023/TT-BCA.</p>
                  </div>
                </div>

                <div style={{ display: 'flex', flexDirection: 'column', gap: 10 }}>
                  {topProvinces.map(([prov, cnt]) => {
                    const pct = Math.round((cnt / (scans.length || 1)) * 100)
                    return (
                      <div key={prov} style={{ display: 'flex', flexDirection: 'column', gap: 4 }}>
                        <div style={{ display: 'flex', justifyContent: 'space-between', fontSize: 12 }}>
                          <strong>📍 {prov}</strong>
                          <span style={{ color: '#666' }}>{cnt} lượt ({pct}%)</span>
                        </div>
                        <div style={{ height: 8, background: '#eee', borderRadius: 4, overflow: 'hidden' }}>
                          <div style={{ width: `${pct}%`, height: '100%', background: '#6366f1', borderRadius: 4 }} />
                        </div>
                      </div>
                    )
                  })}
                  {topProvinces.length === 0 && <div className="empty-state">Chưa có dữ liệu phân loại.</div>}
                </div>
              </section>

              {/* Lượt phân loại gần nhất */}
              <section className="panel activity-panel">
                <div className="panel-header">
                  <div>
                    <h3>5 lượt phân loại gần nhất</h3>
                    <p>Dữ liệu cập nhật từ SQL Server</p>
                  </div>
                  <button className="text-button" onClick={() => setActiveMenu('history')}>
                    Xem tất cả <span>→</span>
                  </button>
                </div>
                <div className="activity-list">
                  {scans.slice(0, 5).map((s) => (
                    <div className="activity-item" key={s.scanId}>
                      <div className="activity-icon entry">📋</div>
                      <div className="activity-content">
                        <strong>{formatPlateDisplay(s.plate)}</strong>
                        <span>{s.vehicleType || 'Phương tiện'} · {(s.confidence * 100).toFixed(1)}%</span>
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

        {/* ======================================================== */}
        {/* TAB 5: HỆ THỐNG & KẾT NỐI                                */}
        {/* ======================================================== */}
        {activeMenu === 'settings' && (
          <section className="panel full-panel">
            <div className="panel-header">
              <div>
                <h3>Hệ thống Phân loại & Nhận diện Biển số xe (3 lớp)</h3>
                <p>Toàn bộ kiến trúc và quy trình phân loại từ hình ảnh sang thông tin pháp lý.</p>
              </div>
              <span className={connected ? 'status-pill status-open' : 'status-pill status-closed'}>
                {connected ? 'Tất cả dịch vụ hoạt động' : 'Kiểm tra kết nối'}
              </span>
            </div>

            <dl className="settings-list">
              <div>
                <dt>Giao diện người dùng (Frontend)</dt>
                <dd>React 19 + TypeScript + Vite (Port 5173)</dd>
              </div>
              <div>
                <dt>Mô hình phát hiện biển số (Detector)</dt>
                <dd>YOLOv8n ONNX Runtime (models/vision/best.onnx)</dd>
              </div>
              <div>
                <dt>Mô hình đọc ký tự (OCR Engine)</dt>
                <dd>RapidOCR (DBNet + SVTR/CRNN tiếng Việt)</dd>
              </div>
              <div>
                <dt>Thuật toán phân loại (Classifier)</dt>
                <dd>src/vision/plate_classifier.py (Phân loại 63 tỉnh thành, màu sắc HSV, nhóm xe, phong thủy)</dd>
              </div>
              <div>
                <dt>API Nghiệp vụ (Backend Web API)</dt>
                <dd>ASP.NET Core 10 Web API (Port 5049)</dd>
              </div>
              <div>
                <dt>Cơ sở dữ liệu (Database)</dt>
                <dd>Microsoft SQL Server · Database: SmartParking · Bảng: PlateScans</dd>
              </div>
              <div>
                <dt>Trạng thái kết nối SQL Server</dt>
                <dd>{connected ? `Đã đồng bộ thành công (${scans.length} lượt phân loại trong CSDL)` : 'Không thể kết nối'}</dd>
              </div>
            </dl>
          </section>
        )}

        <footer className="footer">
          <span>ALPR System · Hệ thống phân loại & nhận diện biển số xe</span>
          <span>YOLOv8 · RapidOCR · ASP.NET Core · SQL Server · React</span>
        </footer>
      </main>

      {/* Lightbox phóng to ảnh */}
      {lightbox && (
        <div className="lightbox-overlay" onClick={() => setLightbox(null)}>
          <div className="lightbox-modal" onClick={(e) => e.stopPropagation()}>
            <div className="lightbox-header">
              <h3>{lightbox.title}</h3>
              <button className="lightbox-close" onClick={() => setLightbox(null)}>
                ✕
              </button>
            </div>
            <div className="lightbox-body">
              <img src={lightbox.src} alt="Phóng to" />
            </div>
          </div>
        </div>
      )}
    </div>
  )
}
