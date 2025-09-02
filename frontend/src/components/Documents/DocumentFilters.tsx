import React, { useState } from 'react';
import {
  Card,
  Row,
  Col,
  Select,
  DatePicker,
  Button,
  Space,
  Typography,
  Tag
} from 'antd';
import {
  FilterOutlined,
  ClearOutlined
} from '@ant-design/icons';
import dayjs from 'dayjs';

const { RangePicker } = DatePicker;
const { Text } = Typography;
const { Option } = Select;

interface DocumentFiltersProps {
  filters: {
    status: string;
    fileType: string;
    dateRange: [string, string] | null;
  };
  onApplyFilters: (filters: {
    status: string;
    fileType: string;
    dateRange: [string, string] | null;
  }) => void;
}

const DocumentFilters: React.FC<DocumentFiltersProps> = ({
  filters,
  onApplyFilters
}) => {
  const [localFilters, setLocalFilters] = useState(filters);

  const statusOptions = [
    { value: '', label: '全部状态' },
    { value: 'processing', label: '处理中' },
    { value: 'completed', label: '已完成' },
    { value: 'failed', label: '处理失败' }
  ];

  const fileTypeOptions = [
    { value: '', label: '全部类型' },
    { value: 'pdf', label: 'PDF' },
    { value: 'word', label: 'Word文档' },
    { value: 'text', label: '文本文件' },
    { value: 'markdown', label: 'Markdown' }
  ];

  const handleStatusChange = (value: string) => {
    setLocalFilters(prev => ({ ...prev, status: value }));
  };

  const handleFileTypeChange = (value: string) => {
    setLocalFilters(prev => ({ ...prev, fileType: value }));
  };

  const handleDateRangeChange = (_dates: any, dateStrings: [string, string]) => {
    setLocalFilters(prev => ({ 
      ...prev, 
      dateRange: dateStrings[0] && dateStrings[1] ? dateStrings : null 
    }));
  };

  const handleApply = () => {
    onApplyFilters(localFilters);
  };

  const handleClear = () => {
    const clearedFilters = {
      status: '',
      fileType: '',
      dateRange: null
    };
    setLocalFilters(clearedFilters);
    onApplyFilters(clearedFilters);
  };

  const hasActiveFilters = localFilters.status || localFilters.fileType || localFilters.dateRange;

  return (
    <Card size="small">
      <Row gutter={[16, 16]} align="middle">
        <Col xs={24} sm={6}>
          <div>
            <Text strong style={{ display: 'block', marginBottom: 4 }}>
              状态
            </Text>
            <Select
              style={{ width: '100%' }}
              value={localFilters.status}
              onChange={handleStatusChange}
              placeholder="选择状态"
            >
              {statusOptions.map(option => (
                <Option key={option.value} value={option.value}>
                  {option.label}
                </Option>
              ))}
            </Select>
          </div>
        </Col>

        <Col xs={24} sm={6}>
          <div>
            <Text strong style={{ display: 'block', marginBottom: 4 }}>
              文件类型
            </Text>
            <Select
              style={{ width: '100%' }}
              value={localFilters.fileType}
              onChange={handleFileTypeChange}
              placeholder="选择类型"
            >
              {fileTypeOptions.map(option => (
                <Option key={option.value} value={option.value}>
                  {option.label}
                </Option>
              ))}
            </Select>
          </div>
        </Col>

        <Col xs={24} sm={8}>
          <div>
            <Text strong style={{ display: 'block', marginBottom: 4 }}>
              上传时间
            </Text>
            <RangePicker
              style={{ width: '100%' }}
              value={localFilters.dateRange ? [
                dayjs(localFilters.dateRange[0]),
                dayjs(localFilters.dateRange[1])
              ] : null}
              onChange={handleDateRangeChange}
              placeholder={['开始日期', '结束日期']}
            />
          </div>
        </Col>

        <Col xs={24} sm={4}>
          <Space direction="vertical" style={{ width: '100%' }}>
            <Button
              type="primary"
              icon={<FilterOutlined />}
              onClick={handleApply}
              style={{ width: '100%' }}
            >
              应用
            </Button>
            <Button
              icon={<ClearOutlined />}
              onClick={handleClear}
              disabled={!hasActiveFilters}
              style={{ width: '100%' }}
            >
              清除
            </Button>
          </Space>
        </Col>
      </Row>

      {/* Active Filters Display */}
      {hasActiveFilters && (
        <Row style={{ marginTop: 12 }}>
          <Col span={24}>
            <Text type="secondary" style={{ marginRight: 8 }}>
              当前筛选：
            </Text>
            <Space wrap>
              {localFilters.status && (
                <Tag closable onClose={() => handleStatusChange('')}>
                  状态: {statusOptions.find(opt => opt.value === localFilters.status)?.label}
                </Tag>
              )}
              {localFilters.fileType && (
                <Tag closable onClose={() => handleFileTypeChange('')}>
                  类型: {fileTypeOptions.find(opt => opt.value === localFilters.fileType)?.label}
                </Tag>
              )}
              {localFilters.dateRange && (
                <Tag closable onClose={() => handleDateRangeChange(null, ['', ''])}>
                  时间: {localFilters.dateRange[0]} ~ {localFilters.dateRange[1]}
                </Tag>
              )}
            </Space>
          </Col>
        </Row>
      )}
    </Card>
  );
};

export default DocumentFilters;