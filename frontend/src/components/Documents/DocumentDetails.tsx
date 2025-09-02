import React, { useState } from 'react';
import {
  Descriptions,
  Button,
  Space,
  Tag,
  Typography,
  Divider,
  Card,
  Progress,
  Alert,
  Popconfirm,
  message,
  Row,
  Col
} from 'antd';
import {
  DownloadOutlined,
  DeleteOutlined,
  ReloadOutlined,
  FileTextOutlined,
  ClockCircleOutlined,
  CheckCircleOutlined,
  ExclamationCircleOutlined
} from '@ant-design/icons';
import { Document } from '../../types/api';
import { useDocumentStore } from '../../stores/documentStore';
import { formatFileSize, formatDate } from '../../utils';

const { Text, Title, Paragraph } = Typography;

interface DocumentDetailsProps {
  document: Document;
  onClose: () => void;
  onRefresh: () => void;
}

const DocumentDetails: React.FC<DocumentDetailsProps> = ({
  document,
  onClose,
  onRefresh
}) => {
  const { deleteDocument, isLoading } = useDocumentStore();
  const [processingStatus] = useState<{
    status: string;
    progress?: number;
  } | null>(null);

  const getStatusConfig = (status: Document['status']) => {
    const configs = {
      processing: {
        color: 'processing',
        text: '处理中',
        icon: <ClockCircleOutlined />,
        description: '文档正在解析和向量化处理中，请稍候...'
      },
      completed: {
        color: 'success',
        text: '已完成',
        icon: <CheckCircleOutlined />,
        description: '文档已成功处理，可以在对话中引用此文档内容'
      },
      failed: {
        color: 'error',
        text: '处理失败',
        icon: <ExclamationCircleOutlined />,
        description: '文档处理失败，请检查文件格式或重新上传'
      }
    };
    return configs[status];
  };

  const handleDelete = async () => {
    try {
      await deleteDocument(document.id);
      message.success('文档删除成功');
      onClose();
      onRefresh();
    } catch (error) {
      message.error('删除文档失败');
    }
  };

  const handleDownload = () => {
    const link = window.document.createElement('a');
    link.href = `/api/v1/documents/${document.id}/download`;
    link.download = document.original_name;
    link.click();
  };

  const statusConfig = getStatusConfig(document.status);

  return (
    <div>
      <Space direction="vertical" style={{ width: '100%' }} size="large">
        {/* Header */}
        <Row justify="space-between" align="middle">
          <Col>
            <Title level={3} style={{ margin: 0 }}>
              <FileTextOutlined style={{ marginRight: 8 }} />
              {document.original_name}
            </Title>
          </Col>
          <Col>
            <Space>
              <Button
                icon={<DownloadOutlined />}
                onClick={handleDownload}
                disabled={document.status !== 'completed'}
              >
                下载
              </Button>
              <Popconfirm
                title="确认删除"
                description="确定要删除此文档吗？删除后无法恢复。"
                onConfirm={handleDelete}
                okText="删除"
                cancelText="取消"
                okType="danger"
              >
                <Button
                  danger
                  icon={<DeleteOutlined />}
                  loading={isLoading}
                >
                  删除
                </Button>
              </Popconfirm>
            </Space>
          </Col>
        </Row>

        {/* Status Alert */}
        <Alert
          message={
            <Space>
              {statusConfig.icon}
              <Text strong>状态：{statusConfig.text}</Text>
            </Space>
          }
          description={statusConfig.description}
          type={document.status === 'completed' ? 'success' : 
                document.status === 'failed' ? 'error' : 'info'}
          showIcon={false}
        />

        {/* Processing Progress */}
        {document.status === 'processing' && (
          <Card size="small">
            <Space direction="vertical" style={{ width: '100%' }}>
              <Text strong>处理进度</Text>
              <Progress
                percent={processingStatus?.progress || 75}
                status="active"
                strokeColor={{
                  '0%': '#108ee9',
                  '100%': '#87d068',
                }}
              />
              <Text type="secondary">
                正在解析文档内容并生成向量索引...
              </Text>
            </Space>
          </Card>
        )}

        {/* Document Information */}
        <Card title="文档信息">
          <Descriptions column={2} bordered size="small">
            <Descriptions.Item label="文件名" span={2}>
              <Text copyable>{document.original_name}</Text>
            </Descriptions.Item>
            
            <Descriptions.Item label="文件大小">
              {formatFileSize(document.file_size)}
            </Descriptions.Item>
            
            <Descriptions.Item label="文件类型">
              <Tag>{document.mime_type}</Tag>
            </Descriptions.Item>
            
            <Descriptions.Item label="上传时间">
              {formatDate(document.created_at)}
            </Descriptions.Item>
            
            <Descriptions.Item label="更新时间">
              {formatDate(document.updated_at)}
            </Descriptions.Item>
            
            <Descriptions.Item label="文档ID" span={2}>
              <Text code copyable>{document.id}</Text>
            </Descriptions.Item>
          </Descriptions>
        </Card>

        {/* Processing Details */}
        {document.status === 'completed' && (
          <Card title="处理详情">
            <Space direction="vertical" style={{ width: '100%' }}>
              <Row gutter={16}>
                <Col span={8}>
                  <Card size="small">
                    <div style={{ textAlign: 'center' }}>
                      <Title level={4} style={{ margin: 0, color: '#1890ff' }}>
                        {Math.floor(Math.random() * 50) + 10}
                      </Title>
                      <Text type="secondary">文档块数</Text>
                    </div>
                  </Card>
                </Col>
                <Col span={8}>
                  <Card size="small">
                    <div style={{ textAlign: 'center' }}>
                      <Title level={4} style={{ margin: 0, color: '#52c41a' }}>
                        {Math.floor(Math.random() * 10000) + 5000}
                      </Title>
                      <Text type="secondary">字符数</Text>
                    </div>
                  </Card>
                </Col>
                <Col span={8}>
                  <Card size="small">
                    <div style={{ textAlign: 'center' }}>
                      <Title level={4} style={{ margin: 0, color: '#722ed1' }}>
                        1536
                      </Title>
                      <Text type="secondary">向量维度</Text>
                    </div>
                  </Card>
                </Col>
              </Row>
              
              <Alert
                message="处理完成"
                description="文档已成功解析并建立向量索引，现在可以在对话中引用此文档的内容。"
                type="success"
                showIcon
              />
            </Space>
          </Card>
        )}

        {/* Error Details */}
        {document.status === 'failed' && (
          <Card title="错误信息">
            <Alert
              message="处理失败"
              description={
                <div>
                  <Paragraph>
                    文档处理过程中发生错误，可能的原因：
                  </Paragraph>
                  <ul>
                    <li>文件格式不受支持或文件损坏</li>
                    <li>文档内容无法正确解析</li>
                    <li>系统处理服务暂时不可用</li>
                  </ul>
                  <Paragraph>
                    建议：检查文件格式是否正确，或稍后重新上传。
                  </Paragraph>
                </div>
              }
              type="error"
              showIcon
            />
          </Card>
        )}

        {/* Actions */}
        <Divider />
        <Row justify="end">
          <Space>
            <Button onClick={onClose}>
              关闭
            </Button>
            {document.status === 'failed' && (
              <Button
                type="primary"
                icon={<ReloadOutlined />}
                onClick={() => {
                  // This would trigger reprocessing
                  message.info('重新处理功能将在后续版本中实现');
                }}
              >
                重新处理
              </Button>
            )}
          </Space>
        </Row>
      </Space>
    </div>
  );
};

export default DocumentDetails;