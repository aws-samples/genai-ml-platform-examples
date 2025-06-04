import { WebSocketMessageType } from '../websocket/WebSocketService';
import webSocketService from '../websocket/WebSocketService';

/**
 * Notification severity levels
 */
export enum NotificationSeverity {
  INFO = 'info',
  SUCCESS = 'success',
  WARNING = 'warning',
  ERROR = 'error',
}

/**
 * Notification type
 */
export interface Notification {
  id: string;
  title: string;
  message: string;
  severity: NotificationSeverity;
  timestamp: number;
  read: boolean;
  autoClose?: boolean;
  duration?: number;
  data?: any;
}

/**
 * Notification listener type
 */
export type NotificationListener = (notification: Notification) => void;

/**
 * Notification service for managing user notifications
 */
class NotificationService {
  private notifications: Notification[] = [];
  private listeners: Set<NotificationListener> = new Set();
  private maxNotifications: number = 50;
  private defaultAutoClose: boolean = true;
  private defaultDuration: number = 5000; // 5 seconds

  constructor() {
    // Initialize WebSocket event listeners
    this.initWebSocketListeners();
  }

  /**
   * Initialize WebSocket event listeners
   */
  private initWebSocketListeners(): void {
    // Listen for system notifications
    webSocketService.addEventListener(
      WebSocketMessageType.SYSTEM_NOTIFICATION,
      (event) => {
        const { title, message, severity, autoClose, duration, data } = event.payload;
        this.showNotification({
          title,
          message,
          severity: severity || NotificationSeverity.INFO,
          autoClose,
          duration,
          data,
        });
      }
    );

    // Listen for travel plan updates
    webSocketService.addEventListener(
      WebSocketMessageType.PLAN_UPDATE,
      (event) => {
        const { planId, status, message } = event.payload;
        this.showNotification({
          title: 'Travel Plan Update',
          message: message || `Your travel plan ${planId} status is now: ${status}`,
          severity: NotificationSeverity.INFO,
          data: { planId, status },
        });
      }
    );

    // Listen for interaction requests
    webSocketService.addEventListener(
      WebSocketMessageType.INTERACTION_REQUEST,
      (event) => {
        const { interactionId, question, options } = event.payload;
        this.showNotification({
          title: 'Input Needed',
          message: question || 'Your input is needed to continue planning',
          severity: NotificationSeverity.WARNING,
          autoClose: false, // Don't auto close interaction requests
          data: { interactionId, options },
        });
      }
    );

    // Listen for WebSocket errors
    webSocketService.addEventListener(
      WebSocketMessageType.ERROR,
      (event) => {
        this.showNotification({
          title: 'Connection Error',
          message: 'There was an error with the real-time connection. Some updates may be delayed.',
          severity: NotificationSeverity.ERROR,
        });
      }
    );
  }

  /**
   * Show a notification
   * @param options Notification options
   */
  public showNotification({
    title,
    message,
    severity = NotificationSeverity.INFO,
    autoClose = this.defaultAutoClose,
    duration = this.defaultDuration,
    data,
  }: {
    title: string;
    message: string;
    severity?: NotificationSeverity;
    autoClose?: boolean;
    duration?: number;
    data?: any;
  }): Notification {
    const notification: Notification = {
      id: this.generateId(),
      title,
      message,
      severity,
      timestamp: Date.now(),
      read: false,
      autoClose,
      duration,
      data,
    };

    // Add to notifications list with limit
    this.notifications.unshift(notification);
    if (this.notifications.length > this.maxNotifications) {
      this.notifications = this.notifications.slice(0, this.maxNotifications);
    }

    // Notify all listeners
    this.notifyListeners(notification);

    // Auto close if enabled
    if (autoClose && duration) {
      setTimeout(() => {
        this.removeNotification(notification.id);
      }, duration);
    }

    return notification;
  }

  /**
   * Generate a unique ID for a notification
   */
  private generateId(): string {
    return `notification-${Date.now()}-${Math.random().toString(36).substr(2, 9)}`;
  }

  /**
   * Notify all listeners of a new notification
   * @param notification The notification
   */
  private notifyListeners(notification: Notification): void {
    this.listeners.forEach((listener) => {
      try {
        listener(notification);
      } catch (error) {
        console.error('Error in notification listener:', error);
      }
    });
  }

  /**
   * Get all notifications
   */
  public getNotifications(): Notification[] {
    return [...this.notifications];
  }

  /**
   * Get unread notifications
   */
  public getUnreadNotifications(): Notification[] {
    return this.notifications.filter((notification) => !notification.read);
  }

  /**
   * Mark a notification as read
   * @param id Notification ID
   */
  public markAsRead(id: string): boolean {
    const notification = this.notifications.find((n) => n.id === id);
    if (notification) {
      notification.read = true;
      return true;
    }
    return false;
  }

  /**
   * Mark all notifications as read
   */
  public markAllAsRead(): void {
    this.notifications.forEach((notification) => {
      notification.read = true;
    });
  }

  /**
   * Remove a notification
   * @param id Notification ID
   */
  public removeNotification(id: string): boolean {
    const index = this.notifications.findIndex((n) => n.id === id);
    if (index !== -1) {
      this.notifications.splice(index, 1);
      return true;
    }
    return false;
  }

  /**
   * Clear all notifications
   */
  public clearNotifications(): void {
    this.notifications = [];
  }

  /**
   * Add a notification listener
   * @param listener The listener function
   */
  public addListener(listener: NotificationListener): void {
    this.listeners.add(listener);
  }

  /**
   * Remove a notification listener
   * @param listener The listener function to remove
   */
  public removeListener(listener: NotificationListener): boolean {
    return this.listeners.delete(listener);
  }

  /**
   * Set the maximum number of notifications to keep
   * @param max Maximum number of notifications
   */
  public setMaxNotifications(max: number): void {
    this.maxNotifications = max;
    
    // Trim the list if needed
    if (this.notifications.length > max) {
      this.notifications = this.notifications.slice(0, max);
    }
  }

  /**
   * Set the default auto-close behavior
   * @param autoClose Whether to auto-close by default
   * @param duration Duration in milliseconds before auto-close
   */
  public setDefaultAutoClose(autoClose: boolean, duration?: number): void {
    this.defaultAutoClose = autoClose;
    
    if (duration) {
      this.defaultDuration = duration;
    }
  }
}

// Export as singleton
const notificationService = new NotificationService();
export default notificationService; 