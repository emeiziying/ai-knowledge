import React from 'react';
import { ConfigProvider } from 'antd';
import zhCN from 'antd/locale/zh_CN';

function App() {
  return (
    <ConfigProvider locale={zhCN}>
      <div className="App">
        <h1>AI Knowledge Base</h1>
        <p>Welcome to AI Knowledge Base Application</p>
      </div>
    </ConfigProvider>
  );
}

export default App;