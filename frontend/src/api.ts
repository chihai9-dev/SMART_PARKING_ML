export type TicketDto = {
  ticketId: number
  ticketCode: string
  plate: string
  vehicleType: string
  entryTime: string
  entryImagePath?: string | null
  plateImagePath?: string | null
  exitTime?: string | null
  exitImagePath?: string | null
  status: number | string
  penaltyAmount: number
  createdAt?: string
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
  [key: string]: unknown
}

export type GateTicketResult = {
  ticket_id?: number | null
  ticket_code?: string | null
  plate?: string | null
  vehicle_type?: string | null
  entry_time?: string | null
  exit_time?: string | null
  status?: number | string
  status_code?: number
  penalty_amount?: number
}

export type GatePredictionResult = {
  estimated_exit?: string | null
  recommended_zone?: string | null
  behavior?: string | null
  current_demand?: number | null
  duration_minutes?: number | null
}

export type GateEventResult = {
  status?: string
  event?: string
  message?: string
  plate?: string
  ticket?: GateTicketResult
  prediction?: GatePredictionResult
  [key: string]: unknown
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

export async function fetchTickets(): Promise<TicketDto[]> {
  const response = await fetch('/backend-api/Tickets', {
    headers: { Accept: 'application/json' },
  })

  const result = await readResponse<unknown>(response)
  if (!Array.isArray(result)) throw new Error('Dữ liệu vé từ backend không đúng định dạng.')
  return result as TicketDto[]
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

export async function submitGateEvent(
  mode: 'entry' | 'exit',
  image: Blob,
  preview: PlatePreview | null,
): Promise<GateEventResult> {
  const form = new FormData()
  form.append('mode', mode)
  form.append('image', image, 'camera-frame.jpg')

  if (preview && preview.plate) form.append('plate_hint', preview.plate)
  if (preview && typeof preview.confidence === 'number') {
    form.append('preview_confidence', String(preview.confidence))
  }
  if (preview && preview.crop_jpeg_b64) {
    form.append('preview_crop_jpeg_b64', preview.crop_jpeg_b64)
  }

  const response = await fetch('/python-api/gate-event', {
    method: 'POST',
    body: form,
  })

  return readResponse<GateEventResult>(response)
}
