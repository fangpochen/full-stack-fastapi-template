import {
  Box,
  Drawer,
  DrawerBody,
  DrawerCloseButton,
  DrawerContent,
  DrawerOverlay,
  Flex,
  IconButton,
  Image,
  Text,
  useColorModeValue,
  useDisclosure,
} from "@chakra-ui/react"
import { useQueryClient } from "@tanstack/react-query"
import { FiLogOut, FiMenu } from "react-icons/fi"

import Logo from "/assets/images/fastapi-logo.svg"
import type { UserPublic } from "../../client"
import useAuth from "../../hooks/useAuth"
import SidebarItems from "./SidebarItems"

const Sidebar = () => {
  const queryClient = useQueryClient()
  const bgColor = useColorModeValue("white", "gray.800")
  const textColor = useColorModeValue("gray.700", "gray.200")
  const currentUser = queryClient.getQueryData<UserPublic>(["currentUser"])
  const { isOpen, onOpen, onClose } = useDisclosure()
  const { logout } = useAuth()

  const handleLogout = async () => {
    logout()
  }

  return (
    <>
      {/* Mobile */}
      <IconButton
        onClick={onOpen}
        display={{ base: "flex", md: "none" }}
        aria-label="Open Menu"
        position="absolute"
        fontSize="20px"
        m={4}
        icon={<FiMenu />}
      />
      <Drawer isOpen={isOpen} placement="left" onClose={onClose}>
        <DrawerOverlay />
        <DrawerContent maxW="250px">
          <DrawerCloseButton />
          <DrawerBody py={8}>
            <Flex flexDir="column" justify="space-between">
              <Box>
                <Box p={6}>
                  <Text fontSize="xl" fontWeight="bold" color="#009485">
                    阿应工具箱
                  </Text>
                </Box>
                <SidebarItems onClose={onClose} />
                <Flex
                  as="button"
                  onClick={handleLogout}
                  p={2}
                  color="red.500"
                  fontWeight="bold"
                  alignItems="center"
                >
                  <FiLogOut />
                  <Text ml={2}>退出登录</Text>
                </Flex>
              </Box>
              {currentUser?.email && (
                <Text color={textColor} noOfLines={2} fontSize="sm" p={2}>
                  当前用户: {currentUser.email}
                </Text>
              )}
            </Flex>
          </DrawerBody>
        </DrawerContent>
      </Drawer>

      {/* Desktop */}
      <Box
        as="nav"
        pos="sticky"
        top="0"
        w="250px"
        h="100vh"
        bg={bgColor}
        borderRight="1px"
        borderColor="gray.200"
        display={{ base: "none", md: "block" }}
      >
        <Flex flexDir="column" h="full">
          <Box p={6}>
            <Text fontSize="xl" fontWeight="bold" color="#009485">
              阿应工具箱
            </Text>
          </Box>
          <Box flex="1">
            <SidebarItems />
          </Box>
          <Box p={4}>
            <Flex
              as="button"
              onClick={handleLogout}
              p={2}
              color="red.500"
              fontWeight="bold"
              alignItems="center"
              w="full"
            >
              <FiLogOut />
              <Text ml={2}>退出登录</Text>
            </Flex>
            {currentUser?.email && (
              <Text color={textColor} noOfLines={2} fontSize="sm" mt={2}>
                当前用户: {currentUser.email}
              </Text>
            )}
          </Box>
        </Flex>
      </Box>
    </>
  )
}

export default Sidebar
