import React, { useState } from "react";
import {
  Form,
  Input,
  Button,
  Card,
  Typography,
  Alert,
  Space,
  Divider,
} from "antd";
import { UserOutlined, LockOutlined } from "@ant-design/icons";
import { Link, useNavigate, useLocation } from "react-router-dom";
import { useAuth } from "../../hooks/useAuth";

const { Title, Text } = Typography;

interface LoginFormData {
  username: string;
  password: string;
}

const Login: React.FC = () => {
  const [form] = Form.useForm();
  const navigate = useNavigate();
  const location = useLocation();
  const { login, isLoading, error, clearError } = useAuth();
  const [loginError, setLoginError] = useState<string | null>(null);

  // Get the intended destination from location state, default to dashboard
  const from = (location.state as any)?.from?.pathname || "/";

  const handleSubmit = async (values: LoginFormData) => {
    try {
      setLoginError(null);
      clearError();

      await login(values.username, values.password);

      // Redirect to intended destination or dashboard
      navigate(from, { replace: true });
    } catch (err: any) {
      setLoginError(err.message || "登录失败，请检查用户名和密码");
    }
  };

  const displayError = loginError || error;

  return (
    <div
      style={{
        minHeight: "100vh",
        display: "flex",
        alignItems: "center",
        justifyContent: "center",
        background: "linear-gradient(135deg, #667eea 0%, #764ba2 100%)",
        padding: "20px",
      }}
    >
      <Card
        style={{
          width: "100%",
          maxWidth: 400,
          boxShadow: "0 8px 32px rgba(0, 0, 0, 0.1)",
          borderRadius: "12px",
        }}
        styles={{ body: { padding: "40px" } }}
      >
        <div style={{ textAlign: "center", marginBottom: "32px" }}>
          <Title level={2} style={{ color: "#1890ff", marginBottom: "8px" }}>
            AI 知识库
          </Title>
          <Text type="secondary">登录到您的账户</Text>
        </div>

        {displayError && (
          <Alert
            message={displayError}
            type="error"
            showIcon
            closable
            onClose={() => {
              setLoginError(null);
              clearError();
            }}
            style={{ marginBottom: "24px" }}
          />
        )}

        <Form
          form={form}
          name="login"
          onFinish={handleSubmit}
          layout="vertical"
          size="large"
        >
          <Form.Item
            name="username"
            label="用户名"
            rules={[
              { required: true, message: "请输入用户名" },
              { min: 3, message: "用户名至少3个字符" },
            ]}
          >
            <Input
              prefix={<UserOutlined />}
              placeholder="请输入用户名"
              autoComplete="username"
            />
          </Form.Item>

          <Form.Item
            name="password"
            label="密码"
            rules={[
              { required: true, message: "请输入密码" },
              { min: 6, message: "密码至少6个字符" },
            ]}
          >
            <Input.Password
              prefix={<LockOutlined />}
              placeholder="请输入密码"
              autoComplete="current-password"
            />
          </Form.Item>

          <Form.Item style={{ marginBottom: "16px" }}>
            <Button
              type="primary"
              htmlType="submit"
              loading={isLoading}
              block
              style={{ height: "44px", fontSize: "16px" }}
            >
              {isLoading ? "登录中..." : "登录"}
            </Button>
          </Form.Item>
        </Form>

        <Divider>
          <Text type="secondary">还没有账户？</Text>
        </Divider>

        <div style={{ textAlign: "center" }}>
          <Space>
            <Text type="secondary">没有账户？</Text>
            <Link to="/auth/register">
              <Button type="link" style={{ padding: 0 }}>
                立即注册
              </Button>
            </Link>
          </Space>
        </div>
      </Card>
    </div>
  );
};

export default Login;
