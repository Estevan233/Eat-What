export type TransportMethod = 'GET' | 'POST' | 'PUT' | 'DELETE'

export type TransportRequest = {
  path: string
  method: TransportMethod
  data?: unknown
  headers: Record<string, string>
  timeout: number
}

export type TransportResponse = {
  statusCode: number
  body: unknown
  requestId?: string
}

export interface Transport {
  execute(request: TransportRequest): Promise<TransportResponse>
}
