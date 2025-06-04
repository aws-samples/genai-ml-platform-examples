import { useState, useEffect, useCallback } from 'react';
import { notificationService, Notification, NotificationSeverity } from '../services';

/**
 * Hook for using notifications in React components
 * @returns Notification state and methods
 */
export const useNotifications = () => {
  const [notifications, setNotifications] = useState<Notification[]>(
    notificationService.getNotifications()
  );
  const [unreadCount, setUnreadCount] = useState<number>(
    notificationService.getUnreadNotifications().length
  );

  // Show a new notification
  const showNotification = useCallback(
    (
      title: string,
      message: string,
      severity: NotificationSeverity = NotificationSeverity.INFO,
      autoClose: boolean = true,
      duration?: number,
      data?: any
    ): Notification => {
      return notificationService.showNotification({
        title,
        message,
        severity,
        autoClose,
        duration,
        data,
      });
    },
    []
  );

  // Mark a notification as read
  const markAsRead = useCallback(
    (id: string): boolean => {
      const result = notificationService.markAsRead(id);
      if (result) {
        setNotifications([...notificationService.getNotifications()]);
        setUnreadCount(notificationService.getUnreadNotifications().length);
      }
      return result;
    },
    []
  );

  // Mark all notifications as read
  const markAllAsRead = useCallback(() => {
    notificationService.markAllAsRead();
    setNotifications([...notificationService.getNotifications()]);
    setUnreadCount(0);
  }, []);

  // Remove a notification
  const removeNotification = useCallback(
    (id: string): boolean => {
      const result = notificationService.removeNotification(id);
      if (result) {
        setNotifications([...notificationService.getNotifications()]);
        setUnreadCount(notificationService.getUnreadNotifications().length);
      }
      return result;
    },
    []
  );

  // Clear all notifications
  const clearNotifications = useCallback(() => {
    notificationService.clearNotifications();
    setNotifications([]);
    setUnreadCount(0);
  }, []);

  // Set up notification listener
  useEffect(() => {
    const notificationListener = (notification: Notification) => {
      setNotifications([...notificationService.getNotifications()]);
      setUnreadCount(notificationService.getUnreadNotifications().length);
    };

    notificationService.addListener(notificationListener);

    return () => {
      notificationService.removeListener(notificationListener);
    };
  }, []);

  return {
    notifications,
    unreadCount,
    showNotification,
    markAsRead,
    markAllAsRead,
    removeNotification,
    clearNotifications,
  };
};

export default useNotifications; 