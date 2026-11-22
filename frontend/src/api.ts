export type PlateScanDto = {
  scanId: number
  plate: string
  confidence: number
  imagePath?: string | null
  cropImagePath?: string | null
  plateColor?: PlateColorResult
  plateColorCode?: string | null
  plateColorLabel?: string | null
  plateColorConfidence?: number | null
  scanTime: string
  note?: string | null
  colorCode?: string | null
  createdAt?: string
}

export type PlateScanStats = {
  totalScans: number
  todayScans: number
  averageConfidence: number
}

export type PlateColorResult = {
  color_code?: string
  color_label?: string
  confidence?: number
  probabilities?: Record<string, number>
  algorithm?: string
  features?: Record<string, number>
  comparison?: PlateColorResult
}

export type ClassifierMetrics = {
  accuracy?: number
  precision_macro?: number
  recall_macro?: number
  f1_macro?: number
  labels?: string[]
  confusion_matrix?: number[][]
  per_class?: Record<string, {
    precision: number
    recall: number
    f1_score: number
    support: number
  }>
}

export type ClassifierEvaluation = {
  mean_confidence?: number
  mean_confidence_correct?: number | null
  mean_confidence_incorrect?: number | null
  median_ms_per_image?: number
  mean_ms_per_image?: number
  p95_ms_per_image?: number
  timing_repeats_per_image?: number
  timing_scope?: string
}

export type AlgorithmComparisonReport = {
  winner?: string | null
  outcome?: string
  evaluation_source?: string
  caveat?: string
  train_samples?: number
  test_samples?: number
  test_real_samples?: number
  test_synthetic_samples?: number
  algorithms?: Record<string, {
    model_version?: string
    metrics?: ClassifierMetrics
    evaluation?: ClassifierEvaluation
  }>
}

export type PlatePreview = {
  status?: string
  plate?: string
  valid?: boolean
  confidence?: number
  engine?: string
  message?: string
  crop_jpeg_b64?: string
  annotated_jpeg_b64?: string
  bbox?: number[]
  plate_color?: PlateColorResult
  [key: string]: unknown
}

export type ScanResult = {
  status: string
  plate?: string
  valid?: boolean
  confidence?: number
  engine?: string
  message?: string
  bbox?: number[]
  crop_jpeg_b64?: string
  annotated_jpeg_b64?: string
  image_path?: string
  crop_path?: string
  database_saved?: boolean
  database_message?: string | null
  plate_color?: PlateColorResult
  algorithm_comparison?: AlgorithmComparisonReport | null
  [key: string]: unknown
}

async function readResponse<T>(response: Response): Promise<T> {
  const text = await response.text()
  let body: unknown = {}
  if (text) {
    try { body = JSON.parse(text) } catch { body = { message: text } }
  }
  if (!response.ok) {
    const data = body as { message?: string; title?: string }
    throw new Error(data.message || data.title || ('Request failed (HTTP ' + response.status + ').'))
  }
  return body as T
}

export async function fetchPlateScans(search?: string): Promise<PlateScanDto[]> {
  const url = search
    ? '/backend-api/PlateScans?search=' + encodeURIComponent(search)
    : '/backend-api/PlateScans'
  const response = await fetch(url, { headers: { Accept: 'application/json' } })
  const result = await readResponse<unknown>(response)
  if (!Array.isArray(result)) throw new Error('Du lieu tu backend khong dung dinh dang.')
  return result as PlateScanDto[]
}

export async function fetchPlateScanStats(): Promise<PlateScanStats> {
  const response = await fetch('/backend-api/PlateScans/stats', { headers: { Accept: 'application/json' } })
  return readResponse<PlateScanStats>(response)
}

export async function deletePlateScan(id: number): Promise<void> {
  const response = await fetch('/backend-api/PlateScans/' + id, {
    method: 'DELETE',
    headers: { Accept: 'application/json' },
  })
  await readResponse<unknown>(response)
}

export async function scanPlate(image: Blob): Promise<ScanResult> {
  const form = new FormData()
  form.append('image', image, 'plate-upload.jpg')
  const response = await fetch('/python-api/scan-plate', { method: 'POST', body: form })
  return readResponse<ScanResult>(response)
}

export async function previewPlate(image: Blob): Promise<PlatePreview> {
  const form = new FormData()
  form.append('image', image, 'camera-frame.jpg')
  const response = await fetch('/python-api/preview-plate', { method: 'POST', body: form })
  return readResponse<PlatePreview>(response)
}
