/**
 * Utility functions for formatting data for display
 */

/**
 * Format a date string (ISO format) to a readable format
 */
export const formatDate = (dateString: string): string => {
  if (!dateString) return 'N/A';
  
  const date = new Date(dateString);
  return new Intl.DateTimeFormat('en-US', {
    weekday: 'short',
    month: 'short',
    day: 'numeric',
    year: 'numeric'
  }).format(date);
};

/**
 * Format a time string (HH:MM) to a readable format
 */
export const formatTime = (timeString: string): string => {
  if (!timeString) return 'N/A';
  
  // Handle ISO datetime strings
  if (timeString.includes('T')) {
    const date = new Date(timeString);
    return new Intl.DateTimeFormat('en-US', {
      hour: 'numeric',
      minute: 'numeric',
      hour12: true
    }).format(date);
  }
  
  // Handle HH:MM format
  const [hours, minutes] = timeString.split(':').map(Number);
  const date = new Date();
  date.setHours(hours, minutes);
  
  return new Intl.DateTimeFormat('en-US', {
    hour: 'numeric',
    minute: 'numeric',
    hour12: true
  }).format(date);
};

/**
 * Format a currency amount for display
 */
export const formatCurrency = (
  amount: number,
  currency: string = 'USD'
): string => {
  if (amount === undefined || amount === null) return 'N/A';
  
  return new Intl.NumberFormat('en-US', {
    style: 'currency',
    currency,
    minimumFractionDigits: 2,
    maximumFractionDigits: 2
  }).format(amount);
};

/**
 * Format a duration in minutes to a readable format (e.g., 2h 15m)
 */
export const formatDuration = (minutes: number): string => {
  if (!minutes && minutes !== 0) return 'N/A';
  
  const hours = Math.floor(minutes / 60);
  const remainingMinutes = minutes % 60;
  
  if (hours === 0) {
    return `${remainingMinutes}m`;
  } else if (remainingMinutes === 0) {
    return `${hours}h`;
  } else {
    return `${hours}h ${remainingMinutes}m`;
  }
};

/**
 * Calculate the duration between two datetime strings in minutes
 */
export const calculateDuration = (
  startDate: string,
  startTime: string,
  endDate: string,
  endTime: string
): number | null => {
  if (!startDate || !startTime || !endDate || !endTime) return null;
  
  const start = new Date(`${startDate}T${startTime}`);
  const end = new Date(`${endDate}T${endTime}`);
  
  const durationMs = end.getTime() - start.getTime();
  return Math.round(durationMs / (1000 * 60));
};

/**
 * Truncate text with ellipsis if it exceeds the specified length
 */
export const truncateText = (
  text: string,
  maxLength: number = 100
): string => {
  if (!text) return '';
  if (text.length <= maxLength) return text;
  
  return `${text.substring(0, maxLength)}...`;
};

/**
 * Format a booking reference for display
 */
export const formatBookingReference = (
  reference: string | undefined
): string => {
  if (!reference) return 'Pending';
  return reference.toUpperCase();
};

/**
 * Get a human-readable status label
 */
export const getStatusLabel = (status: string): string => {
  const statusMap: Record<string, string> = {
    'PENDING': 'Pending',
    'CONFIRMED': 'Confirmed',
    'CANCELLED': 'Cancelled',
    'DRAFT': 'Draft',
    'PLANNING': 'Planning',
    'COMPLETED': 'Completed'
  };
  
  return statusMap[status] || status;
}; 