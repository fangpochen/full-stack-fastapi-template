import {
  Box,
  Button,
  Flex,
  Table,
  Thead,
  Tbody,
  Tr,
  Th,
  Td,
  IconButton,
  useToast,
  Text,
  TableContainer,
  Switch,
  NumberInput,
  NumberInputField,
  NumberInputStepper,
  NumberIncrementStepper,
  NumberDecrementStepper,
  HStack,
  Checkbox,
  Select,
  ButtonGroup,
  FormControl,
  FormLabel,
} from "@chakra-ui/react"
import { FiTrash2, FiCopy } from "react-icons/fi"
import { useApiKeys, useCreateApiKeys, useDeleteApiKey, useToggleApiKey } from "../../services/api-key"
import { useQueryClient, useQuery } from "@tanstack/react-query"
import { useState } from "react"
import axios from "axios"
import { ItemsService } from "../../client"
import { useUsers } from "../../services/user"

interface ApiKey {
  id: string;
  key: string;
  is_active: boolean;
  created_at: string;
  user_id: string;
  item?: {
    id: string;
    title: string;
  };
  machine_info: Record<string, any>;
}

interface User {
  id: string;
  email: string;
  username: string;
}

const formatMachineInfo = (info: Record<string, any>) => {
  if (Object.keys(info).length === 0) {
    return "未绑定设备"
  }
  return JSON.stringify(info, null, 2)
}

// 在组件外部定义 useItems hook
const useItems = () => {
  return useQuery({
    queryKey: ["items"],
    queryFn: () => ItemsService.readItems()
  })
}

// 添加 hook 来获取当前用户信息
const useCurrentUser = () => {
  return useQuery({
    queryKey: ['current-user'],
    queryFn: async () => {
      const response = await axios.get(`${import.meta.env.VITE_API_URL}/api/v1/users/me`, {
        headers: {
          Authorization: `Bearer ${localStorage.getItem("access_token")}`,
        },
      });
      return response.data;
    },
  });
};

export const KeyManagement = () => {
  const toast = useToast()
  const queryClient = useQueryClient()
  const [count, setCount] = useState(1)
  const [selectedKeys, setSelectedKeys] = useState<string[]>([])
  const [selectedItemId, setSelectedItemId] = useState<string>("")
  const [page, setPage] = useState(1)
  const [pageSize, setPageSize] = useState(10)
  const [selectedUserId, setSelectedUserId] = useState<string>("")
  const { data: users } = useUsers()
  const { data: keysResponse } = useApiKeys({
    page,
    pageSize,
    userId: selectedUserId || undefined
  })
  const { data: itemsResponse } = useItems()
  const createKeysMutation = useCreateApiKeys()
  const deleteKeyMutation = useDeleteApiKey()
  const toggleKeyMutation = useToggleApiKey()
  const keys = keysResponse?.data || []
  const pagination = keysResponse?.pagination || { total: 0, total_pages: 1 }
  const items = itemsResponse?.data || []
  // 使用 hook 获取用户信息
  const { data: currentUser } = useCurrentUser();
  const isAdmin = currentUser?.is_superuser || false;

  const handleSelectAll = (e: React.ChangeEvent<HTMLInputElement>) => {
    if (e.target.checked) {
      setSelectedKeys(keys.map((key: ApiKey) => key.id))
    } else {
      setSelectedKeys([])
    }
  }

  const handleSelect = (id: string) => {
    setSelectedKeys(prev => {
      if (prev.includes(id)) {
        return prev.filter(key => key !== id)
      } else {
        return [...prev, id]
      }
    })
  }

  const handleBatchToggle = async (active: boolean) => {
    try {
      await Promise.all(selectedKeys.map(id => toggleKeyMutation.mutateAsync(id)))
      toast({ 
        status: "success", 
        title: `成功${active ? '启用' : '禁用'}${selectedKeys.length}个密钥` 
      })
      queryClient.invalidateQueries({ queryKey: ["api-keys"] })
      setSelectedKeys([]) // 清空选择
    } catch (error) {
      toast({ status: "error", title: "操作失败" })
    }
  }

  const handleCreate = async () => {
    try {
      await createKeysMutation.mutateAsync({
        count,
        item_id: selectedItemId || undefined
      })
      toast({ status: "success", title: `成功创建 ${count} 个密钥` })
      queryClient.invalidateQueries({ queryKey: ["api-keys"] })
    } catch (error) {
      toast({ status: "error", title: "创建失败" })
    }
  }

  const handleDelete = async (id: string) => {
    try {
      await deleteKeyMutation.mutateAsync(id)
      toast({ status: "success", title: "删除成功" })
      queryClient.invalidateQueries({ queryKey: ["api-keys"] })
    } catch (error) {
      toast({ status: "error", title: "删除失败" })
    }
  }

  const handleToggle = async (id: string) => {
    try {
      await toggleKeyMutation.mutateAsync(id)
      toast({ status: "success", title: "状态更新成功" })
    } catch (error) {
      toast({ status: "error", title: "状态更新失败" })
    }
  }

  const handleCopy = async (text: string) => {
    try {
      // 首先尝试使用传统方法
      const textArea = document.createElement('textarea');
      textArea.style.position = 'fixed';  // 避免页面滚动
      textArea.style.opacity = '0';       // 隐藏元素
      textArea.value = text;
      document.body.appendChild(textArea);
      textArea.focus();
      textArea.select();
      
      const successful = document.execCommand('copy');
      document.body.removeChild(textArea);
      
      if (successful) {
        toast({ 
          status: "success", 
          title: "复制成功",
          position: "top",
          duration: 2000
        });
        return;
      }

      // 如果传统方法失败，尝试现代 Clipboard API
      await navigator.clipboard.writeText(text);
      toast({ 
        status: "success", 
        title: "复制成功",
        position: "top",
        duration: 2000
      });
    } catch (error) {
      console.error('Copy failed:', error);
      toast({ 
        status: "error", 
        title: "复制失败，请手动复制",
        position: "top",
        duration: 2000
      });
    }
  };

  const handleBatchDelete = async () => {
    try {
      await axios.delete(`${import.meta.env.VITE_API_URL}/api/v1/api-keys/batch`, { 
        data: selectedKeys,
        headers: {
          "Content-Type": "application/json",
          Authorization: `Bearer ${localStorage.getItem("access_token")}`,
        }
      });
      toast({ status: "success", title: `成功删除${selectedKeys.length}个密钥` });
      queryClient.invalidateQueries({ queryKey: ["api-keys"] });
      setSelectedKeys([]); 
    } catch (error) {
      console.error('Delete error:', error);
      toast({ status: "error", title: "删除失败" });
    }
  };

  return (
    <Box maxW="100vw" overflowX="auto">
      <HStack spacing={4} mb={4}>
        <NumberInput
          value={count}
          onChange={(_, value) => setCount(value)}
          defaultValue={1}
          min={1}
          max={100}
          w="120px"
          size="md"
        >
          <NumberInputField placeholder="数量" />
          <NumberInputStepper>
            <NumberIncrementStepper />
            <NumberDecrementStepper />
          </NumberInputStepper>
        </NumberInput>
        
        <Select
          placeholder="选择项目"
          value={selectedItemId}
          onChange={(e) => setSelectedItemId(e.target.value)}
          w="200px"
        >
          {items.map((item) => (
            <option key={item.id} value={item.id}>
              {item.title}
            </option>
          ))}
        </Select>

        <Button
          colorScheme="purple"
          bg="#6B46C1"
          _hover={{ bg: "#805AD5" }}
          onClick={handleCreate}
          isLoading={createKeysMutation.isPending}
        >
          创建密钥
        </Button>
        {selectedKeys.length > 0 && (
          <>
            <Button
              colorScheme="red"
              onClick={() => handleBatchToggle(false)}
              isLoading={toggleKeyMutation.isPending}
            >
              批量禁用
            </Button>
            <Button
              colorScheme="green"
              onClick={() => handleBatchToggle(true)}
              isLoading={toggleKeyMutation.isPending}
            >
              批量启用
            </Button>
            <Button
              colorScheme="red"
              onClick={handleBatchDelete}
              isLoading={deleteKeyMutation.isPending}
            >
              批量删除
            </Button>
          </>
        )}
      </HStack>

      <Flex mb={4} gap={4}>
        {isAdmin && (
          <FormControl w="300px">
            <FormLabel>用户筛选</FormLabel>
            <Select
              value={selectedUserId}
              onChange={(e) => {
                setSelectedUserId(e.target.value);
                setPage(1);
              }}
              placeholder="全部用户"
            >
              {users?.map((user: User) => (
                <option key={user.id} value={user.id}>
                  {user.email || user.username}
                </option>
              ))}
            </Select>
          </FormControl>
        )}
      </Flex>

      <TableContainer minW="1200px">
        <Table size="md">
          <Thead>
            <Tr>
              <Th width="50px">
                <Checkbox
                  isChecked={selectedKeys.length === keys.length}
                  isIndeterminate={selectedKeys.length > 0 && selectedKeys.length < keys.length}
                  onChange={handleSelectAll}
                />
              </Th>
              <Th width="300px">密钥</Th>
              <Th width="200px">项目</Th>
              <Th width="400px">设备信息</Th>
              <Th width="200px">用户ID</Th>
              <Th width="200px">创建时间</Th>
              <Th width="100px">状态</Th>
              <Th width="100px">操作</Th>
            </Tr>
          </Thead>
          <Tbody>
            {keys.map((key: ApiKey) => (
              <Tr key={key.id}>
                <Td>
                  <Checkbox
                    isChecked={selectedKeys.includes(key.id)}
                    onChange={() => handleSelect(key.id)}
                  />
                </Td>
                <Td>
                  <Flex gap={2} align="center" width="100%">
                    <Text 
                      fontFamily="mono" 
                      fontSize="sm"
                      whiteSpace="nowrap"
                      overflow="hidden"
                      textOverflow="ellipsis"
                      maxW="350px"
                    >
                      {key.key}
                    </Text>
                    <IconButton
                      aria-label="Copy key"
                      icon={<FiCopy />}
                      size="sm"
                      variant="ghost"
                      onClick={() => handleCopy(key.key)}
                    />
                  </Flex>
                </Td>
                <Td>
                  <Text color={key.item ? "black" : "gray.500"}>
                    {key.item ? key.item.title : "未关联项目"}
                  </Text>
                </Td>
                <Td>
                  <Box
                    whiteSpace="pre-wrap"
                    fontFamily="mono"
                    fontSize="sm"
                    p={2}
                    bg="gray.50"
                    borderRadius="md"
                    maxH="200px"
                    overflowY="auto"
                    minW="350px"
                  >
                    {formatMachineInfo(key.machine_info)}
                  </Box>
                </Td>
                <Td>
                  <Text fontFamily="mono">{key.user_id || '未绑定用户'}</Text>
                </Td>
                <Td>{new Date(key.created_at).toLocaleString()}</Td>
                <Td>
                  <Switch
                    isChecked={key.is_active}
                    onChange={() => handleToggle(key.id)}
                    colorScheme="green"
                  />
                </Td>
                <Td>
                  <IconButton
                    aria-label="Delete key"
                    icon={<FiTrash2 />}
                    colorScheme="red"
                    size="sm"
                    onClick={() => handleDelete(key.id)}
                    isLoading={deleteKeyMutation.isPending}
                  />
                </Td>
              </Tr>
            ))}
          </Tbody>
        </Table>
      </TableContainer>

      <Flex justify="space-between" align="center" mt={4} px={4}>
        <Text fontSize="sm">
          共 {pagination.total} 条记录
        </Text>
        <HStack spacing={2}>
          <Select
            size="sm"
            value={pageSize}
            onChange={(e) => {
              setPageSize(Number(e.target.value));
              setPage(1);
            }}
            w="120px"
          >
            <option value={10}>10 条/页</option>
            <option value={20}>20 条/页</option>
            <option value={50}>50 条/页</option>
          </Select>

          <ButtonGroup size="sm" variant="outline">
            <Button
              onClick={() => setPage(p => p - 1)}
              isDisabled={page <= 1}
            >
              上一页
            </Button>
            <Button
              onClick={() => setPage(p => p + 1)}
              isDisabled={page >= pagination.total_pages}
            >
              下一页
            </Button>
          </ButtonGroup>
          
          <Text fontSize="sm">
            第 {page} / {pagination.total_pages} 页
          </Text>
        </HStack>
      </Flex>
    </Box>
  )
}