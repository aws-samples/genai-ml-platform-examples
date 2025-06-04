/**
 * Unified Data Transformation Service
 * 
 * This service standardizes all data formats (backend-strands, legacy) 
 * to match the UI component interfaces exactly.
 */

import { Flight, Accommodation, Activity, BookingStatus, TravelPlan } from '../../models/TravelPlan';

/**
 * Result types that can be rendered by the UI
 */
export type UIResultType = 'flight' | 'accommodation' | 'activity' | 'itinerary' | 'text';

/**
 * Standardized result format for UI rendering
 */
export interface StandardizedResult {
  id: string;
  type: UIResultType;
  title: string;
  description: string;
  timestamp: string;
  data?: Flight | Accommodation | Activity | TravelPlan;
  content?: string; // For text-based results from backend-strands
}

/**
 * Validation error class
 */
export class DataValidationError extends Error {
  constructor(message: string, public readonly data: any) {
    super(`Data validation failed: ${message}`);
    this.name = 'DataValidationError';
  }
}

/**
 * Data transformation and validation service
 */
class DataTransformationService {
  
  /**
   * Transform backend-strands flight data to UI Flight interface
   */
  transformToFlight(backendData: any): Flight {
    if (!backendData) {
      throw new DataValidationError('Flight data is null or undefined', backendData);
    }

    // Validate required fields
    if (!backendData.airline) {
      throw new DataValidationError('Missing required field: airline', backendData);
    }
    if (!backendData.flight_number && !backendData.flightNumber) {
      throw new DataValidationError('Missing required field: flight_number/flightNumber', backendData);
    }

    const flight: Flight = {
      airline: backendData.airline,
      flightNumber: backendData.flight_number || backendData.flightNumber,
      departure: {
        airport: backendData.origin || backendData.departure?.airport || '',
        terminal: backendData.departure_terminal || backendData.departure?.terminal,
        date: backendData.departure_date || backendData.departure?.date || '',
        time: backendData.departure_time || backendData.departure?.time || ''
      },
      arrival: {
        airport: backendData.destination || backendData.arrival?.airport || '',
        terminal: backendData.arrival_terminal || backendData.arrival?.terminal,
        date: backendData.arrival_date || backendData.arrival?.date || backendData.departure_date || '',
        time: backendData.arrival_time || backendData.arrival?.time || ''
      },
      status: this.mapToBookingStatus(backendData.status),
      bookingReference: backendData.booking_reference || backendData.bookingReference
    };

    // Add price if available
    if (backendData.price !== undefined || backendData.price?.amount !== undefined) {
      flight.price = {
        amount: backendData.price?.amount || backendData.price || 0,
        currency: backendData.currency || backendData.price?.currency || 'USD'
      };
    }

    return flight;
  }

  /**
   * Transform backend-strands hotel data to UI Accommodation interface
   */
  transformToAccommodation(backendData: any): Accommodation {
    if (!backendData) {
      throw new DataValidationError('Accommodation data is null or undefined', backendData);
    }

    // Validate required fields
    if (!backendData.name) {
      throw new DataValidationError('Missing required field: name', backendData);
    }

    const accommodation: Accommodation = {
      name: backendData.name,
      type: backendData.hotel_type || backendData.type || 'Hotel',
      address: backendData.location?.address || backendData.address || '',
      checkIn: {
        date: backendData.check_in_date || backendData.checkIn?.date || '',
        time: backendData.check_in_time || backendData.checkIn?.time || '14:00'
      },
      checkOut: {
        date: backendData.check_out_date || backendData.checkOut?.date || '',
        time: backendData.check_out_time || backendData.checkOut?.time || '11:00'
      },
      status: this.mapToBookingStatus(backendData.status),
      bookingReference: backendData.booking_reference || backendData.bookingReference
    };

    // Add price if available
    if (backendData.price_per_night !== undefined || backendData.price !== undefined) {
      accommodation.price = {
        amount: backendData.price_per_night || backendData.price?.amount || backendData.price || 0,
        currency: backendData.currency || backendData.price?.currency || 'USD',
        isTotal: backendData.price_is_total || false
      };
    }

    return accommodation;
  }

  /**
   * Transform backend-strands activity data to UI Activity interface
   */
  transformToActivity(backendData: any): Activity {
    if (!backendData) {
      throw new DataValidationError('Activity data is null or undefined', backendData);
    }

    // Validate required fields
    if (!backendData.name && !backendData.title) {
      throw new DataValidationError('Missing required field: name/title', backendData);
    }

    const activity: Activity = {
      id: backendData.id || `activity-${Date.now()}-${Math.random().toString(36).substr(2, 9)}`,
      name: backendData.name || backendData.title,
      description: backendData.description,
      date: backendData.date || backendData.activity_date || '',
      startTime: backendData.start_time || backendData.startTime,
      endTime: backendData.end_time || backendData.endTime,
      location: backendData.location,
      bookingReference: backendData.booking_reference || backendData.bookingReference,
      status: this.mapToBookingStatus(backendData.status)
    };

    // Add price if available
    if (backendData.price_per_person !== undefined || backendData.price !== undefined) {
      activity.price = {
        amount: backendData.price_per_person || backendData.price?.amount || backendData.price || 0,
        currency: backendData.currency || backendData.price?.currency || 'USD'
      };
    }

    return activity;
  }

  /**
   * Transform any backend data to standardized result format
   */
  transformToStandardizedResult(data: any, sourceType: 'backend-strands' | 'legacy'): StandardizedResult {
    if (!data) {
      throw new DataValidationError('Result data is null or undefined', data);
    }

    // Handle text-based results (from backend-strands)
    if (typeof data === 'string') {
      return {
        id: `text-result-${Date.now()}`,
        type: 'text',
        title: 'Travel Plan',
        description: 'Generated travel plan',
        timestamp: new Date().toISOString(),
        content: data
      };
    }

    // Handle object-based results
    const resultType = this.determineResultType(data);
    const id = data.id || `${resultType}-${Date.now()}-${Math.random().toString(36).substr(2, 9)}`;

    let standardizedResult: StandardizedResult = {
      id,
      type: resultType,
      title: data.title || data.name || `${resultType} result`,
      description: data.description || '',
      timestamp: data.timestamp || new Date().toISOString()
    };

    // Transform data based on type
    try {
      switch (resultType) {
        case 'flight':
          standardizedResult.data = this.transformToFlight(data.data || data);
          standardizedResult.title = `${standardizedResult.data.departure.airport} to ${standardizedResult.data.arrival.airport}`;
          standardizedResult.description = `${standardizedResult.data.airline} ${standardizedResult.data.flightNumber}`;
          break;

        case 'accommodation':
          standardizedResult.data = this.transformToAccommodation(data.data || data);
          standardizedResult.title = standardizedResult.data.name;
          standardizedResult.description = `${standardizedResult.data.type} accommodation`;
          break;

        case 'activity':
          standardizedResult.data = this.transformToActivity(data.data || data);
          standardizedResult.title = standardizedResult.data.name;
          standardizedResult.description = standardizedResult.data.description || 'Activity';
          break;

        case 'itinerary':
          // Pass through itinerary data as-is for now (already complex object)
          standardizedResult.data = data.data || data;
          break;

        case 'text':
          standardizedResult.content = data.content || data.text || JSON.stringify(data);
          break;

        default:
          console.warn(`Unknown result type: ${resultType}, treating as text`);
          standardizedResult.type = 'text';
          standardizedResult.content = JSON.stringify(data, null, 2);
      }
    } catch (error) {
      console.error(`Error transforming ${resultType} data:`, error);
      // Fallback to text representation
      standardizedResult.type = 'text';
      const errorMessage = error instanceof Error ? error.message : String(error);
      standardizedResult.content = `Error transforming data: ${errorMessage}\n\nRaw data:\n${JSON.stringify(data, null, 2)}`;
    }

    return standardizedResult;
  }

  /**
   * Determine the result type from data
   */
  private determineResultType(data: any): UIResultType {
    // Check explicit type field first
    if (data.type) {
      const type = data.type.toLowerCase();
      if (['flight', 'accommodation', 'activity', 'itinerary', 'text'].includes(type)) {
        return type as UIResultType;
      }
    }

    // Infer from data structure
    if (data.airline || data.flight_number || data.flightNumber) {
      return 'flight';
    }
    if (data.check_in_date || data.checkIn || data.hotel_type) {
      return 'accommodation';
    }
    if (data.activity_date || (data.name && data.location)) {
      return 'activity';
    }
    if (data.dailyItinerary || data.daily_itinerary) {
      return 'itinerary';
    }

    // Default to text
    return 'text';
  }

  /**
   * Map various status values to BookingStatus enum
   */
  private mapToBookingStatus(status: any): BookingStatus {
    if (!status) return BookingStatus.PENDING;

    const statusStr = status.toString().toLowerCase();
    switch (statusStr) {
      case 'confirmed':
      case 'booked':
        return BookingStatus.CONFIRMED;
      case 'cancelled':
      case 'canceled':
        return BookingStatus.CANCELLED;
      case 'pending':
      case 'processing':
      default:
        return BookingStatus.PENDING;
    }
  }

  /**
   * Validate that transformed data matches expected interface
   */
  validateFlightData(flight: Flight): void {
    if (!flight.airline || !flight.flightNumber) {
      throw new DataValidationError('Invalid flight: missing airline or flight number', flight);
    }
    if (!flight.departure.airport || !flight.arrival.airport) {
      throw new DataValidationError('Invalid flight: missing departure or arrival airport', flight);
    }
  }

  validateAccommodationData(accommodation: Accommodation): void {
    if (!accommodation.name || !accommodation.type) {
      throw new DataValidationError('Invalid accommodation: missing name or type', accommodation);
    }
  }

  validateActivityData(activity: Activity): void {
    if (!activity.id || !activity.name) {
      throw new DataValidationError('Invalid activity: missing id or name', activity);
    }
  }

  /**
   * Transform and validate a batch of results
   */
  transformResultsBatch(results: any[], sourceType: 'backend-strands' | 'legacy'): StandardizedResult[] {
    if (!Array.isArray(results)) {
      throw new DataValidationError('Results must be an array', results);
    }

    return results.map((result, index) => {
      try {
        return this.transformToStandardizedResult(result, sourceType);
      } catch (error) {
        console.error(`Error transforming result at index ${index}:`, error);
        const errorMessage = error instanceof Error ? error.message : String(error);
        // Return error result instead of throwing
        return {
          id: `error-${index}-${Date.now()}`,
          type: 'text' as UIResultType,
          title: `Transformation Error`,
          description: `Failed to transform result #${index + 1}`,
          timestamp: new Date().toISOString(),
          content: `Error: ${errorMessage}\n\nOriginal data:\n${JSON.stringify(result, null, 2)}`
        };
      }
    });
  }
}

// Export singleton instance
export const dataTransformationService = new DataTransformationService();
export default dataTransformationService;