import React from 'react';
import { Spin, Typography } from 'antd';
import { LoadingOutlined } from '@ant-design/icons';

const { Text } = Typography;

interface LoadingSpinnerProps {
  size?: 'small' | 'default' | 'large';
  tip?: string;
  spinning?: boolean;
  children?: React.ReactNode;
  style?: React.CSSProperties;
  className?: string;
}

const LoadingSpinner: React.FC<LoadingSpinnerProps> = ({
  size = 'default',
  tip,
  spinning = true,
  children,
  style,
  className
}) => {
  const antIcon = <LoadingOutlined style={{ fontSize: size === 'large' ? 24 : size === 'small' ? 14 : 18 }} spin />;

  if (children) {
    return (
      <Spin 
        spinning={spinning} 
        indicator={antIcon} 
        tip={tip}
        size={size}
        style={style}
        className={className}
      >
        {children}
      </Spin>
    );
  }

  return (
    <div 
      style={{
        display: 'flex',
        flexDirection: 'column',
        alignItems: 'center',
        justifyContent: 'center',
        padding: '40px 20px',
        ...style
      }}
      className={className}
    >
      <Spin 
        indicator={antIcon} 
        size={size}
      />
      {tip && (
        <Text 
          type="secondary" 
          style={{ 
            marginTop: '12px', 
            fontSize: size === 'large' ? '16px' : size === 'small' ? '12px' : '14px'
          }}
        >
          {tip}
        </Text>
      )}
    </div>
  );
};

export default LoadingSpinner;