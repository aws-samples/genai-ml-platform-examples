/**
 * Frontend models for travel plan data
 * Based on backend TravelPlan model but optimized for UI display
 */

/**
 * Represents a travel plan created by a user
 */
export interface TravelPlan {
  /**
   * Plan ID
   */
  planId: string;
  
  /**
   * Title of the travel plan
   */
  title: string;
  
  /**
   * Description of the travel plan
   */
  description?: string;
  
  /**
   * Start date of the trip (ISO format)
   */
  startDate: string;
  
  /**
   * End date of the trip (ISO format)
   */
  endDate: string;
  
  /**
   * Destination details
   */
  destination: Destination;
  
  /**
   * Budget information
   */
  budget: Budget;
  
  /**
   * Detailed day-by-day itinerary
   */
  dailyItinerary?: DailyItineraryItem[];
  
  /**
   * Transportation arrangements (flights, transfers, etc.)
   */
  transportation?: TransportationItem[];
  
  /**
   * Special requests for the trip
   */
  specialRequests?: string[];
  
  /**
   * Emergency contacts for the trip
   */
  emergencyContacts?: EmergencyContact[];
  
  /**
   * Flight details if applicable
   */
  flights?: Flight[];
  
  /**
   * Accommodation details if applicable
   */
  accommodations?: Accommodation[];
  
  /**
   * Activities planned during the trip
   */
  activities?: Activity[];
  
  /**
   * Current status of the plan
   */
  status: TravelPlanStatus;
  
  /**
   * When the plan was created
   */
  createdAt: string;
  
  /**
   * When the plan was last updated
   */
  updatedAt: string;
}

/**
 * Represents a destination
 */
export interface Destination {
  /**
   * Name of the destination (e.g., "Bali")
   */
  name: string;
  
  /**
   * Country of the destination
   */
  country: string;
  
  /**
   * City or area within the country
   */
  city?: string;
  
  /**
   * Coordinates for mapping
   */
  coordinates?: {
    latitude: number;
    longitude: number;
  };
}

/**
 * Represents budget information
 */
export interface Budget {
  /**
   * Total budget amount
   */
  total: number;
  
  /**
   * Currency of the budget
   */
  currency: string;
  
  /**
   * Breakdown of the budget by category
   */
  breakdown?: {
    [category: string]: number;
  };
}

/**
 * Represents flight information
 */
export interface Flight {
  /**
   * Flight booking reference
   */
  bookingReference?: string;
  
  /**
   * Airline name
   */
  airline: string;
  
  /**
   * Flight number
   */
  flightNumber: string;
  
  /**
   * Departure information
   */
  departure: {
    airport: string;
    terminal?: string;
    date: string;
    time: string;
  };
  
  /**
   * Arrival information
   */
  arrival: {
    airport: string;
    terminal?: string;
    date: string;
    time: string;
  };
  
  /**
   * Price of the flight
   */
  price?: {
    amount: number;
    currency: string;
  };
  
  /**
   * Booking status
   */
  status: BookingStatus;
}

/**
 * Represents accommodation information
 */
export interface Accommodation {
  /**
   * Accommodation booking reference
   */
  bookingReference?: string;
  
  /**
   * Name of the accommodation
   */
  name: string;
  
  /**
   * Type of accommodation (hotel, hostel, etc.)
   */
  type: string;
  
  /**
   * Address of the accommodation
   */
  address: string;
  
  /**
   * Check-in date and time
   */
  checkIn: {
    date: string;
    time?: string;
  };
  
  /**
   * Check-out date and time
   */
  checkOut: {
    date: string;
    time?: string;
  };
  
  /**
   * Price of the accommodation
   */
  price?: {
    amount: number;
    currency: string;
    isTotal: boolean;
  };
  
  /**
   * Booking status
   */
  status: BookingStatus;
}

/**
 * Represents an activity during the trip
 */
export interface Activity {
  /**
   * Activity ID
   */
  id: string;
  
  /**
   * Name of the activity
   */
  name: string;
  
  /**
   * Description of the activity
   */
  description?: string;
  
  /**
   * Date of the activity
   */
  date: string;
  
  /**
   * Start time of the activity
   */
  startTime?: string;
  
  /**
   * End time of the activity
   */
  endTime?: string;
  
  /**
   * Location of the activity
   */
  location?: string;
  
  /**
   * Price of the activity
   */
  price?: {
    amount: number;
    currency: string;
  };
  
  /**
   * Booking reference if applicable
   */
  bookingReference?: string;
  
  /**
   * Booking status if applicable
   */
  status?: BookingStatus;
}

/**
 * Possible statuses for a travel plan
 */
export enum TravelPlanStatus {
  DRAFT = 'DRAFT',
  PLANNING = 'PLANNING',
  CONFIRMED = 'CONFIRMED',
  COMPLETED = 'COMPLETED',
  CANCELLED = 'CANCELLED'
}

/**
 * Possible statuses for a booking
 */
export enum BookingStatus {
  PENDING = 'PENDING',
  CONFIRMED = 'CONFIRMED',
  CANCELLED = 'CANCELLED'
}

/**
 * Represents a daily itinerary item
 */
export interface DailyItineraryItem {
  /**
   * Day number in the itinerary
   */
  day: number;
  
  /**
   * Date for this day's itinerary (ISO format)
   */
  date: string;
  
  /**
   * Title for this day's itinerary
   */
  title: string;
  
  /**
   * Description of this day's itinerary
   */
  description?: string;
  
  /**
   * Schedule of activities for this day
   */
  schedule: ScheduleItem[];
}

/**
 * Represents a scheduled item in the daily itinerary
 */
export interface ScheduleItem {
  /**
   * Time slot for this activity (e.g., "09:00 - 11:00")
   */
  time: string;
  
  /**
   * Name of the activity
   */
  activity: string;
  
  /**
   * Description of the activity
   */
  description?: string;
  
  /**
   * Type of activity (e.g., "meal", "transportation", "sightseeing")
   */
  type?: string;
  
  /**
   * Location of the activity
   */
  location?: string;
  
  /**
   * Additional notes about the activity
   */
  notes?: string;
}

/**
 * Represents a transportation item
 */
export interface TransportationItem {
  /**
   * Type of transportation (e.g., "Flight", "Train", "Bus", "Transfer")
   */
  type: string;
  
  /**
   * Provider of the transportation service
   */
  provider: string;
  
  /**
   * Details about the transportation
   */
  details: string;
  
  /**
   * Booking reference if applicable
   */
  bookingReference?: string;
}

/**
 * Represents an emergency contact
 */
export interface EmergencyContact {
  /**
   * Name of the emergency contact
   */
  name: string;
  
  /**
   * Phone number of the emergency contact
   */
  phone: string;
  
  /**
   * Email of the emergency contact
   */
  email?: string;
  
  /**
   * Relationship to the traveler
   */
  relationship?: string;
}

/**
 * Generic result item used for display in the OutputDisplay component
 */
export interface ResultItem {
  id: string;
  type: 'flight' | 'accommodation' | 'activity' | 'itinerary' | 'recommendation' | 'booking';
  title: string;
  description?: string;
  data: any; // Type-specific data (Flight, Accommodation, etc.)
  status?: BookingStatus;
  timestamp: string;
} 