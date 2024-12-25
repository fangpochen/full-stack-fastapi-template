// This file is auto-generated by @hey-api/openapi-ts
import { OpenAPI } from "./core/OpenAPI"

export { ApiError as CoreApiError } from "./core/ApiError"
export { CancelablePromise, CancelError } from "./core/CancelablePromise"
export { OpenAPI, type OpenAPIConfig } from "./core/OpenAPI"
export * from "./sdk.gen"
export * from "./types.gen"

export interface ApiKey {
  id: number
  name: string
  key?: string
  created_at: string
  is_active: boolean
}

export interface CreateApiKeyRequest {
  name: string
}

export class ApiError extends Error {
  constructor(
    public response: Response | undefined,
    message: string,
    public status: number = response?.status || 500
  ) {
    super(message)
    this.name = 'ApiError'
  }
}

export class ApiKeysService {
  static async listApiKeys(): Promise<ApiKey[]> {
    try {
      const response = await fetch(`${OpenAPI.BASE}/api/keys`, {
        method: 'GET',
        headers: {
          'Authorization': `Bearer ${localStorage.getItem('access_token')}`,
          'Content-Type': 'application/json',
        },
      })
      if (!response.ok) {
        const error = await response.json()
        throw new ApiError(response, error.detail || 'Failed to fetch keys', response.status)
      }
      return response.json()
    } catch (error) {
      if (error instanceof ApiError) throw error
      throw new ApiError(undefined, 'Network error', 500)
    }
  }

  static async createApiKey(data: CreateApiKeyRequest): Promise<ApiKey> {
    try {
      const token = localStorage.getItem('access_token');
      if (!token) {
        throw new ApiError(undefined, 'No authentication token found');
      }

      const response = await fetch(`${OpenAPI.BASE}/api/keys`, {
        method: 'POST',
        headers: {
          'Authorization': `Bearer ${token}`,
          'Content-Type': 'application/json',
        },
        body: JSON.stringify(data),
      })
      if (!response.ok) {
        const error = await response.json()
        throw new ApiError(response, error.detail || 'Failed to create key')
      }
      return response.json()
    } catch (error) {
      if (error instanceof ApiError) throw error
      throw new ApiError(undefined, 'Network error')
    }
  }

  static async deleteApiKey(id: string): Promise<void> {
    try {
      const response = await fetch(`${OpenAPI.BASE}/api/keys/${id}`, {
        method: 'DELETE',
        headers: {
          'Authorization': `Bearer ${localStorage.getItem('access_token')}`,
          'Content-Type': 'application/json',
        },
      })
      if (!response.ok) {
        const error = await response.json()
        throw new ApiError(response, error.detail || 'Failed to delete key', response.status)
      }
    } catch (error) {
      if (error instanceof ApiError) throw error
      throw new ApiError(undefined, 'Network error', 500)
    }
  }

  static async toggleApiKey(id: number): Promise<ApiKey> {
    try {
      const token = localStorage.getItem('access_token');
      if (!token) {
        throw new ApiError(undefined, 'No authentication token found');
      }

      const response = await fetch(`${OpenAPI.BASE}/api/keys/${id}/toggle`, {
        method: 'PUT',
        headers: {
          'Authorization': `Bearer ${token}`,
          'Content-Type': 'application/json',
        },
      })
      if (!response.ok) {
        const error = await response.json()
        throw new ApiError(response, error.detail || 'Failed to toggle key')
      }
      return response.json()
    } catch (error) {
      if (error instanceof ApiError) throw error
      throw new ApiError(undefined, 'Network error')
    }
  }
}
