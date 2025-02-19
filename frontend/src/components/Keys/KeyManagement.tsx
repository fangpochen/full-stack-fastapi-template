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
  Input,
} from "@chakra-ui/react"
import { FiTrash2, FiCopy } from "react-icons/fi"
import { useApiKeys, useCreateApiKeys, useDeleteApiKey, useToggleApiKey } from "../../services/api-key"
import { useQueryClient, useQuery } from "@tanstack/react-query"
import { useState } from "react"
import axios from "axios"
import { ItemsService, UsersService } from "../../client"

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
  expires_at?: string;
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
  const [expiresAt, setExpiresAt] = useState(() => {
    const date = new Date();
    date.setMonth(date.getMonth() + 1);
    return date.toISOString().slice(0, 16);
  });
  const [page, setPage] = useState(1)
  const [pageSize, setPageSize] = useState(10)
  const [selectedUserId, setSelectedUserId] = useState<string>("")
  const { data: usersResponse } = useQuery({
    queryKey: ["users"],
    queryFn: () => UsersService.readUsers({ skip: 0, limit: 100 })
  })
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
      if (!selectedItemId) {
        toast({ status: "error", title: "请选择项目" });
        return;
      }
      
      await createKeysMutation.mutateAsync({
        count,
        item_id: selectedItemId,
        expires_at: expiresAt
      })
      toast({ status: "success", title: `成功创建 ${count} 个密钥` })
      queryClient.invalidateQueries({ queryKey: ["api-keys"] })
    } catch (error: any) {
      toast({ 
        status: "error", 
        title: "创建失败", 
        description: error.response?.data?.detail || "未知错误" 
      })
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

  // 添加批量续约的处理函数
  const handleBatchRenew = async (newExpiresAt: string) => {
    try {
      await axios.put(
        `${import.meta.env.VITE_API_URL}/api/v1/api-keys/batch-renew`,
        {
          key_ids: selectedKeys,
          expires_at: newExpiresAt
        },
        {
          headers: {
            "Content-Type": "application/json",
            Authorization: `Bearer ${localStorage.getItem("access_token")}`,
          },
        }
      );
      toast({ status: "success", title: `成功续约${selectedKeys.length}个密钥` });
      queryClient.invalidateQueries({ queryKey: ["api-keys"] });
      setSelectedKeys([]);
    } catch (error) {
      console.error('Renew error:', error);
      toast({ status: "error", title: "续约失败" });
    }
  };

  return (
    <Box maxW="100vw" overflowX="auto">
      <HStack spacing={4} mb={4}>
        <FormControl w="120px">
          <FormLabel fontSize="sm">数量</FormLabel>
          <NumberInput
            value={count}
            onChange={(_, value) => setCount(value)}
            defaultValue={1}
            min={1}
            max={100}
            size="md"
          >
            <NumberInputField placeholder="数量" />
            <NumberInputStepper>
              <NumberIncrementStepper />
              <NumberDecrementStepper />
            </NumberInputStepper>
          </NumberInput>
        </FormControl>
        
        <FormControl w="200px" isRequired>
          <FormLabel fontSize="sm">项目</FormLabel>
          <Select
            placeholder="选择项目"
            value={selectedItemId}
            onChange={(e) => setSelectedItemId(e.target.value)}
          >
            {items.map((item) => (
              <option key={item.id} value={item.id}>
                {item.title}
              </option>
            ))}
          </Select>
        </FormControl>

        <FormControl w="400px">
          <FormLabel fontSize="sm">过期时间</FormLabel>
          <HStack>
            <Input
              type="datetime-local"
              value={expiresAt}
              onChange={(e) => setExpiresAt(e.target.value)}
            />
            <ButtonGroup size="sm" variant="outline">
              <Button
                onClick={() => {
                  const date = new Date();
                  date.setMonth(date.getMonth() + 1);
                  setExpiresAt(date.toISOString().slice(0, 16));
                }}
              >
                1个月
              </Button>
              <Button
                onClick={() => {
                  const date = new Date();
                  date.setMonth(date.getMonth() + 3);
                  setExpiresAt(date.toISOString().slice(0, 16));
                }}
              >
                3个月
              </Button>
              <Button
                onClick={() => {
                  const date = new Date();
                  date.setFullYear(date.getFullYear() + 1);
                  setExpiresAt(date.toISOString().slice(0, 16));
                }}
              >
                1年
              </Button>
              <Button
                colorScheme="purple"
                onClick={() => {
                  setExpiresAt("9999-12-31T23:59");
                }}
              >
                永久
              </Button>
            </ButtonGroup>
          </HStack>
        </FormControl>

        <Button
          colorScheme="blue"
          onClick={handleCreate}
          isLoading={createKeysMutation.isPending}
        >
          创建密钥
        </Button>
      </HStack>

      <Flex mb={4} gap={4} align="center">
        <Text fontWeight="medium">用户筛选</Text>
        {isAdmin && (
          <Select
            w="200px"
            value={selectedUserId}
            onChange={(e) => {
              setSelectedUserId(e.target.value);
              setPage(1);
            }}
            placeholder="全部用户"
            size="sm"
          >
            <option value="">全部用户</option>
            {usersResponse?.data?.map((user: { id: string; email: string }) => (
              <option key={user.id} value={user.id}>
                {user.email}
              </option>
            ))}
          </Select>
        )}

        {selectedKeys.length > 0 && (
          <>
            <ButtonGroup size="sm">
              <Button
                colorScheme="red"
                onClick={() => handleBatchToggle(false)}
                isLoading={toggleKeyMutation.isPending}
                size="sm"
              >
                批量禁用
              </Button>
              <Button
                colorScheme="green"
                onClick={() => handleBatchToggle(true)}
                isLoading={toggleKeyMutation.isPending}
                size="sm"
              >
                批量启用
              </Button>
              <Button
                colorScheme="red"
                onClick={handleBatchDelete}
                isLoading={deleteKeyMutation.isPending}
                size="sm"
              >
                批量删除
              </Button>
            </ButtonGroup>
            <ButtonGroup size="sm">
              <Button
                colorScheme="blue"
                onClick={() => {
                  const date = new Date();
                  date.setMonth(date.getMonth() + 1);
                  handleBatchRenew(date.toISOString());
                }}
                size="sm"
              >
                续约1个月
              </Button>
              <Button
                colorScheme="blue"
                onClick={() => {
                  const date = new Date();
                  date.setMonth(date.getMonth() + 3);
                  handleBatchRenew(date.toISOString());
                }}
                size="sm"
              >
                续约3个月
              </Button>
              <Button
                colorScheme="blue"
                onClick={() => {
                  const date = new Date();
                  date.setFullYear(date.getFullYear() + 1);
                  handleBatchRenew(date.toISOString());
                }}
                size="sm"
              >
                续约1年
              </Button>
              <Button
                colorScheme="purple"
                onClick={() => {
                  handleBatchRenew("9999-12-31T23:59:00");
                }}
                size="sm"
              >
                永久有效
              </Button>
            </ButtonGroup>
          </>
        )}
      </Flex>

      <TableContainer minW="800px">
        <Table size="sm">
          <Thead>
            <Tr>
              <Th width="30px">
                <Checkbox
                  isChecked={selectedKeys.length === keys.length}
                  isIndeterminate={selectedKeys.length > 0 && selectedKeys.length < keys.length}
                  onChange={handleSelectAll}
                />
              </Th>
              <Th width="200px">密钥</Th>
              <Th width="120px">项目</Th>
              <Th width="200px">设备信息</Th>
              <Th width="120px">用户ID</Th>
              <Th width="100px">创建时间</Th>
              <Th width="100px">过期时间</Th>
              <Th width="60px">状态</Th>
              <Th width="60px">操作</Th>
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
                  <Flex gap={1} align="center" width="100%">
                    <Text 
                      fontFamily="mono" 
                      fontSize="xs"
                      whiteSpace="nowrap"
                      overflow="hidden"
                      textOverflow="ellipsis"
                      maxW="160px"
                    >
                      {key.key}
                    </Text>
                    <IconButton
                      aria-label="Copy key"
                      icon={<FiCopy />}
                      size="xs"
                      variant="ghost"
                      onClick={() => handleCopy(key.key)}
                    />
                  </Flex>
                </Td>
                <Td>
                  <Text fontSize="xs" color={key.item ? "black" : "gray.500"} isTruncated maxW="120px">
                    {key.item ? key.item.title : "未关联项目"}
                  </Text>
                </Td>
                <Td>
                  <Box
                    whiteSpace="pre-wrap"
                    fontFamily="mono"
                    fontSize="xs"
                    p={1}
                    bg="gray.50"
                    borderRadius="sm"
                    maxH="100px"
                    overflowY="auto"
                    maxW="200px"
                  >
                    {formatMachineInfo(key.machine_info)}
                  </Box>
                </Td>
                <Td>
                  <Text fontFamily="mono" fontSize="xs" isTruncated maxW="120px">{key.user_id || '未绑定用户'}</Text>
                </Td>
                <Td>
                  <Text fontSize="xs">{new Date(key.created_at).toLocaleDateString()}</Text>
                </Td>
                <Td>
                  <Text fontSize="xs">{key.expires_at ? new Date(key.expires_at).toLocaleDateString() : '永不过期'}</Text>
                </Td>
                <Td>
                  <Switch
                    size="sm"
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
                    size="xs"
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