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
  message
} from 'antd';
import {
  InboxOutlined,
  DeleteOutlined,
  CheckCircleOutlined,
  ExclamationCircleOutlined
} from '@ant-design/icons';
import { useDocumentStore } from '../../stores/documentStore';
import { formatFileSize } from '../../utils';

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
            ? { ...f, status: 'uploading' as const }
            : f
        )
      );

      await uploadDocument(uploadFile.file);

      // Update file status to done
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
      case 'done':
        return <CheckCircleOutlined style={{ color: '#52c41a' }} />;
      case 'error':
        return <ExclamationCircleOutlined style={{ color: '#ff4d4f' }} />;
      default:
        return null;
    }
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
    <div>
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
              className={dragOver ? 'drag-over' : ''}
              style={{
                backgroundColor: dragOver ? '#f0f9ff' : undefined,
                borderColor: dragOver ? '#1890ff' : undefined,
              }}
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
          <Card title="上传列表">
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
                    />
                  ]}
                >
                  <List.Item.Meta
                    avatar={getStatusIcon(item.status)}
                    title={
                      <Space>
                        <Text>{item.name}</Text>
                        <Text type="secondary">({formatFileSize(item.size)})</Text>
                      </Space>
                    }
                    description={
                      <div>
                        {item.status === 'uploading' && (
                          <Progress
                            percent={item.progress}
                            size="small"
                            status="active"
                          />
                        )}
                        {item.status === 'error' && (
                          <Text type="danger">{item.error}</Text>
                        )}
                        {item.status === 'done' && (
                          <Text type="success">上传完成</Text>
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