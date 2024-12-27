import { useMutation } from "@tanstack/react-query"
import { useNavigate } from "@tanstack/react-router"

interface SignUpCredentials {
  email: string
  password: string
  invite_code: string
}

export default function useAuth() {
  const navigate = useNavigate()

  const signUpMutation = useMutation({
    mutationFn: async (credentials: SignUpCredentials) => {
      const response = await fetch(`${API_URL}/auth/register`, {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
        },
        body: JSON.stringify({
          email: credentials.email,
          password: credentials.password,
          invite_code: credentials.invite_code,
        }),
      })

      if (!response.ok) {
        const error = await response.json()
        throw new Error(error.detail || "注册失败，请检查邀请码是否有效")
      }

      return response.json()
    },
    onSuccess: () => {
      navigate({ to: "/login" })
    },
    onError: (error: Error) => {
      setError(error.message)
    },
  })

  return {
    signUpMutation,
    error,
    resetError,
  }
} 