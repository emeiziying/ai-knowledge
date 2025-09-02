import React, { useEffect, useState } from 'react';
import { 
  Typography, 
  Row, 
  Col, 
  Card, 
  Input, 
  Button, 
  Space, 
  message,
  Modal,
  Spin
} from 'antd';
import { 
  UploadOutlined, 
  SearchOutlined, 
  ReloadOutlined,
  FilterOutlined 
} from '@ant-design/icons';
import { useDocumentStore } from '../../stores/documentStore';
import DocumentList from '../../components/Documents/DocumentList';
import FileUpload from '../../components/Documents/FileUpload';
import DocumentDetails from '../../components/Documents/DocumentDetails';
import DocumentFilters from '../../components/Documents/DocumentFilters';

const { Title } = Typography;
const { Search } = Input;

const Documents: React.FC = () => {
  const {
    documents,
    currentDocument,
    isLoading,
    error,
    pagination,
    searchQuery,
    fetchDocuments,
    searchDocuments,
    setSearchQuery,
    clearError,
    clearCurrentDocument
  } = useDocumentStore();

  const [uploadModalVisible, setUploadModalVisible] = useState(false);
  const [detailsModalVisible, setDetailsModalVisible] = useState(false);
  const [filtersVisible, setFiltersVisible] = useState(false);
  const [filters, setFilters] = useState({
    status: '',
    fileType: '',
    dateRange: null as [string, string] | null
  });

  useEffect(() => {
    fetchDocuments();
  }, []);

  useEffect(() => {
    if (error) {
      message.error(error);
      clearError();
    }
  }, [error, clearError]);

  const handleSearch = (value: string) => {
    setSearchQuery(value);
    if (value.trim()) {
      searchDocuments(value);
    } else {
      fetchDocuments();
    }
  };

  const handleRefresh = () => {
    if (searchQuery) {
      searchDocuments(searchQuery);
    } else {
      fetchDocuments();
    }
  };

  const handleUploadSuccess = () => {
    setUploadModalVisible(false);
    message.success('文档上传成功');
    handleRefresh();
  };

  const handleViewDetails = (documentId: string) => {
    const document = documents.find(doc => doc.id === documentId);
    if (document) {
      useDocumentStore.getState().currentDocument = document;
      setDetailsModalVisible(true);
    }
  };

  const handleCloseDetails = () => {
    setDetailsModalVisible(false);
    clearCurrentDocument();
  };

  const handlePageChange = (page: number, pageSize?: number) => {
    fetchDocuments(page, pageSize || pagination.limit, searchQuery);
  };

  const handleApplyFilters = (newFilters: typeof filters) => {
    setFilters(newFilters);
    // Apply filters to the document list
    // This would typically involve updating the API call with filter parameters
    fetchDocuments(1, pagination.limit, searchQuery);
  };

  return (
    <div style={{ padding: '24px' }}>
      <Row gutter={[16, 16]}>
        <Col span={24}>
          <Card>
            <Row justify="space-between" align="middle" style={{ marginBottom: 16 }}>
              <Col>
                <Title level={2} style={{ margin: 0 }}>文档管理</Title>
              </Col>
              <Col>
                <Space>
                  <Button 
                    type="primary" 
                    icon={<UploadOutlined />}
                    onClick={() => setUploadModalVisible(true)}
                  >
                    上传文档
                  </Button>
                  <Button 
                    icon={<ReloadOutlined />}
                    onClick={handleRefresh}
                    loading={isLoading}
                  >
                    刷新
                  </Button>
                </Space>
              </Col>
            </Row>

            <Row gutter={[16, 16]} style={{ marginBottom: 16 }}>
              <Col xs={24} sm={16} md={18}>
                <Search
                  placeholder="搜索文档名称或内容..."
                  allowClear
                  enterButton={<SearchOutlined />}
                  size="large"
                  onSearch={handleSearch}
                  defaultValue={searchQuery}
                />
              </Col>
              <Col xs={24} sm={8} md={6}>
                <Button
                  icon={<FilterOutlined />}
                  onClick={() => setFiltersVisible(!filtersVisible)}
                  style={{ width: '100%', height: '40px' }}
                >
                  筛选
                </Button>
              </Col>
            </Row>

            {filtersVisible && (
              <Row style={{ marginBottom: 16 }}>
                <Col span={24}>
                  <DocumentFilters
                    filters={filters}
                    onApplyFilters={handleApplyFilters}
                  />
                </Col>
              </Row>
            )}

            <Spin spinning={isLoading}>
              <DocumentList
                documents={documents}
                pagination={pagination}
                onPageChange={handlePageChange}
                onViewDetails={handleViewDetails}
                onRefresh={handleRefresh}
              />
            </Spin>
          </Card>
        </Col>
      </Row>

      {/* Upload Modal */}
      <Modal
        title="上传文档"
        open={uploadModalVisible}
        onCancel={() => setUploadModalVisible(false)}
        footer={null}
        width={600}
      >
        <FileUpload onUploadSuccess={handleUploadSuccess} />
      </Modal>

      {/* Document Details Modal */}
      <Modal
        title="文档详情"
        open={detailsModalVisible}
        onCancel={handleCloseDetails}
        footer={null}
        width={800}
      >
        {currentDocument && (
          <DocumentDetails
            document={currentDocument}
            onClose={handleCloseDetails}
            onRefresh={handleRefresh}
          />
        )}
      </Modal>
    </div>
  );
};

export default Documents;