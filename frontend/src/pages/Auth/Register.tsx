import React, { useState } from 'react';
import { Form, Input, Button, Card, Typography, Alert, Space, Divider } from 'antd';
import { UserOutlined, LockOutlined, MailOutlined } from '@ant-design/icons';
import { Link, useNavigate } from 'react-router-dom';
import { useAuth } from '../../hooks/useAuth';

const { Title, Text } = Typography;

interface RegisterFormData {
  username: string;
  email: string;
  password: string;
  confirmPassword: string;
}

const Register: React.FC = () => {
  const [form] = Form.useForm();
  const navigate = useNavigate();
  const { register, isLoading, error, clearError } = useAuth();
  const [registerError, setRegisterError] = useState<string | null>(null);

  const handleSubmit = async (values: RegisterFormData) => {
    try {
      setRegisterError(null);
      clearError();
      
      await register(values.username, values.email, values.password);
      
      // Redirect to dashboard after successful registration
      navigate('/', { replace: true });
    } catch (err: any) {
      setRegisterError(err.message || '注册失败，请稍后重试');
    }
  };

  const displayError = registerError || error;

  return (
    <div style={{
      minHeight: '100vh',
      display: 'flex',
      alignItems: 'center',
      justifyContent: 'center',
      background: 'linear-gradient(135deg, #667eea 0%, #764ba2 100%)',
      padding: '20px'
    }}>
      <Card
        style={{
          width: '100%',
          maxWidth: 400,
          boxShadow: '0 8px 32px rgba(0, 0, 0, 0.1)',
          borderRadius: '12px'
        }}
        bodyStyle={{ padding: '40px' }}
      >
        <div style={{ textAlign: 'center', marginBottom: '32px' }}>
          <Title level={2} style={{ color: '#1890ff', marginBottom: '8px' }}>
            AI 知识库
          </Title>
          <Text type="secondary">创建您的账户</Text>
        </div>

        {displayError && (
          <Alert
            message={displayError}
            type="error"
            showIcon
            closable
            onClose={() => {
              setRegisterError(null);
              clearError();
            }}
            style={{ marginBottom: '24px' }}
          />
        )}

        <Form
          form={form}
          name="register"
          onFinish={handleSubmit}
          layout="vertical"
          size="large"
        >
          <Form.Item
            name="username"
            label="用户名"
            rules={[
              { required: true, message: '请输入用户名' },
              { min: 3, message: '用户名至少3个字符' },
              { max: 20, message: '用户名最多20个字符' },
              { pattern: /^[a-zA-Z0-9_]+$/, message: '用户名只能包含字母、数字和下划线' }
            ]}
          >
            <Input
              prefix={<UserOutlined />}
              placeholder="请输入用户名"
              autoComplete="username"
            />
          </Form.Item>

          <Form.Item
            name="email"
            label="邮箱"
            rules={[
              { required: true, message: '请输入邮箱地址' },
              { type: 'email', message: '请输入有效的邮箱地址' }
            ]}
          >
            <Input
              prefix={<MailOutlined />}
              placeholder="请输入邮箱地址"
              autoComplete="email"
            />
          </Form.Item>

          <Form.Item
            name="password"
            label="密码"
            rules={[
              { required: true, message: '请输入密码' },
              { min: 6, message: '密码至少6个字符' },
              { max: 50, message: '密码最多50个字符' }
            ]}
          >
            <Input.Password
              prefix={<LockOutlined />}
              placeholder="请输入密码"
              autoComplete="new-password"
            />
          </Form.Item>

          <Form.Item
            name="confirmPassword"
            label="确认密码"
            dependencies={['password']}
            rules={[
              { required: true, message: '请确认密码' },
              ({ getFieldValue }) => ({
                validator(_, value) {
                  if (!value || getFieldValue('password') === value) {
                    return Promise.resolve();
                  }
                  return Promise.reject(new Error('两次输入的密码不一致'));
                },
              }),
            ]}
          >
            <Input.Password
              prefix={<LockOutlined />}
              placeholder="请再次输入密码"
              autoComplete="new-password"
            />
          </Form.Item>

          <Form.Item style={{ marginBottom: '16px' }}>
            <Button
              type="primary"
              htmlType="submit"
              loading={isLoading}
              block
              style={{ height: '44px', fontSize: '16px' }}
            >
              {isLoading ? '注册中...' : '注册'}
            </Button>
          </Form.Item>
        </Form>

        <Divider>
          <Text type="secondary">已有账户？</Text>
        </Divider>

        <div style={{ textAlign: 'center' }}>
          <Space>
            <Text type="secondary">已有账户？</Text>
            <Link to="/auth/login">
              <Button type="link" style={{ padding: 0 }}>
                立即登录
              </Button>
            </Link>
          </Space>
        </div>
      </Card>
    </div>
  );
};

export default Register;