import React, { useState } from 'react';
import {
  List,
  Button,
  Typography,
  Dropdown,
  Modal,
  Input,
  message,
  Empty,
  Spin,
} from 'antd';
import {
  PlusOutlined,
  MessageOutlined,
  MoreOutlined,
  EditOutlined,
  DeleteOutlined,
} from '@ant-design/icons';
import { Conversation } from '../../types/api';
import { useChatStore } from '../../stores/chatStore';
import './ConversationList.css';

const { Title, Text } = Typography;

interface ConversationListProps {
  conversations: Conversation[];
  currentConversation: Conversation | null;
  onNewConversation: () => void;
  onSelectConversation: (conversationId: string) => void;
}

const ConversationList: React.FC<ConversationListProps> = ({
  conversations,
  currentConversation,
  onNewConversation,
  onSelectConversation,
}) => {
  const { deleteConversation, updateConversationTitle, isLoading } = useChatStore();
  const [editingId, setEditingId] = useState<string | null>(null);
  const [editTitle, setEditTitle] = useState('');
  const [deleteModalVisible, setDeleteModalVisible] = useState(false);
  const [conversationToDelete, setConversationToDelete] = useState<string | null>(null);

  const handleEditTitle = (conversation: Conversation) => {
    setEditingId(conversation.id);
    setEditTitle(conversation.title);
  };

  const handleSaveTitle = async (conversationId: string) => {
    if (!editTitle.trim()) {
      message.error('对话标题不能为空');
      return;
    }

    try {
      await updateConversationTitle(conversationId, editTitle.trim());
      setEditingId(null);
      message.success('标题更新成功');
    } catch (error) {
      message.error('标题更新失败');
    }
  };

  const handleCancelEdit = () => {
    setEditingId(null);
    setEditTitle('');
  };

  const handleDeleteClick = (conversationId: string) => {
    setConversationToDelete(conversationId);
    setDeleteModalVisible(true);
  };

  const handleConfirmDelete = async () => {
    if (!conversationToDelete) return;

    try {
      await deleteConversation(conversationToDelete);
      setDeleteModalVisible(false);
      setConversationToDelete(null);
      message.success('对话删除成功');
    } catch (error) {
      message.error('对话删除失败');
    }
  };

  const formatDate = (dateString: string) => {
    const date = new Date(dateString);
    const now = new Date();
    const diffTime = now.getTime() - date.getTime();
    const diffDays = Math.floor(diffTime / (1000 * 60 * 60 * 24));

    if (diffDays === 0) {
      return date.toLocaleTimeString('zh-CN', { 
        hour: '2-digit', 
        minute: '2-digit' 
      });
    } else if (diffDays === 1) {
      return '昨天';
    } else if (diffDays < 7) {
      return `${diffDays}天前`;
    } else {
      return date.toLocaleDateString('zh-CN', { 
        month: 'short', 
        day: 'numeric' 
      });
    }
  };

  const getMenuItems = (conversation: Conversation) => [
    {
      key: 'edit',
      icon: <EditOutlined />,
      label: '编辑标题',
      onClick: () => handleEditTitle(conversation),
    },
    {
      key: 'delete',
      icon: <DeleteOutlined />,
      label: '删除对话',
      danger: true,
      onClick: () => handleDeleteClick(conversation.id),
    },
  ];

  return (
    <div className="conversation-list">
      <div className="conversation-header">
        <Title level={4} className="conversation-title">
          <MessageOutlined /> 对话列表
        </Title>
        <Button
          type="primary"
          icon={<PlusOutlined />}
          onClick={onNewConversation}
          className="new-conversation-btn"
        >
          新对话
        </Button>
      </div>

      <div className="conversation-content">
        {isLoading ? (
          <div className="loading-container">
            <Spin size="large" />
          </div>
        ) : conversations.length === 0 ? (
          <Empty
            image={Empty.PRESENTED_IMAGE_SIMPLE}
            description="暂无对话"
            className="empty-conversations"
          >
            <Button type="primary" onClick={onNewConversation}>
              开始新对话
            </Button>
          </Empty>
        ) : (
          <List
            className="conversations-list"
            dataSource={conversations}
            renderItem={(conversation) => (
              <List.Item
                className={`conversation-item ${
                  currentConversation?.id === conversation.id ? 'active' : ''
                }`}
                onClick={() => onSelectConversation(conversation.id)}
              >
                <div className="conversation-item-content">
                  <div className="conversation-main">
                    {editingId === conversation.id ? (
                      <Input
                        value={editTitle}
                        onChange={(e) => setEditTitle(e.target.value)}
                        onPressEnter={() => handleSaveTitle(conversation.id)}
                        onBlur={handleCancelEdit}
                        autoFocus
                        className="edit-title-input"
                      />
                    ) : (
                      <div className="conversation-info">
                        <Text className="conversation-name" ellipsis>
                          {conversation.title || '新对话'}
                        </Text>
                        <Text type="secondary" className="conversation-time">
                          {formatDate(conversation.updated_at)}
                        </Text>
                      </div>
                    )}
                  </div>
                  
                  <Dropdown
                    menu={{ items: getMenuItems(conversation) }}
                    trigger={['click']}
                    placement="bottomRight"
                  >
                    <Button
                      type="text"
                      icon={<MoreOutlined />}
                      size="small"
                      className="conversation-menu-btn"
                      onClick={(e) => e.stopPropagation()}
                    />
                  </Dropdown>
                </div>
              </List.Item>
            )}
          />
        )}
      </div>

      <Modal
        title="删除对话"
        open={deleteModalVisible}
        onOk={handleConfirmDelete}
        onCancel={() => setDeleteModalVisible(false)}
        okText="删除"
        cancelText="取消"
        okButtonProps={{ danger: true }}
      >
        <p>确定要删除这个对话吗？此操作无法撤销。</p>
      </Modal>
    </div>
  );
};

export default ConversationList;