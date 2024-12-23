import { Box, Flex, Text, VStack, Image } from "@chakra-ui/react"
// ... 其他导入保持不变

interface SidebarProps {
  title: string
  logo?: string
}

export function Sidebar({ title, logo }: SidebarProps) {
  return (
    <Box
      w="240px"
      h="100vh"
      bg="white"
      borderRight="1px"
      borderColor="gray.200"
      position="sticky"
      top={0}
    >
      <Flex p={4} align="center" borderBottom="1px" borderColor="gray.200">
        {logo && (
          <Image
            src={logo}
            alt="Logo"
            boxSize="32px"
            mr={2}
          />
        )}
        <Text fontSize="xl" fontWeight="bold">
          {title}
        </Text>
      </Flex>
      
      {/* 其他菜单项保持不变 */}
    </Box>
  )
} 