import { createFileRoute } from "@tanstack/react-router"
import Register from "../components/Auth/Register"

export const Route = createFileRoute("/register")({
  component: Register,
}) 