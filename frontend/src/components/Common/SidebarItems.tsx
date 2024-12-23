import { Box, Flex, Icon, Text, useColorModeValue } from "@chakra-ui/react"
import { useQueryClient } from "@tanstack/react-query"
import { Link } from "@tanstack/react-router"
import { FiBriefcase, FiHome, FiSettings, FiUsers, FiKey } from "react-icons/fi"

import type { UserPublic } from "../../client"

const items = [
  { icon: FiHome, title: "控制台", path: "/" },
  { icon: FiBriefcase, title: "项目管理", path: "/items" },
  { icon: FiSettings, title: "用户设置", path: "/settings" },
]

interface SidebarItemsProps {
  onClose?: () => void
}

const SidebarItems = ({ onClose }: SidebarItemsProps) => {
  const queryClient = useQueryClient()
  const textColor = useColorModeValue("ui.main", "ui.light")
  const bgActive = useColorModeValue("#E2E8F0", "#4A5568")
  const currentUser = queryClient.getQueryData<UserPublic>(["currentUser"])

  const finalItems = currentUser?.is_superuser
    ? [...items, { icon: FiUsers, title: "管理员", path: "/admin" }]
    : items

  const listItems = finalItems.map(({ icon, title, path }) => (
    <Flex
      as={Link}
      to={path}
      w="100%"
      p={2}
      key={title}
      activeProps={{
        style: {
          background: bgActive,
          borderRadius: "12px",
        },
      }}
      color={textColor}
      onClick={onClose}
    >
      <Icon as={icon} alignSelf="center" />
      <Text ml={2}>{title}</Text>
    </Flex>
  ))

  return (
    <>
      <Box>
        {listItems}
        <Flex
          as={Link}
          to="/keys"
          w="100%"
          p={2}
          key="Keys"
          activeProps={{
            style: {
              background: bgActive,
              borderRadius: "12px",
            },
          }}
          color={textColor}
          onClick={onClose}
        >
          <Icon as={FiKey} alignSelf="center" />
          <Text ml={2}>密钥管理</Text>
        </Flex>
      </Box>
    </>
  )
}

export default SidebarItems
