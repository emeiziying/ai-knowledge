import React, { useState, useEffect } from 'react';
import { Layout, Menu, Avatar, Dropdown, Space, Typography, message, Button, Drawer } from 'antd';
import { 
  FileTextOutlined, 
  MessageOutlined, 
  SettingOutlined, 
  UserOutlined,
  LogoutOutlined,
  DashboardOutlined,
  MenuOutlined
} from '@ant-design/icons';
import { useNavigate, useLocation } from 'react-router-dom';
import { useAuth } from '../../hooks/useAuth';
import './MainLayout.css';

const { Header, Sider, Content } = Layout;
const { Title } = Typography;

interface MainLayoutProps {
  children: React.ReactNode;
}

const MainLayout: React.FC<MainLayoutProps> = ({ children }) => {
  const navigate = useNavigate();
  const location = useLocation();
  const { user, logout } = useAuth();
  const [isMobile, setIsMobile] = useState(window.innerWidth < 768);
  const [drawerVisible, setDrawerVisible] = useState(false);

  useEffect(() => {
    const handleResize = () => {
      setIsMobile(window.innerWidth < 768);
      if (window.innerWidth >= 768) {
        setDrawerVisible(false);
      }
    };

    window.addEventListener('resize', handleResize);
    return () => window.removeEventListener('resize', handleResize);
  }, []);

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
    if (isMobile) {
      setDrawerVisible(false);
    }
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
    <Layout className="main-layout">
      {/* Desktop Sidebar */}
      {!isMobile && (
        <Sider
          theme="light"
          width={250}
          style={{
            boxShadow: '2px 0 8px rgba(0,0,0,0.1)',
          }}
        >
          <div className="sidebar-content">
            <div className="sidebar-header">
              <Title className="sidebar-title" level={4}>
                AI 知识库
              </Title>
            </div>
            <Menu
              className="sidebar-menu"
              mode="inline"
              selectedKeys={[location.pathname]}
              items={menuItems}
              onClick={handleMenuClick}
            />
          </div>
        </Sider>
      )}

      {/* Mobile Drawer */}
      {isMobile && (
        <Drawer
          className="mobile-drawer"
          title={null}
          placement="left"
          onClose={() => setDrawerVisible(false)}
          open={drawerVisible}
          bodyStyle={{ padding: 0 }}
          width={250}
        >
          <div className="sidebar-content">
            <div className="sidebar-header">
              <Title className="sidebar-title" level={4}>
                AI 知识库
              </Title>
            </div>
            <Menu
              className="sidebar-menu"
              mode="inline"
              selectedKeys={[location.pathname]}
              items={menuItems}
              onClick={handleMenuClick}
            />
          </div>
        </Drawer>
      )}
      
      <Layout>
        <Header className={`main-header ${isMobile ? 'mobile' : 'desktop'}`}>
          {/* Mobile menu button */}
          {isMobile && (
            <Button
              className="mobile-menu-btn"
              type="text"
              icon={<MenuOutlined />}
              onClick={() => setDrawerVisible(true)}
            />
          )}

          {/* Mobile title */}
          {isMobile && (
            <Title className="mobile-title" level={5}>
              AI 知识库
            </Title>
          )}

          {/* User menu */}
          <Dropdown
            menu={{
              items: userMenuItems,
              onClick: handleUserMenuClick,
            }}
            placement="bottomRight"
          >
            <div className="user-dropdown">
              <Space>
                <Avatar icon={<UserOutlined />} size={isMobile ? 'small' : 'default'} />
                {!isMobile && <span>{user?.username || '用户'}</span>}
              </Space>
            </div>
          </Dropdown>
        </Header>
        
        <Content className={`main-content ${isMobile ? 'mobile' : 'desktop'}`}>
          {children}
        </Content>
      </Layout>
    </Layout>
  );
};

export default MainLayout;