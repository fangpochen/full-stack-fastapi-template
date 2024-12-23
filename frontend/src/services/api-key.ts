import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query"
import { ApiError } from "../client"

const API_URL = import.meta.env.VITE_API_URL + "/api/v1"

export const useApiKeys = () => {
  return useQuery<API.ApiKeysResponse>({
    queryKey: ["api-keys"],
    queryFn: async () => {
      const response = await fetch(`${API_URL}/api-keys`, {
        headers: {
          Authorization: `Bearer ${localStorage.getItem("access_token")}`,
        },
      })
      if (!response.ok) throw new ApiError(response, "Failed to fetch API keys")
      return response.json()
    },
  })
}

// 类型定义
declare namespace API {
  interface ApiKey {
    id: string
    key: string
    is_active: boolean
    created_at: string
    expires_at: string | null
  }

  interface ApiKeysResponse {
    data: ApiKey[]
    count: number
  }
}

export const useCreateApiKeys = () => {
  return useMutation({
    mutationFn: async (count: number) => {
      const response = await fetch(`${API_URL}/api-keys/create`, {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
          Authorization: `Bearer ${localStorage.getItem("access_token")}`,
        },
        body: JSON.stringify({ count }),
      })
      if (!response.ok) throw new ApiError(response, "Failed to create API keys")
      return response.json()
    },
  })
}

export const useDeleteApiKey = () => {
  return useMutation({
    mutationFn: async (id: string) => {
      const response = await fetch(`${API_URL}/api-keys/${id}`, {
        method: "DELETE",
        headers: {
          Authorization: `Bearer ${localStorage.getItem("access_token")}`,
        },
      })
      if (!response.ok) throw new ApiError(response, "Failed to delete API key")
    },
  })
}

export const useToggleApiKey = () => {
  const queryClient = useQueryClient()
  
  return useMutation({
    mutationFn: async (id: string) => {
      const response = await fetch(`${API_URL}/api-keys/${id}/toggle`, {
        method: "PUT",
        headers: {
          Authorization: `Bearer ${localStorage.getItem("access_token")}`,
        },
      })
      if (!response.ok) throw new ApiError(response, "Failed to toggle API key")
      return response.json()
    },
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["api-keys"] })
    },
  })
}

export async function getApiKeys() {
  const response = await fetch(`${API_URL}/api-keys`, {
    headers: {
      Authorization: `Bearer ${localStorage.getItem("access_token")}`,
    },
  })
  if (!response.ok) throw new ApiError(response, "Failed to fetch API keys")
  return response.json()
} 