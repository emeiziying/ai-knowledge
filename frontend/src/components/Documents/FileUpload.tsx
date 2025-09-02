import React, { useState } from 'react';
import {
  Upload,
  Button,
  Progress,
  Alert,
  Space,
  Typography,
  List,
  Card,
  message,
  Spin,
  Badge
} from 'antd';
import {
  InboxOutlined,
  DeleteOutlined,
  CheckCircleOutlined,
  ExclamationCircleOutlined,
  LoadingOutlined,
  FileTextOutlined
} from '@ant-design/icons';
import { useDocumentStore } from '../../stores/documentStore';
import { formatFileSize } from '../../utils';
import './FileUpload.css';

const { Dragger } = Upload;
const { Text, Title } = Typography;

interface FileUploadProps {
  onUploadSuccess?: () => void;
}

interface UploadFile {
  uid: string;
  name: string;
  size: number;
  status: 'uploading' | 'done' | 'error' | 'removed';
  progress: number;
  file: File;
  error?: string | undefined;
}

const FileUpload: React.FC<FileUploadProps> = ({ onUploadSuccess }) => {
  const { uploadDocument } = useDocumentStore();
  const [fileList, setFileList] = useState<UploadFile[]>([]);
  const [dragOver, setDragOver] = useState(false);

  // Supported file types
  const supportedTypes = [
    'application/pdf',
    'application/msword',
    'application/vnd.openxmlformats-officedocument.wordprocessingml.document',
    'text/plain',
    'text/markdown',
    'application/rtf'
  ];

  const maxFileSize = 50 * 1024 * 1024; // 50MB

  const validateFile = (file: File): string | null => {
    if (!supportedTypes.includes(file.type)) {
      return '不支持的文件格式。支持的格式：PDF、Word、TXT、Markdown';
    }
    if (file.size > maxFileSize) {
      return `文件大小不能超过 ${formatFileSize(maxFileSize)}`;
    }
    return null;
  };

  const handleFileSelect = (files: FileList | File[]) => {
    const newFiles: UploadFile[] = [];
    
    Array.from(files).forEach((file) => {
      const error = validateFile(file);
      
      const uploadFile: UploadFile = {
        uid: `${Date.now()}-${Math.random()}`,
        name: file.name,
        size: file.size,
        status: error ? 'error' : 'uploading',
        progress: 0,
        file,
        error: error || undefined
      };
      
      newFiles.push(uploadFile);
    });

    setFileList(prev => [...prev, ...newFiles]);

    // Start uploading valid files
    newFiles.forEach(uploadFile => {
      if (!uploadFile.error) {
        handleUpload(uploadFile);
      }
    });
  };

  const handleUpload = async (uploadFile: UploadFile) => {
    try {
      // Update file status to uploading
      setFileList(prev => 
        prev.map(f => 
          f.uid === uploadFile.uid 
            ? { ...f, status: 'uploading' as const, progress: 0 }
            : f
        )
      );

      // Simulate progress updates during upload
      const progressInterval = setInterval(() => {
        setFileList(prev => 
          prev.map(f => 
            f.uid === uploadFile.uid && f.status === 'uploading'
              ? { ...f, progress: Math.min(f.progress + Math.random() * 20, 90) }
              : f
          )
        );
      }, 200);

      await uploadDocument(uploadFile.file);

      // Clear progress interval and set to complete
      clearInterval(progressInterval);
      setFileList(prev => 
        prev.map(f => 
          f.uid === uploadFile.uid 
            ? { ...f, status: 'done' as const, progress: 100 }
            : f
        )
      );

      message.success(`文件 "${uploadFile.name}" 上传成功`);
      
      if (onUploadSuccess) {
        onUploadSuccess();
      }
    } catch (error: any) {
      // Update file status to error
      setFileList(prev => 
        prev.map(f => 
          f.uid === uploadFile.uid 
            ? { 
                ...f, 
                status: 'error' as const, 
                error: error.message || '上传失败'
              }
            : f
        )
      );
      
      message.error(`文件 "${uploadFile.name}" 上传失败`);
    }
  };

  const handleRemoveFile = (uid: string) => {
    setFileList(prev => prev.filter(f => f.uid !== uid));
  };

  const handleDrop = (e: React.DragEvent) => {
    e.preventDefault();
    setDragOver(false);
    
    const files = e.dataTransfer.files;
    if (files.length > 0) {
      handleFileSelect(files);
    }
  };

  const handleDragOver = (e: React.DragEvent) => {
    e.preventDefault();
    setDragOver(true);
  };

  const handleDragLeave = (e: React.DragEvent) => {
    e.preventDefault();
    setDragOver(false);
  };

  const getStatusIcon = (status: UploadFile['status']) => {
    switch (status) {
      case 'uploading':
        return <Spin indicator={<LoadingOutlined style={{ fontSize: 16, color: '#1890ff' }} spin />} />;
      case 'done':
        return <CheckCircleOutlined style={{ color: '#52c41a', fontSize: 16 }} />;
      case 'error':
        return <ExclamationCircleOutlined style={{ color: '#ff4d4f', fontSize: 16 }} />;
      default:
        return <FileTextOutlined style={{ color: '#8c8c8c', fontSize: 16 }} />;
    }
  };

  const getUploadingCount = () => {
    return fileList.filter(f => f.status === 'uploading').length;
  };

  const getCompletedCount = () => {
    return fileList.filter(f => f.status === 'done').length;
  };

  const getErrorCount = () => {
    return fileList.filter(f => f.status === 'error').length;
  };

  const uploadProps = {
    name: 'file',
    multiple: true,
    showUploadList: false,
    beforeUpload: (file: File) => {
      handleFileSelect([file]);
      return false; // Prevent default upload
    },
  };

  return (
    <div className="file-upload-container">
      <Space direction="vertical" style={{ width: '100%' }} size="large">
        {/* Upload Area */}
        <Card>
          <div
            onDrop={handleDrop}
            onDragOver={handleDragOver}
            onDragLeave={handleDragLeave}
          >
            <Dragger
              {...uploadProps}
              className={`upload-dragger ${dragOver ? 'drag-over' : ''}`}
            >
            <p className="ant-upload-drag-icon">
              <InboxOutlined style={{ fontSize: '48px', color: '#1890ff' }} />
            </p>
            <p className="ant-upload-text">
              <Title level={4}>点击或拖拽文件到此区域上传</Title>
            </p>
            <p className="ant-upload-hint">
              支持单个或批量上传。支持的格式：PDF、Word、TXT、Markdown
              <br />
              最大文件大小：{formatFileSize(maxFileSize)}
            </p>
          </Dragger>
          </div>
        </Card>

        {/* File List */}
        {fileList.length > 0 && (
          <Card 
            className="file-list-card"
            title={
              <Space>
                <span>上传列表</span>
                {getUploadingCount() > 0 && (
                  <Badge count={getUploadingCount()} style={{ backgroundColor: '#1890ff' }}>
                    <span className="status-badge uploading">上传中</span>
                  </Badge>
                )}
                {getCompletedCount() > 0 && (
                  <Badge count={getCompletedCount()} style={{ backgroundColor: '#52c41a' }}>
                    <span className="status-badge completed">已完成</span>
                  </Badge>
                )}
                {getErrorCount() > 0 && (
                  <Badge count={getErrorCount()} style={{ backgroundColor: '#ff4d4f' }}>
                    <span className="status-badge error">失败</span>
                  </Badge>
                )}
              </Space>
            }
          >
            <List
              dataSource={fileList}
              renderItem={(item) => (
                <List.Item
                  actions={[
                    <Button
                      type="text"
                      danger
                      icon={<DeleteOutlined />}
                      onClick={() => handleRemoveFile(item.uid)}
                      disabled={item.status === 'uploading'}
                      size="small"
                    />
                  ]}
                  className={`file-item ${
                    item.status === 'uploading' ? 'uploading' :
                    item.status === 'error' ? 'error' :
                    item.status === 'done' ? 'completed' : ''
                  }`}
                >
                  <List.Item.Meta
                    avatar={getStatusIcon(item.status)}
                    title={
                      <Space>
                        <Text strong={item.status === 'uploading'}>{item.name}</Text>
                        <Text type="secondary">({formatFileSize(item.size)})</Text>
                      </Space>
                    }
                    description={
                      <div>
                        {item.status === 'uploading' && (
                          <div className="upload-progress">
                            <Progress
                              percent={Math.round(item.progress)}
                              size="small"
                              status="active"
                              strokeColor="#52c41a"
                              showInfo={true}
                            />
                            <div className="progress-description">
                              正在上传和处理文档...
                            </div>
                          </div>
                        )}
                        {item.status === 'error' && (
                          <Text type="danger">{item.error}</Text>
                        )}
                        {item.status === 'done' && (
                          <Text type="success">✓ 上传完成，文档已建立索引</Text>
                        )}
                      </div>
                    }
                  />
                </List.Item>
              )}
            />
          </Card>
        )}

        {/* Upload Instructions */}
        <Alert
          message="上传说明"
          description={
            <ul style={{ margin: 0, paddingLeft: '20px' }}>
              <li>支持的文件格式：PDF、Word (.doc/.docx)、纯文本 (.txt)、Markdown (.md)</li>
              <li>单个文件最大 {formatFileSize(maxFileSize)}</li>
              <li>上传后系统会自动解析文档内容并建立索引</li>
              <li>处理完成后即可在对话中引用文档内容</li>
            </ul>
          }
          type="info"
          showIcon
        />
      </Space>


    </div>
  );
};

export default FileUpload;