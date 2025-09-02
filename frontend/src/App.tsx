import { useEffect } from 'react';
import { RouterProvider } from 'react-router-dom';
import { ConfigProvider } from 'antd';
import zhCN from 'antd/locale/zh_CN';
import { router } from './router';
import { authService } from './services/authService';

function App() {
  useEffect(() => {
    // Initialize auth service on app startup
    authService.initialize();
  }, []);

  return (
    <ConfigProvider locale={zhCN}>
      <RouterProvider router={router} />
    </ConfigProvider>
  );
}

export default App;