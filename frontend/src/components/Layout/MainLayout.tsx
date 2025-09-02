import React from 'react';
import { Layout, Menu, Avatar, Dropdown, Space, Typography, message } from 'antd';
import { 
  FileTextOutlined, 
  MessageOutlined, 
  SettingOutlined, 
  UserOutlined,
  LogoutOutlined,
  DashboardOutlined
} from '@ant-design/icons';
import { useNavigate, useLocation } from 'react-router-dom';
import { useAuth } from '../../hooks/useAuth';

const { Header, Sider, Content } = Layout;
const { Title } = Typography;

interface MainLayoutProps {
  children: React.ReactNode;
}

const MainLayout: React.FC<MainLayoutProps> = ({ children }) => {
  const navigate = useNavigate();
  const location = useLocation();
  const { user, logout } = useAuth();

  const menuItems = [
    {
      key: '/',
      icon: <DashboardOutlined />,
      label: '仪表板',
    },
    {
      key: '/documents',
      icon: <FileTextOutlined />,
      label: '文档管理',
    },
    {
      key: '/chat',
      icon: <MessageOutlined />,
      label: '智能问答',
    },
    {
      key: '/settings',
      icon: <SettingOutlined />,
      label: '系统设置',
    },
  ];

  const userMenuItems = [
    {
      key: 'profile',
      icon: <UserOutlined />,
      label: '个人资料',
    },
    {
      key: 'logout',
      icon: <LogoutOutlined />,
      label: '退出登录',
      danger: true,
    },
  ];

  const handleMenuClick = ({ key }: { key: string }) => {
    navigate(key);
  };

  const handleUserMenuClick = async ({ key }: { key: string }) => {
    if (key === 'logout') {
      try {
        await logout();
        message.success('已成功退出登录');
        navigate('/auth/login', { replace: true });
      } catch (error) {
        message.error('退出登录失败');
      }
    } else if (key === 'profile') {
      // TODO: Navigate to profile page or show profile modal
      message.info('个人资料功能即将上线');
    }
  };

  return (
    <Layout style={{ minHeight: '100vh' }}>
      <Sider
        theme="light"
        width={250}
        style={{
          boxShadow: '2px 0 8px rgba(0,0,0,0.1)',
        }}
      >
        <div style={{ 
          padding: '16px', 
          borderBottom: '1px solid #f0f0f0',
          textAlign: 'center'
        }}>
          <Title level={4} style={{ margin: 0, color: '#1890ff' }}>
            AI 知识库
          </Title>
        </div>
        <Menu
          mode="inline"
          selectedKeys={[location.pathname]}
          items={menuItems}
          onClick={handleMenuClick}
          style={{ border: 'none', paddingTop: '16px' }}
        />
      </Sider>
      
      <Layout>
        <Header 
          style={{ 
            background: '#fff', 
            padding: '0 24px',
            boxShadow: '0 2px 8px rgba(0,0,0,0.1)',
            display: 'flex',
            justifyContent: 'flex-end',
            alignItems: 'center'
          }}
        >
          <Dropdown
            menu={{
              items: userMenuItems,
              onClick: handleUserMenuClick,
            }}
            placement="bottomRight"
          >
            <Space style={{ cursor: 'pointer' }}>
              <Avatar icon={<UserOutlined />} />
              <span>{user?.username || '用户'}</span>
            </Space>
          </Dropdown>
        </Header>
        
        <Content 
          style={{ 
            margin: '24px',
            padding: '24px',
            background: '#fff',
            borderRadius: '8px',
            boxShadow: '0 2px 8px rgba(0,0,0,0.1)'
          }}
        >
          {children}
        </Content>
      </Layout>
    </Layout>
  );
};

export default MainLayout;