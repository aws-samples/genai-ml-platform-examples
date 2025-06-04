import { BackendStrandsApiClient } from '../api/BackendStrandsApiClient';

/**
 * Simple polling service for checking travel plan status
 */
export class PollingService {
  private pollingIntervals: Map<string, number> = new Map();
  
  /**
   * Start polling for a specific plan
   */
  startPolling(
    planId: string, 
    apiClient: BackendStrandsApiClient,
    onUpdate: (data: any) => void,
    interval: number = 2000
  ): void {
    // Stop any existing polling for this plan
    this.stopPolling(planId);
    
    // Start polling immediately
    this.pollOnce(planId, apiClient, onUpdate);
    
    // Then set up interval
    const intervalId = window.setInterval(async () => {
      await this.pollOnce(planId, apiClient, onUpdate);
    }, interval);
    
    this.pollingIntervals.set(planId, intervalId);
  }
  
  /**
   * Poll once and handle the response
   */
  private async pollOnce(
    planId: string,
    apiClient: BackendStrandsApiClient,
    onUpdate: (data: any) => void
  ): Promise<void> {
    try {
      const response = await apiClient.getPlanningStatus(planId);
      onUpdate(response.data);
      
      // Stop polling if in terminal state
      if (['completed', 'failed', 'cancelled'].includes(response.data.status)) {
        this.stopPolling(planId);
      }
    } catch (error) {
      console.error('Polling error:', error);
      // Continue polling even on error
    }
  }
  
  /**
   * Stop polling for a specific plan
   */
  stopPolling(planId: string): void {
    const intervalId = this.pollingIntervals.get(planId);
    if (intervalId) {
      clearInterval(intervalId);
      this.pollingIntervals.delete(planId);
    }
  }
  
  /**
   * Stop all polling
   */
  stopAllPolling(): void {
    this.pollingIntervals.forEach((intervalId, planId) => {
      clearInterval(intervalId);
    });
    this.pollingIntervals.clear();
  }
}

// Export singleton instance
export const pollingService = new PollingService();