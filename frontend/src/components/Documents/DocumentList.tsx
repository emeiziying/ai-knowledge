import React from 'react';
import {
  Table,
  Tag,
  Button,
  Space,
  Typography,
  Tooltip,
  Popconfirm,
  Progress,
  message
} from 'antd';
import {
  EyeOutlined,
  DeleteOutlined,
  DownloadOutlined,
  FileTextOutlined,
  FilePdfOutlined,
  FileWordOutlined,
  FileOutlined
} from '@ant-design/icons';
import { Document } from '../../types/api';
import { useDocumentStore } from '../../stores/documentStore';
import { formatFileSize, formatDate } from '../../utils';

const { Text } = Typography;

interface DocumentListProps {
  documents: Document[];
  pagination: {
    total: number;
    page: number;
    limit: number;
    pages: number;
  };
  onPageChange: (page: number, pageSize?: number) => void;
  onViewDetails: (documentId: string) => void;
  onRefresh: () => void;
}

const DocumentList: React.FC<DocumentListProps> = ({
  documents,
  pagination,
  onPageChange,
  onViewDetails,
  onRefresh
}) => {
  const { deleteDocument, isLoading } = useDocumentStore();

  const getFileIcon = (mimeType: string) => {
    if (mimeType.includes('pdf')) return <FilePdfOutlined style={{ color: '#ff4d4f' }} />;
    if (mimeType.includes('word') || mimeType.includes('document')) return <FileWordOutlined style={{ color: '#1890ff' }} />;
    if (mimeType.includes('text')) return <FileTextOutlined style={{ color: '#52c41a' }} />;
    return <FileOutlined style={{ color: '#8c8c8c' }} />;
  };

  const getStatusTag = (status: Document['status']) => {
    const statusConfig = {
      processing: { color: 'processing', text: '处理中' },
      completed: { color: 'success', text: '已完成' },
      failed: { color: 'error', text: '处理失败' }
    };
    
    const config = statusConfig[status];
    return <Tag color={config.color}>{config.text}</Tag>;
  };

  const handleDelete = async (documentId: string, documentName: string) => {
    try {
      await deleteDocument(documentId);
      message.success(`文档 "${documentName}" 删除成功`);
      onRefresh();
    } catch (error) {
      message.error('删除文档失败');
    }
  };

  const handleDownload = (document: Document) => {
    // Create download link
    const link = window.document.createElement('a');
    link.href = `/api/v1/documents/${document.id}/download`;
    link.download = document.original_name;
    link.click();
  };

  const columns = [
    {
      title: '文档',
      dataIndex: 'original_name',
      key: 'name',
      render: (name: string, record: Document) => (
        <Space>
          {getFileIcon(record.mime_type)}
          <div>
            <div>
              <Text strong>{name}</Text>
            </div>
            <div>
              <Text type="secondary" style={{ fontSize: '12px' }}>
                {formatFileSize(record.file_size)}
              </Text>
            </div>
          </div>
        </Space>
      ),
    },
    {
      title: '状态',
      dataIndex: 'status',
      key: 'status',
      width: 100,
      render: (status: Document['status']) => (
        <div>
          {getStatusTag(status)}
          {status === 'processing' && (
            <Progress
              percent={75} // This would come from processing status API
              size="small"
              style={{ marginTop: 4 }}
            />
          )}
        </div>
      ),
    },
    {
      title: '上传时间',
      dataIndex: 'created_at',
      key: 'created_at',
      width: 150,
      render: (date: string) => (
        <Tooltip title={new Date(date).toLocaleString()}>
          <Text type="secondary">{formatDate(date)}</Text>
        </Tooltip>
      ),
    },
    {
      title: '操作',
      key: 'actions',
      width: 150,
      render: (_: any, record: Document) => (
        <Space size="small">
          <Tooltip title="查看详情">
            <Button
              type="text"
              icon={<EyeOutlined />}
              onClick={() => onViewDetails(record.id)}
            />
          </Tooltip>
          
          <Tooltip title="下载">
            <Button
              type="text"
              icon={<DownloadOutlined />}
              onClick={() => handleDownload(record)}
              disabled={record.status !== 'completed'}
            />
          </Tooltip>
          
          <Popconfirm
            title="确认删除"
            description={`确定要删除文档 "${record.original_name}" 吗？`}
            onConfirm={() => handleDelete(record.id, record.original_name)}
            okText="删除"
            cancelText="取消"
            okType="danger"
          >
            <Tooltip title="删除">
              <Button
                type="text"
                danger
                icon={<DeleteOutlined />}
                loading={isLoading}
              />
            </Tooltip>
          </Popconfirm>
        </Space>
      ),
    },
  ];

  return (
    <Table
      columns={columns}
      dataSource={documents}
      rowKey="id"
      pagination={{
        current: pagination.page,
        total: pagination.total,
        pageSize: pagination.limit,
        showSizeChanger: true,
        showQuickJumper: true,
        showTotal: (total, range) => 
          `第 ${range[0]}-${range[1]} 条，共 ${total} 条`,
        onChange: onPageChange,
        onShowSizeChange: onPageChange,
      }}
      locale={{
        emptyText: '暂无文档数据'
      }}
    />
  );
};

export default DocumentList;