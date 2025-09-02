import React from 'react';
import { Typography } from 'antd';

const { Title } = Typography;

const Settings: React.FC = () => {
  return (
    <div>
      <Title level={2}>系统设置</Title>
      <p>系统设置功能将在后续任务中实现</p>
    </div>
  );
};

export default Settings;