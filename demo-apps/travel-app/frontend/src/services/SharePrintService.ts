/**
 * Service for sharing and printing travel-related data
 */
import { TravelPlan, Flight, Accommodation, Activity } from '../models/TravelPlan';
import { formatDate, formatTime, formatCurrency } from '../utils/formatters';

/**
 * SharePrintService handles sharing and printing of travel results
 */
class SharePrintService {
  /**
   * Share an itinerary using the Web Share API
   * @param travelPlan The travel plan to share
   */
  shareItinerary(travelPlan: TravelPlan): Promise<void> {
    const title = `Travel Itinerary: ${travelPlan.title}`;
    const text = this.generateItineraryText(travelPlan);
    const url = window.location.href;
    
    if (navigator.share) {
      return navigator.share({
        title,
        text,
        url
      }).catch(error => {
        console.error('Error sharing:', error);
        this.fallbackShare(title, text);
      });
    } else {
      this.fallbackShare(title, text);
      return Promise.resolve();
    }
  }
  
  /**
   * Share a flight booking using the Web Share API
   * @param flight The flight to share
   */
  shareFlight(flight: Flight): Promise<void> {
    const title = `Flight: ${flight.airline} ${flight.flightNumber}`;
    const text = this.generateFlightText(flight);
    const url = window.location.href;
    
    if (navigator.share) {
      return navigator.share({
        title,
        text,
        url
      }).catch(error => {
        console.error('Error sharing:', error);
        this.fallbackShare(title, text);
      });
    } else {
      this.fallbackShare(title, text);
      return Promise.resolve();
    }
  }
  
  /**
   * Share an accommodation booking using the Web Share API
   * @param accommodation The accommodation to share
   */
  shareAccommodation(accommodation: Accommodation): Promise<void> {
    const title = `Accommodation: ${accommodation.name}`;
    const text = this.generateAccommodationText(accommodation);
    const url = window.location.href;
    
    if (navigator.share) {
      return navigator.share({
        title,
        text,
        url
      }).catch(error => {
        console.error('Error sharing:', error);
        this.fallbackShare(title, text);
      });
    } else {
      this.fallbackShare(title, text);
      return Promise.resolve();
    }
  }
  
  /**
   * Share an activity using the Web Share API
   * @param activity The activity to share
   */
  shareActivity(activity: Activity): Promise<void> {
    const title = `Activity: ${activity.name}`;
    const text = this.generateActivityText(activity);
    const url = window.location.href;
    
    if (navigator.share) {
      return navigator.share({
        title,
        text,
        url
      }).catch(error => {
        console.error('Error sharing:', error);
        this.fallbackShare(title, text);
      });
    } else {
      this.fallbackShare(title, text);
      return Promise.resolve();
    }
  }
  
  /**
   * Print an itinerary
   * @param travelPlan The travel plan to print
   */
  printItinerary(travelPlan: TravelPlan): void {
    const printContent = this.generatePrintableHTML(travelPlan);
    this.printHTML(printContent);
  }
  
  /**
   * Print a flight booking
   * @param flight The flight to print
   */
  printFlight(flight: Flight): void {
    const printContent = this.generateFlightHTML(flight);
    this.printHTML(printContent);
  }
  
  /**
   * Print an accommodation booking
   * @param accommodation The accommodation to print
   */
  printAccommodation(accommodation: Accommodation): void {
    const printContent = this.generateAccommodationHTML(accommodation);
    this.printHTML(printContent);
  }
  
  /**
   * Print an activity
   * @param activity The activity to print
   */
  printActivity(activity: Activity): void {
    const printContent = this.generateActivityHTML(activity);
    this.printHTML(printContent);
  }
  
  /**
   * Fallback for sharing when Web Share API is not available
   * @param title The title to share
   * @param text The text to share
   */
  private fallbackShare(title: string, text: string): void {
    // Copy to clipboard
    const fullText = `${title}\n\n${text}`;
    
    if (navigator.clipboard) {
      navigator.clipboard.writeText(fullText)
        .then(() => {
          alert('Copied to clipboard! You can now paste and share it manually.');
        })
        .catch(err => {
          console.error('Failed to copy text:', err);
          this.fallbackTextArea(fullText);
        });
    } else {
      this.fallbackTextArea(fullText);
    }
  }
  
  /**
   * Fallback method using a textarea for copying content
   * @param text The text to copy
   */
  private fallbackTextArea(text: string): void {
    const textArea = document.createElement('textarea');
    textArea.value = text;
    document.body.appendChild(textArea);
    textArea.focus();
    textArea.select();
    
    try {
      document.execCommand('copy');
      alert('Copied to clipboard! You can now paste and share it manually.');
    } catch (err) {
      console.error('Failed to copy text:', err);
      alert('Unable to copy. Please select the text manually and copy.');
    }
    
    document.body.removeChild(textArea);
  }
  
  /**
   * Generate text representation of a travel itinerary
   * @param travelPlan The travel plan
   */
  private generateItineraryText(travelPlan: TravelPlan): string {
    let text = `TRAVEL ITINERARY: ${travelPlan.title}\n`;
    text += `Destination: ${travelPlan.destination.name}, ${travelPlan.destination.country}\n`;
    text += `Dates: ${formatDate(travelPlan.startDate)} - ${formatDate(travelPlan.endDate)}\n`;
    text += `Budget: ${formatCurrency(travelPlan.budget.total, travelPlan.budget.currency)}\n\n`;
    
    if (travelPlan.description) {
      text += `${travelPlan.description}\n\n`;
    }
    
    if (travelPlan.flights && travelPlan.flights.length > 0) {
      text += 'FLIGHTS:\n';
      travelPlan.flights.forEach(flight => {
        text += `- ${flight.airline} ${flight.flightNumber}\n`;
        text += `  From: ${flight.departure.airport} (${formatDate(flight.departure.date)} at ${formatTime(flight.departure.time)})\n`;
        text += `  To: ${flight.arrival.airport} (${formatDate(flight.arrival.date)} at ${formatTime(flight.arrival.time)})\n`;
        text += `  Status: ${flight.status}\n\n`;
      });
    }
    
    if (travelPlan.accommodations && travelPlan.accommodations.length > 0) {
      text += 'ACCOMMODATIONS:\n';
      travelPlan.accommodations.forEach(accommodation => {
        text += `- ${accommodation.name} (${accommodation.type})\n`;
        text += `  Address: ${accommodation.address}\n`;
        text += `  Check-in: ${formatDate(accommodation.checkIn.date)}${accommodation.checkIn.time ? ` at ${formatTime(accommodation.checkIn.time)}` : ''}\n`;
        text += `  Check-out: ${formatDate(accommodation.checkOut.date)}${accommodation.checkOut.time ? ` at ${formatTime(accommodation.checkOut.time)}` : ''}\n`;
        text += `  Status: ${accommodation.status}\n\n`;
      });
    }
    
    if (travelPlan.activities && travelPlan.activities.length > 0) {
      text += 'ACTIVITIES:\n';
      // Group activities by date
      const activitiesByDate: { [key: string]: Activity[] } = {};
      travelPlan.activities.forEach(activity => {
        if (!activitiesByDate[activity.date]) {
          activitiesByDate[activity.date] = [];
        }
        activitiesByDate[activity.date].push(activity);
      });
      
      // Sort dates
      const sortedDates = Object.keys(activitiesByDate).sort((a, b) => {
        return new Date(a).getTime() - new Date(b).getTime();
      });
      
      sortedDates.forEach(date => {
        text += `  ${formatDate(date)}:\n`;
        activitiesByDate[date].forEach(activity => {
          text += `  - ${activity.name}\n`;
          if (activity.location) {
            text += `    Location: ${activity.location}\n`;
          }
          if (activity.startTime) {
            text += `    Time: ${formatTime(activity.startTime)}${activity.endTime ? ` - ${formatTime(activity.endTime)}` : ''}\n`;
          }
          if (activity.description) {
            text += `    ${activity.description}\n`;
          }
          text += '\n';
        });
      });
    }
    
    return text;
  }
  
  /**
   * Generate text representation of a flight
   * @param flight The flight
   */
  private generateFlightText(flight: Flight): string {
    let text = `FLIGHT: ${flight.airline} ${flight.flightNumber}\n\n`;
    text += `From: ${flight.departure.airport}\n`;
    text += `Date: ${formatDate(flight.departure.date)}\n`;
    text += `Time: ${formatTime(flight.departure.time)}\n`;
    if (flight.departure.terminal) {
      text += `Terminal: ${flight.departure.terminal}\n`;
    }
    text += '\n';
    
    text += `To: ${flight.arrival.airport}\n`;
    text += `Date: ${formatDate(flight.arrival.date)}\n`;
    text += `Time: ${formatTime(flight.arrival.time)}\n`;
    if (flight.arrival.terminal) {
      text += `Terminal: ${flight.arrival.terminal}\n`;
    }
    text += '\n';
    
    if (flight.price) {
      text += `Price: ${formatCurrency(flight.price.amount, flight.price.currency)}\n`;
    }
    
    if (flight.bookingReference) {
      text += `Booking Reference: ${flight.bookingReference}\n`;
    }
    
    text += `Status: ${flight.status}\n`;
    
    return text;
  }
  
  /**
   * Generate text representation of an accommodation
   * @param accommodation The accommodation
   */
  private generateAccommodationText(accommodation: Accommodation): string {
    let text = `ACCOMMODATION: ${accommodation.name}\n\n`;
    text += `Type: ${accommodation.type}\n`;
    text += `Address: ${accommodation.address}\n\n`;
    
    text += `Check-in: ${formatDate(accommodation.checkIn.date)}`;
    if (accommodation.checkIn.time) {
      text += ` at ${formatTime(accommodation.checkIn.time)}`;
    }
    text += '\n';
    
    text += `Check-out: ${formatDate(accommodation.checkOut.date)}`;
    if (accommodation.checkOut.time) {
      text += ` at ${formatTime(accommodation.checkOut.time)}`;
    }
    text += '\n\n';
    
    if (accommodation.price) {
      text += `Price: ${formatCurrency(accommodation.price.amount, accommodation.price.currency)}`;
      text += accommodation.price.isTotal ? ' (total)' : ' (per night)';
      text += '\n';
    }
    
    if (accommodation.bookingReference) {
      text += `Booking Reference: ${accommodation.bookingReference}\n`;
    }
    
    text += `Status: ${accommodation.status}\n`;
    
    return text;
  }
  
  /**
   * Generate text representation of an activity
   * @param activity The activity
   */
  private generateActivityText(activity: Activity): string {
    let text = `ACTIVITY: ${activity.name}\n\n`;
    
    if (activity.description) {
      text += `${activity.description}\n\n`;
    }
    
    text += `Date: ${formatDate(activity.date)}\n`;
    
    if (activity.startTime) {
      text += `Time: ${formatTime(activity.startTime)}`;
      if (activity.endTime) {
        text += ` - ${formatTime(activity.endTime)}`;
      }
      text += '\n';
    }
    
    if (activity.location) {
      text += `Location: ${activity.location}\n`;
    }
    
    if (activity.price) {
      text += `Price: ${formatCurrency(activity.price.amount, activity.price.currency)}\n`;
    }
    
    if (activity.bookingReference) {
      text += `Booking Reference: ${activity.bookingReference}\n`;
    }
    
    if (activity.status) {
      text += `Status: ${activity.status}\n`;
    }
    
    return text;
  }
  
  /**
   * Generate printable HTML for a travel itinerary
   * @param travelPlan The travel plan
   */
  private generatePrintableHTML(travelPlan: TravelPlan): string {
    // Use a similar structure to generateItineraryText but with HTML formatting
    let html = `
      <!DOCTYPE html>
      <html>
      <head>
        <title>Travel Itinerary: ${travelPlan.title}</title>
        <style>
          body { font-family: Arial, sans-serif; margin: 20px; }
          h1, h2, h3 { color: #333; }
          .section { margin-bottom: 20px; }
          .item { margin-bottom: 15px; padding-bottom: 15px; border-bottom: 1px solid #eee; }
          .label { font-weight: bold; }
          .date { color: #666; }
          table { width: 100%; border-collapse: collapse; margin-bottom: 15px; }
          th, td { padding: 8px; text-align: left; border-bottom: 1px solid #ddd; }
          th { background-color: #f2f2f2; }
          .status-confirmed { color: green; }
          .status-pending { color: orange; }
          .status-cancelled { color: red; }
          @media print {
            body { font-size: 12pt; }
            .no-print { display: none; }
            a { text-decoration: none; color: black; }
          }
        </style>
      </head>
      <body>
        <h1>Travel Itinerary: ${travelPlan.title}</h1>
        <div class="section">
          <p><span class="label">Destination:</span> ${travelPlan.destination.name}, ${travelPlan.destination.country}${travelPlan.destination.city ? ` (${travelPlan.destination.city})` : ''}</p>
          <p><span class="label">Dates:</span> ${formatDate(travelPlan.startDate)} - ${formatDate(travelPlan.endDate)}</p>
          <p><span class="label">Budget:</span> ${formatCurrency(travelPlan.budget.total, travelPlan.budget.currency)}</p>
          ${travelPlan.description ? `<p>${travelPlan.description}</p>` : ''}
        </div>
    `;
    
    if (travelPlan.flights && travelPlan.flights.length > 0) {
      html += `
        <div class="section">
          <h2>Flights</h2>
          <table>
            <tr>
              <th>Airline</th>
              <th>Flight</th>
              <th>From</th>
              <th>To</th>
              <th>Date</th>
              <th>Status</th>
            </tr>
      `;
      
      travelPlan.flights.forEach(flight => {
        const statusClass = `status-${flight.status.toLowerCase()}`;
        html += `
          <tr>
            <td>${flight.airline}</td>
            <td>${flight.flightNumber}</td>
            <td>${flight.departure.airport}</td>
            <td>${flight.arrival.airport}</td>
            <td>${formatDate(flight.departure.date)}</td>
            <td class="${statusClass}">${flight.status}</td>
          </tr>
        `;
      });
      
      html += '</table></div>';
    }
    
    if (travelPlan.accommodations && travelPlan.accommodations.length > 0) {
      html += `
        <div class="section">
          <h2>Accommodations</h2>
          <table>
            <tr>
              <th>Name</th>
              <th>Type</th>
              <th>Check-in</th>
              <th>Check-out</th>
              <th>Status</th>
            </tr>
      `;
      
      travelPlan.accommodations.forEach(accommodation => {
        const statusClass = `status-${accommodation.status.toLowerCase()}`;
        html += `
          <tr>
            <td>${accommodation.name}</td>
            <td>${accommodation.type}</td>
            <td>${formatDate(accommodation.checkIn.date)}</td>
            <td>${formatDate(accommodation.checkOut.date)}</td>
            <td class="${statusClass}">${accommodation.status}</td>
          </tr>
        `;
      });
      
      html += '</table></div>';
    }
    
    if (travelPlan.activities && travelPlan.activities.length > 0) {
      // Group activities by date
      const activitiesByDate: { [key: string]: Activity[] } = {};
      travelPlan.activities.forEach(activity => {
        if (!activitiesByDate[activity.date]) {
          activitiesByDate[activity.date] = [];
        }
        activitiesByDate[activity.date].push(activity);
      });
      
      // Sort dates
      const sortedDates = Object.keys(activitiesByDate).sort((a, b) => {
        return new Date(a).getTime() - new Date(b).getTime();
      });
      
      html += '<div class="section"><h2>Daily Itinerary</h2>';
      
      sortedDates.forEach(date => {
        html += `<h3 class="date">${formatDate(date)}</h3>`;
        html += '<table><tr><th>Time</th><th>Activity</th><th>Location</th><th>Details</th></tr>';
        
        activitiesByDate[date].sort((a, b) => {
          if (!a.startTime) return 1;
          if (!b.startTime) return -1;
          return a.startTime.localeCompare(b.startTime);
        }).forEach(activity => {
          let statusClass = '';
          if (activity.status) {
            statusClass = `status-${activity.status.toLowerCase()}`;
          }
          
          html += `
            <tr>
              <td>${activity.startTime ? formatTime(activity.startTime) : 'Any time'}</td>
              <td>${activity.name}</td>
              <td>${activity.location || '-'}</td>
              <td>${activity.description || '-'}</td>
            </tr>
          `;
        });
        
        html += '</table>';
      });
      
      html += '</div>';
    }
    
    html += `
        <div class="no-print" style="margin-top: 30px; text-align: center;">
          <button onclick="window.print()">Print this itinerary</button>
          <button onclick="window.close()">Close</button>
        </div>
      </body>
      </html>
    `;
    
    return html;
  }
  
  /**
   * Generate printable HTML for a flight
   * @param flight The flight
   */
  private generateFlightHTML(flight: Flight): string {
    const statusClass = `status-${flight.status.toLowerCase()}`;
    
    let html = `
      <!DOCTYPE html>
      <html>
      <head>
        <title>Flight: ${flight.airline} ${flight.flightNumber}</title>
        <style>
          body { font-family: Arial, sans-serif; margin: 20px; }
          h1, h2 { color: #333; }
          .section { margin-bottom: 20px; }
          .row { display: flex; margin-bottom: 10px; }
          .col { flex: 1; padding: 0 10px; }
          .label { font-weight: bold; display: block; }
          .value { display: block; }
          .status-confirmed { color: green; }
          .status-pending { color: orange; }
          .status-cancelled { color: red; }
          .flight-path { text-align: center; margin: 30px 0; }
          .flight-arrow { font-size: 24px; margin: 0 10px; }
          @media print {
            body { font-size: 12pt; }
            .no-print { display: none; }
          }
        </style>
      </head>
      <body>
        <h1>Flight Details</h1>
        <div class="section">
          <h2>${flight.airline} ${flight.flightNumber}</h2>
          <p class="${statusClass}">Status: ${flight.status}</p>
          
          <div class="flight-path">
            <div class="row">
              <div class="col">
                <span class="label">Departure</span>
                <strong class="value">${flight.departure.airport}</strong>
                <span class="value">${formatDate(flight.departure.date)}</span>
                <span class="value">${formatTime(flight.departure.time)}</span>
                ${flight.departure.terminal ? `<span class="value">Terminal: ${flight.departure.terminal}</span>` : ''}
              </div>
              
              <div class="col flight-arrow">→</div>
              
              <div class="col">
                <span class="label">Arrival</span>
                <strong class="value">${flight.arrival.airport}</strong>
                <span class="value">${formatDate(flight.arrival.date)}</span>
                <span class="value">${formatTime(flight.arrival.time)}</span>
                ${flight.arrival.terminal ? `<span class="value">Terminal: ${flight.arrival.terminal}</span>` : ''}
              </div>
            </div>
          </div>
          
          <div class="row">
            ${flight.price ? `
              <div class="col">
                <span class="label">Price</span>
                <span class="value">${formatCurrency(flight.price.amount, flight.price.currency)}</span>
              </div>
            ` : ''}
            
            ${flight.bookingReference ? `
              <div class="col">
                <span class="label">Booking Reference</span>
                <span class="value">${flight.bookingReference}</span>
              </div>
            ` : ''}
          </div>
        </div>
        
        <div class="no-print" style="margin-top: 30px; text-align: center;">
          <button onclick="window.print()">Print this flight</button>
          <button onclick="window.close()">Close</button>
        </div>
      </body>
      </html>
    `;
    
    return html;
  }
  
  /**
   * Generate printable HTML for an accommodation
   * @param accommodation The accommodation
   */
  private generateAccommodationHTML(accommodation: Accommodation): string {
    const statusClass = `status-${accommodation.status.toLowerCase()}`;
    
    let html = `
      <!DOCTYPE html>
      <html>
      <head>
        <title>Accommodation: ${accommodation.name}</title>
        <style>
          body { font-family: Arial, sans-serif; margin: 20px; }
          h1, h2 { color: #333; }
          .section { margin-bottom: 20px; }
          .row { display: flex; margin-bottom: 10px; }
          .col { flex: 1; padding: 0 10px; }
          .label { font-weight: bold; display: block; }
          .value { display: block; }
          .status-confirmed { color: green; }
          .status-pending { color: orange; }
          .status-cancelled { color: red; }
          @media print {
            body { font-size: 12pt; }
            .no-print { display: none; }
          }
        </style>
      </head>
      <body>
        <h1>Accommodation Details</h1>
        <div class="section">
          <h2>${accommodation.name}</h2>
          <p>${accommodation.type}</p>
          <p class="${statusClass}">Status: ${accommodation.status}</p>
          
          <div class="row">
            <div class="col">
              <span class="label">Address</span>
              <span class="value">${accommodation.address}</span>
            </div>
          </div>
          
          <div class="row">
            <div class="col">
              <span class="label">Check-in</span>
              <span class="value">${formatDate(accommodation.checkIn.date)}</span>
              ${accommodation.checkIn.time ? `<span class="value">Time: ${formatTime(accommodation.checkIn.time)}</span>` : ''}
            </div>
            
            <div class="col">
              <span class="label">Check-out</span>
              <span class="value">${formatDate(accommodation.checkOut.date)}</span>
              ${accommodation.checkOut.time ? `<span class="value">Time: ${formatTime(accommodation.checkOut.time)}</span>` : ''}
            </div>
          </div>
          
          <div class="row">
            ${accommodation.price ? `
              <div class="col">
                <span class="label">Price</span>
                <span class="value">${formatCurrency(accommodation.price.amount, accommodation.price.currency)}${accommodation.price.isTotal ? ' (total)' : ' (per night)'}</span>
              </div>
            ` : ''}
            
            ${accommodation.bookingReference ? `
              <div class="col">
                <span class="label">Booking Reference</span>
                <span class="value">${accommodation.bookingReference}</span>
              </div>
            ` : ''}
          </div>
        </div>
        
        <div class="no-print" style="margin-top: 30px; text-align: center;">
          <button onclick="window.print()">Print this accommodation</button>
          <button onclick="window.close()">Close</button>
        </div>
      </body>
      </html>
    `;
    
    return html;
  }
  
  /**
   * Generate printable HTML for an activity
   * @param activity The activity
   */
  private generateActivityHTML(activity: Activity): string {
    let statusClass = '';
    if (activity.status) {
      statusClass = `status-${activity.status.toLowerCase()}`;
    }
    
    let html = `
      <!DOCTYPE html>
      <html>
      <head>
        <title>Activity: ${activity.name}</title>
        <style>
          body { font-family: Arial, sans-serif; margin: 20px; }
          h1, h2 { color: #333; }
          .section { margin-bottom: 20px; }
          .row { display: flex; margin-bottom: 10px; }
          .col { flex: 1; padding: 0 10px; }
          .label { font-weight: bold; display: block; }
          .value { display: block; }
          .status-confirmed { color: green; }
          .status-pending { color: orange; }
          .status-cancelled { color: red; }
          @media print {
            body { font-size: 12pt; }
            .no-print { display: none; }
          }
        </style>
      </head>
      <body>
        <h1>Activity Details</h1>
        <div class="section">
          <h2>${activity.name}</h2>
          ${activity.status ? `<p class="${statusClass}">Status: ${activity.status}</p>` : ''}
          
          ${activity.description ? `<p>${activity.description}</p>` : ''}
          
          <div class="row">
            <div class="col">
              <span class="label">Date</span>
              <span class="value">${formatDate(activity.date)}</span>
            </div>
            
            ${activity.startTime ? `
              <div class="col">
                <span class="label">Time</span>
                <span class="value">${formatTime(activity.startTime)}${activity.endTime ? ` - ${formatTime(activity.endTime)}` : ''}</span>
              </div>
            ` : ''}
          </div>
          
          ${activity.location ? `
            <div class="row">
              <div class="col">
                <span class="label">Location</span>
                <span class="value">${activity.location}</span>
              </div>
            </div>
          ` : ''}
          
          <div class="row">
            ${activity.price ? `
              <div class="col">
                <span class="label">Price</span>
                <span class="value">${formatCurrency(activity.price.amount, activity.price.currency)}</span>
              </div>
            ` : ''}
            
            ${activity.bookingReference ? `
              <div class="col">
                <span class="label">Booking Reference</span>
                <span class="value">${activity.bookingReference}</span>
              </div>
            ` : ''}
          </div>
        </div>
        
        <div class="no-print" style="margin-top: 30px; text-align: center;">
          <button onclick="window.print()">Print this activity</button>
          <button onclick="window.close()">Close</button>
        </div>
      </body>
      </html>
    `;
    
    return html;
  }
  
  /**
   * Print HTML content by opening a new window
   * @param html The HTML content to print
   */
  private printHTML(html: string): void {
    const printWindow = window.open('', '_blank');
    if (printWindow) {
      printWindow.document.write(html);
      printWindow.document.close();
      // Trigger print when the content is loaded
      printWindow.onload = () => {
        printWindow.print();
      };
    } else {
      alert('Please allow pop-ups to print this content.');
    }
  }
  
  /**
   * Share plain text content
   * @param text The text to share
   */
  shareText(text: string): Promise<void> {
    const title = 'Travel Plan';
    const url = window.location.href;
    
    if (navigator.share) {
      return navigator.share({
        title,
        text,
        url
      }).catch(error => {
        console.error('Error sharing:', error);
        this.fallbackShare(title, text);
      });
    } else {
      this.fallbackShare(title, text);
      return Promise.resolve();
    }
  }
  
  /**
   * Print plain text or markdown content
   * @param content The content to print
   */
  printContent(content: string): void {
    const html = `
      <!DOCTYPE html>
      <html>
      <head>
        <title>Travel Plan</title>
        <style>
          body {
            font-family: Arial, sans-serif;
            max-width: 800px;
            margin: 0 auto;
            padding: 20px;
            white-space: pre-wrap;
          }
          @media print {
            body { margin: 0; padding: 10px; }
          }
        </style>
      </head>
      <body>
        <pre>${content}</pre>
      </body>
      </html>
    `;
    
    this.printHTML(html);
  }
}

export default new SharePrintService(); 