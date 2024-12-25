import { Box, Heading } from "@chakra-ui/react"
import { createFileRoute } from "@tanstack/react-router"
import { KeyManagement } from "../../components/Keys/KeyManagement"

export const Route = createFileRoute('/_layout/keys')({
  component: KeysPage
})

function KeysPage() {
  return (
    <Box px={4} py={6} w="100%">
      <Heading mb={6}>阿应工具箱 - 密钥管理</Heading>
      <Box maxW="100%" mx="-4">
        <KeyManagement />
      </Box>
    </Box>
  )
}
