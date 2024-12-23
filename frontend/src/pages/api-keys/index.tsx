import { useState } from 'react';
import {
  Button,
  Card,
  Table,
  message,
  Popconfirm,
  Space,
  Tag,
  Modal,
  InputNumber,
} from 'antd';
import type { ColumnsType } from 'antd/es/table';
import { PageContainer } from '@ant-design/pro-components';
import { useRequest } from '@umijs/max';
import { createApiKeys, deleteApiKey, getApiKeys } from '@/services/api-key';

interface ApiKey {
  id: string;
  key: string;
  is_active: boolean;
  created_at: string;
  expires_at: string | null;
}

const ApiKeysPage: React.FC = () => {
  const [messageApi, contextHolder] = message.useMessage();
  const [isModalOpen, setIsModalOpen] = useState(false);
  const [count, setCount] = useState(1);

  // 获取密钥列表
  const { data, loading, refresh } = useRequest(getApiKeys);

  // 批量创建新密钥
  const handleCreate = async () => {
    try {
      const result = await createApiKeys({ count });
      messageApi.success(`成功创建 ${count} 个密钥`);
      setIsModalOpen(false);
      refresh();
    } catch (error) {
      messageApi.error('创建失败');
    }
  };

  // 删除密钥
  const handleDelete = async (id: string) => {
    try {
      await deleteApiKey(id);
      messageApi.success('删除成功');
      refresh();
    } catch (error) {
      messageApi.error('删除失败');
    }
  };

  const columns: ColumnsType<ApiKey> = [
    {
      title: 'API Key',
      dataIndex: 'key',
      key: 'key',
      copyable: true,
    },
    {
      title: '状态',
      dataIndex: 'is_active',
      key: 'is_active',
      render: (active: boolean) => (
        <Tag color={active ? 'success' : 'error'}>
          {active ? '激活' : '未激活'}
        </Tag>
      ),
    },
    {
      title: '创建时间',
      dataIndex: 'created_at',
      key: 'created_at',
    },
    {
      title: '过期时间',
      dataIndex: 'expires_at',
      key: 'expires_at',
    },
    {
      title: '操作',
      key: 'action',
      render: (_, record) => (
        <Space>
          <Popconfirm
            title="确定要删除这个密钥吗？"
            onConfirm={() => handleDelete(record.id)}
          >
            <Button type="link" danger>
              删除
            </Button>
          </Popconfirm>
        </Space>
      ),
    },
  ];

  return (
    <PageContainer>
      {contextHolder}
      <Card>
        <Button
          type="primary"
          onClick={() => setIsModalOpen(true)}
          style={{ marginBottom: 16 }}
        >
          批量生成密钥
        </Button>
        <Table
          columns={columns}
          dataSource={data?.data}
          loading={loading}
          rowKey="id"
        />
      </Card>

      <Modal
        title="批量生成密钥"
        open={isModalOpen}
        onOk={handleCreate}
        onCancel={() => setIsModalOpen(false)}
      >
        <div style={{ marginBottom: 16 }}>
          <span style={{ marginRight: 8 }}>生成数量：</span>
          <InputNumber
            min={1}
            max={100}
            value={count}
            onChange={(value) => setCount(value || 1)}
          />
        </div>
      </Modal>
    </PageContainer>
  );
};

export default ApiKeysPage; 