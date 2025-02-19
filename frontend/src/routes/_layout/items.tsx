import {
  Container,
  Heading,
  SkeletonText,
  Table,
  TableContainer,
  Tbody,
  Td,
  Th,
  Thead,
  Tr,
  Button,
  useDisclosure,
  Modal,
  ModalOverlay,
  ModalContent,
  ModalHeader,
  ModalCloseButton,
  ModalBody,
  ModalFooter,
  FormControl,
  FormLabel,
  Select,
  VStack,
  useToast,
} from "@chakra-ui/react"
import { useQuery, useQueryClient, useMutation } from "@tanstack/react-query"
import { createFileRoute, useNavigate } from "@tanstack/react-router"
import { useEffect, useState } from "react"
import { z } from "zod"
import axios from "axios"

import { ItemsService, type UserPublic } from "../../client"
import ActionsMenu from "../../components/Common/ActionsMenu"
import Navbar from "../../components/Common/Navbar"
import AddItem from "../../components/Items/AddItem"
import { PaginationFooter } from "../../components/Common/PaginationFooter.tsx"
import { UsersService } from "../../client"

const itemsSearchSchema = z.object({
  page: z.number().catch(1),
})

export const Route = createFileRoute("/_layout/items")({
  component: Items,
  validateSearch: (search) => itemsSearchSchema.parse(search),
})

const PER_PAGE = 5

function getItemsQueryOptions({ page }: { page: number }) {
  return {
    queryFn: () =>
      ItemsService.readItems({ skip: (page - 1) * PER_PAGE, limit: PER_PAGE }),
    queryKey: ["items", { page }],
  }
}

// 权限级别枚举
const PERMISSION_LEVELS = {
  READ: "read",
  WRITE: "write",
  ADMIN: "admin"
} as const

type PermissionLevel = typeof PERMISSION_LEVELS[keyof typeof PERMISSION_LEVELS]

interface ItemPermissionsProps {
  itemId: string
  isOpen: boolean
  onClose: () => void
}

function ItemPermissions({ itemId, isOpen, onClose }: ItemPermissionsProps) {
  const toast = useToast()
  const queryClient = useQueryClient()
  const [selectedUserId, setSelectedUserId] = useState("")
  const [selectedRole, setSelectedRole] = useState<PermissionLevel>(PERMISSION_LEVELS.READ)

  // 获取用户列表
  const { data: usersResponse, isLoading, error } = useQuery({
    queryKey: ["users"],
    queryFn: async () => {
      const result = await UsersService.readUsers({ skip: 0, limit: 100 });
      return result;
    },
  });

  // 获取项目当前的权限列表
  const { data: permissions } = useQuery({
    queryKey: ["permissions", itemId],
    queryFn: async () => {
      const response = await axios.get(
        `${import.meta.env.VITE_API_URL}/api/v1/permissions?item_id=${itemId}`,
        {
          headers: {
            Authorization: `Bearer ${localStorage.getItem("access_token")}`,
          },
        }
      )
      return response.data
    }
  })

  // 创建权限的 mutation
  const createPermission = useMutation({
    mutationFn: async (data: { user_id: string; item_id: string; role: string }) => {
      const response = await axios.post(
        `${import.meta.env.VITE_API_URL}/api/v1/permissions`,
        data,
        {
          headers: {
            Authorization: `Bearer ${localStorage.getItem("access_token")}`,
          },
        }
      )
      return response.data
    },
    onSuccess: () => {
      toast({
        title: "权限添加成功",
        status: "success",
      })
      queryClient.invalidateQueries({ queryKey: ["permissions"] })
      onClose()
    },
    onError: () => {
      toast({
        title: "权限添加失败",
        status: "error",
      })
    }
  })

  const handleSubmit = () => {
    if (!selectedUserId) {
      toast({
        title: "请选择用户",
        status: "warning",
      })
      return
    }

    createPermission.mutate({
      user_id: selectedUserId,
      item_id: itemId,
      role: selectedRole
    })
  }

  return (
    <Modal isOpen={isOpen} onClose={onClose}>
      <ModalOverlay />
      <ModalContent>
        <ModalHeader>管理项目权限</ModalHeader>
        <ModalCloseButton />
        <ModalBody>
          <VStack spacing={4}>
            <FormControl>
              <FormLabel>选择用户</FormLabel>
              {isLoading ? (
                <Select isDisabled placeholder="加载中..." />
              ) : error ? (
                <Select isDisabled placeholder="加载失败" />
              ) : (
                <Select
                  placeholder="选择用户"
                  value={selectedUserId}
                  onChange={(e) => setSelectedUserId(e.target.value)}
                >
                  {usersResponse?.data ? (
                    usersResponse.data.map((user) => (
                      <option key={user.id} value={user.id}>
                        {user.email || user.full_name || '未知用户'}
                      </option>
                    ))
                  ) : (
                    <option value="">没有可用用户</option>
                  )}
                </Select>
              )}
              {error && (
                <div style={{ color: 'red', marginTop: '4px', fontSize: '14px' }}>
                  加载用户列表失败
                </div>
              )}
            </FormControl>

            <FormControl>
              <FormLabel>权限级别</FormLabel>
              <Select
                value={selectedRole}
                onChange={(e) => setSelectedRole(e.target.value as typeof PERMISSION_LEVELS[keyof typeof PERMISSION_LEVELS])}
              >
                <option value={PERMISSION_LEVELS.READ}>只读</option>
                <option value={PERMISSION_LEVELS.WRITE}>读写</option>
                <option value={PERMISSION_LEVELS.ADMIN}>管理员</option>
              </Select>
            </FormControl>

            {/* 显示当前权限列表 */}
            {permissions?.data?.length > 0 && (
              <Table size="sm">
                <Thead>
                  <Tr>
                    <Th>用户</Th>
                    <Th>权限</Th>
                  </Tr>
                </Thead>
                <Tbody>
                  {permissions.data.map((perm: any) => (
                    <Tr key={perm.id}>
                      <Td>{perm.user?.email}</Td>
                      <Td>{perm.role}</Td>
                    </Tr>
                  ))}
                </Tbody>
              </Table>
            )}
          </VStack>
        </ModalBody>

        <ModalFooter>
          <Button variant="ghost" mr={3} onClick={onClose}>
            取消
          </Button>
          <Button 
            colorScheme="blue" 
            onClick={handleSubmit}
            isLoading={createPermission.isPending}
          >
            添加权限
          </Button>
        </ModalFooter>
      </ModalContent>
    </Modal>
  )
}

function ItemsTable() {
  const queryClient = useQueryClient()
  const { page } = Route.useSearch()
  const navigate = useNavigate({ from: Route.fullPath })
  const [selectedItemId, setSelectedItemId] = useState<string | null>(null)
  const { isOpen, onOpen, onClose } = useDisclosure()
  
  const setPage = (page: number) =>
    navigate({ search: (prev: {[key: string]: string}) => ({ ...prev, page }) })

  const {
    data: items,
    isPending,
    isPlaceholderData,
  } = useQuery({
    ...getItemsQueryOptions({ page }),
    placeholderData: (prevData) => prevData,
  })

  const hasNextPage = !isPlaceholderData && items?.data.length === PER_PAGE
  const hasPreviousPage = page > 1

  useEffect(() => {
    if (hasNextPage) {
      queryClient.prefetchQuery(getItemsQueryOptions({ page: page + 1 }))
    }
  }, [page, queryClient, hasNextPage])

  return (
    <>
      <TableContainer width="100%">
        <Table size={{ base: "sm", md: "md" }} width="100%">
          <Thead>
            <Tr>
              <Th width="25%">ID</Th>
              <Th width="25%">Title</Th>
              <Th width="30%">Description</Th>
              <Th width="20%">Actions</Th>
            </Tr>
          </Thead>
          {isPending ? (
            <Tbody>
              <Tr>
                {new Array(4).fill(null).map((_, index) => (
                  <Td key={index}>
                    <SkeletonText noOfLines={1} paddingBlock="16px" />
                  </Td>
                ))}
              </Tr>
            </Tbody>
          ) : (
            <Tbody>
              {items?.data.map((item) => (
                <Tr key={item.id} opacity={isPlaceholderData ? 0.5 : 1}>
                  <Td>{item.id}</Td>
                  <Td isTruncated maxWidth="150px">
                    {item.title}
                  </Td>
                  <Td
                    color={!item.description ? "ui.dim" : "inherit"}
                    isTruncated
                    maxWidth="150px"
                  >
                    {item.description || "N/A"}
                  </Td>
                  <Td>
                    <Button
                      size="sm"
                      colorScheme="purple"
                      mr={2}
                      onClick={() => {
                        setSelectedItemId(item.id);
                        onOpen();
                      }}
                    >
                      权限
                    </Button>
                    <ActionsMenu type={"Item"} value={item} />
                  </Td>
                </Tr>
              ))}
            </Tbody>
          )}
        </Table>
      </TableContainer>
      <PaginationFooter
        page={page}
        onChangePage={setPage}
        hasNextPage={hasNextPage}
        hasPreviousPage={hasPreviousPage}
      />

      {selectedItemId && (
        <ItemPermissions
          itemId={selectedItemId}
          isOpen={isOpen}
          onClose={() => {
            onClose();
            setSelectedItemId(null);
          }}
        />
      )}
    </>
  )
}

function Items() {
  const { isOpen, onOpen, onClose } = useDisclosure()
  const queryClient = useQueryClient()
  const currentUser = queryClient.getQueryData<UserPublic>(["currentUser"])
  const navigate = useNavigate({ from: Route.fullPath })

  // 如果不是管理员，重定向到首页
  useEffect(() => {
    if (!currentUser?.is_superuser) {
      navigate({ to: "/" })
    }
  }, [currentUser])

  // 如果不是管理员，不显示任何内容
  if (!currentUser?.is_superuser) {
    return null
  }

  return (
    <>
      <Navbar type="Item" addModalAs={AddItem} />
      <Container maxW="100%" py={8} px={8}>
        <Heading size="lg" mb={8}>
          项目管理
        </Heading>
        <Button onClick={onOpen} mb={8}>
          添加项目
        </Button>
        <ItemsTable />
        <AddItem isOpen={isOpen} onClose={onClose} />
      </Container>
    </>
  )
}
