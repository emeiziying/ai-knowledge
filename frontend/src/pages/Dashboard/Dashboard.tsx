import React from 'react';
import { Card, Row, Col, Statistic, Typography } from 'antd';
import { 
  FileTextOutlined, 
  MessageOutlined, 
  ClockCircleOutlined,
  CheckCircleOutlined 
} from '@ant-design/icons';

const { Title } = Typography;

const Dashboard: React.FC = () => {
  return (
    <div>
      <Title level={2}>仪表板</Title>
      
      <Row gutter={[16, 16]} style={{ marginBottom: '24px' }}>
        <Col xs={24} sm={12} lg={6}>
          <Card>
            <Statistic
              title="文档总数"
              value={0}
              prefix={<FileTextOutlined />}
              valueStyle={{ color: '#3f8600' }}
            />
          </Card>
        </Col>
        
        <Col xs={24} sm={12} lg={6}>
          <Card>
            <Statistic
              title="对话次数"
              value={0}
              prefix={<MessageOutlined />}
              valueStyle={{ color: '#1890ff' }}
            />
          </Card>
        </Col>
        
        <Col xs={24} sm={12} lg={6}>
          <Card>
            <Statistic
              title="处理中"
              value={0}
              prefix={<ClockCircleOutlined />}
              valueStyle={{ color: '#faad14' }}
            />
          </Card>
        </Col>
        
        <Col xs={24} sm={12} lg={6}>
          <Card>
            <Statistic
              title="已完成"
              value={0}
              prefix={<CheckCircleOutlined />}
              valueStyle={{ color: '#52c41a' }}
            />
          </Card>
        </Col>
      </Row>

      <Row gutter={[16, 16]}>
        <Col xs={24} lg={12}>
          <Card title="最近上传的文档" size="small">
            <p>暂无文档</p>
          </Card>
        </Col>
        
        <Col xs={24} lg={12}>
          <Card title="最近的对话" size="small">
            <p>暂无对话记录</p>
          </Card>
        </Col>
      </Row>
    </div>
  );
};

export default Dashboard;