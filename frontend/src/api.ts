export type PlateScanDto = {
  scanId: number
  plate: string
  vehicleType: string
  confidence: number
  imagePath?: string | null
  cropImagePath?: string | null
  scanTime: string
  note?: string | null
  createdAt?: string
}

export type PlateScanStats = {
  totalScans: number
  todayScans: number
  motorbikes: number
  cars: number
  averageConfidence: number
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
  vehicle_type?: string
  bbox?: number[]
  [key: string]: unknown
}

export type ScanResult = {
  status: string
  plate?: string
  valid?: boolean
  confidence?: number
  engine?: string
  message?: string
  vehicle_type?: string
  bbox?: number[]
  crop_jpeg_b64?: string
  annotated_jpeg_b64?: string
  image_path?: string
  crop_path?: string
  [key: string]: unknown
}

type LoginResponse = {
  token: string
  expiresInMinutes?: number
}

async function readResponse<T>(response: Response): Promise<T> {
  const text = await response.text()
  let body: unknown = {}

  if (text) {
    try {
      body = JSON.parse(text)
    } catch {
      body = { message: text }
    }
  }

  if (!response.ok) {
    const data = body as { message?: string; title?: string }
    throw new Error(data.message || data.title || ('Yêu cầu thất bại (HTTP ' + response.status + ').'))
  }

  return body as T
}

export async function login(username: string, password: string): Promise<LoginResponse> {
  const response = await fetch('/backend-api/Auth/login', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json', Accept: 'application/json' },
    body: JSON.stringify({ username, password }),
  })

  const result = await readResponse<LoginResponse>(response)
  if (!result.token) throw new Error('Backend không trả về mã đăng nhập.')
  return result
}

export async function fetchPlateScans(token?: string, search?: string): Promise<PlateScanDto[]> {
  const url = search ? `/backend-api/PlateScans?search=${encodeURIComponent(search)}` : '/backend-api/PlateScans'
  const headers: Record<string, string> = { Accept: 'application/json' }
  if (token) headers['Authorization'] = `Bearer ${token}`

  const response = await fetch(url, { headers })
  const result = await readResponse<unknown>(response)
  if (!Array.isArray(result)) throw new Error('Dữ liệu quét từ backend không đúng định dạng.')
  return result as PlateScanDto[]
}

export async function fetchPlateScanStats(token?: string): Promise<PlateScanStats> {
  const headers: Record<string, string> = { Accept: 'application/json' }
  if (token) headers['Authorization'] = `Bearer ${token}`

  const response = await fetch('/backend-api/PlateScans/stats', { headers })
  return readResponse<PlateScanStats>(response)
}

export async function deletePlateScan(id: number, token?: string): Promise<void> {
  const headers: Record<string, string> = { Accept: 'application/json' }
  if (token) headers['Authorization'] = `Bearer ${token}`

  const response = await fetch(`/backend-api/PlateScans/${id}`, {
    method: 'DELETE',
    headers,
  })
  await readResponse<unknown>(response)
}

export async function scanPlate(image: Blob): Promise<ScanResult> {
  const form = new FormData()
  form.append('image', image, 'plate-upload.jpg')

  const response = await fetch('/python-api/scan-plate', {
    method: 'POST',
    body: form,
  })

  return readResponse<ScanResult>(response)
}

export async function previewPlate(image: Blob): Promise<PlatePreview> {
  const form = new FormData()
  form.append('image', image, 'camera-frame.jpg')

  const response = await fetch('/python-api/preview-plate', {
    method: 'POST',
    body: form,
  })

  return readResponse<PlatePreview>(response)
}

export async function createPlateScan(
  scan: {
    plate: string
    vehicleType: string
    confidence: number
    imagePath?: string | null
    cropImagePath?: string | null
    note?: string | null
  },
  token?: string
): Promise<PlateScanDto> {
  const headers: Record<string, string> = {
    'Content-Type': 'application/json',
    Accept: 'application/json',
  }
  if (token) headers['Authorization'] = `Bearer ${token}`

  const response = await fetch('/backend-api/PlateScans', {
    method: 'POST',
    headers,
    body: JSON.stringify(scan),
  })

  return readResponse<PlateScanDto>(response)
}
