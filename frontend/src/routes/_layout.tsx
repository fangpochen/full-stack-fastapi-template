import { Box, Flex } from "@chakra-ui/react"
import { Outlet, createFileRoute } from "@tanstack/react-router"
import Sidebar from "../components/Common/Sidebar"

export const Route = createFileRoute('/_layout')({
  component: Layout
})

function Layout() {
  return (
    <Flex minH="100vh">
      <Sidebar />
      <Box flex="1" p={4}>
        <Outlet />
      </Box>
    </Flex>
  )
}
