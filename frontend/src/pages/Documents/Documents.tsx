import React from 'react';
import { Typography } from 'antd';

const { Title } = Typography;

const Documents: React.FC = () => {
  return (
    <div>
      <Title level={2}>文档管理</Title>
      <p>文档管理功能将在后续任务中实现</p>
    </div>
  );
};

export default Documents;