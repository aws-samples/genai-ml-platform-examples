import React, { useState, useRef, useEffect } from 'react';
import { 
  Box, 
  Typography,
  Collapse,
  IconButton,
  Chip,
  Divider,
  Button,
  useTheme,
  Paper,
  Grid,
  List,
  ListItem,
  ListItemIcon,
  ListItemText,
  Stepper,
  Step,
  StepLabel,
  StepContent
} from '@mui/material';
import MapIcon from '@mui/icons-material/Map';
import ExpandMoreIcon from '@mui/icons-material/ExpandMore';
import FlightIcon from '@mui/icons-material/Flight';
import HotelIcon from '@mui/icons-material/Hotel';
import AttractionsIcon from '@mui/icons-material/Attractions';
import RestaurantIcon from '@mui/icons-material/Restaurant';
import CalendarTodayIcon from '@mui/icons-material/CalendarToday';
import AccountBalanceWalletIcon from '@mui/icons-material/AccountBalanceWallet';
import ShareIcon from '@mui/icons-material/Share';
import PrintIcon from '@mui/icons-material/Print';
import DirectionsCarIcon from '@mui/icons-material/DirectionsCar';
import { 
  TravelPlan, 
  TravelPlanStatus,
  Activity 
} from '../../../models/TravelPlan';
import { 
  formatDate, 
  formatCurrency,
  getStatusLabel 
} from '../../../utils/formatters';

interface ItineraryResultItemProps {
  travelPlan: TravelPlan;
  onShare?: () => void;
  onPrint?: () => void;
  onViewDetails?: (itemType: string, itemId: string) => void;
}

/**
 * Component for displaying a complete travel itinerary in the results area
 */
const ItineraryResultItem: React.FC<ItineraryResultItemProps> = ({
  travelPlan,
  onShare,
  onPrint,
  onViewDetails
}) => {
  const [expanded, setExpanded] = useState(false);
  const theme = useTheme();
  const itemRef = useRef<HTMLDivElement>(null);
  // State no longer needed as all steps are active by default

  // Sort activities by date
  const sortedActivities = travelPlan.activities 
    ? [...travelPlan.activities].sort((a, b) => {
        const dateA = new Date(a.date + (a.startTime ? `T${a.startTime}` : ''));
        const dateB = new Date(b.date + (b.startTime ? `T${b.startTime}` : ''));
        return dateA.getTime() - dateB.getTime();
      })
    : [];

  // Group activities by date
  const activitiesByDate: Record<string, Activity[]> = {};
  sortedActivities.forEach(activity => {
    if (!activitiesByDate[activity.date]) {
      activitiesByDate[activity.date] = [];
    }
    activitiesByDate[activity.date].push(activity);
  });

  // Get all dates in order (including travel dates that may not have activities)
  const startDate = new Date(travelPlan.startDate);
  const endDate = new Date(travelPlan.endDate);
  const allDates: string[] = [];
  
  // Generate all dates in the travel period
  for (let date = new Date(startDate); date <= endDate; date.setDate(date.getDate() + 1)) {
    const dateStr = date.toISOString().split('T')[0];
    allDates.push(dateStr);
    
    // Ensure each date has an entry in the activitiesByDate map, even if empty
    if (!activitiesByDate[dateStr]) {
      activitiesByDate[dateStr] = [];
    }
  }
  
  // Use all dates in order for the itinerary
  const orderedDates = allDates;

  // Auto-expand itinerary when it appears
  useEffect(() => {
    const timer = setTimeout(() => {
      setExpanded(true);
      
      // Start a scroll animation after expansion
      if (itemRef.current) {
        const rect = itemRef.current.getBoundingClientRect();
        const scrollTop = window.scrollY || document.documentElement.scrollTop;
        const targetPosition = rect.top + scrollTop;
        
        const start = window.scrollY || document.documentElement.scrollTop;
        const distance = targetPosition - start;
        
        // Animation duration in ms (slow scroll)
        const duration = 2000;
        let startTime: number | null = null;
        
        // Define animation function
        const scrollAnimation = (currentTime: number): void => {
          if (startTime === null) startTime = currentTime;
          const elapsedTime = currentTime - startTime;
          
          // Easing function for smooth animation
          const easeInOutQuad = (t: number): number => t < 0.5 ? 2 * t * t : -1 + (4 - 2 * t) * t;
          
          // Calculate scroll position
          const scrollPosition = start + distance * easeInOutQuad(Math.min(elapsedTime / duration, 1));
          window.scrollTo(0, scrollPosition);
          
          // Continue animation if not complete
          if (elapsedTime < duration) {
            requestAnimationFrame(scrollAnimation);
          }
        };
        
        // Start the scroll animation
        requestAnimationFrame(scrollAnimation);
      }
    }, 500);
    
    return () => clearTimeout(timer);
  // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);
  
  // Fixed slow scroll with all steps active from the beginning
  useEffect(() => {
    if (expanded && orderedDates.length > 0) {
      // All steps are active by default (we've set active={true} in the Step component)
      // No need to update any step indices anymore
      
      // Set the constant slow scroll speed (50% slower)
      const scrollDuration = 40000; // 40 seconds for complete scroll
      
      // Get all itinerary steps at once to determine full scroll length
      setTimeout(() => {
        const allStepElements = orderedDates.map((_, index) => 
          document.getElementById(`itinerary-day-${index}`)
        ).filter(el => el !== null);
        
        if (allStepElements.length > 0) {
          // Get the first and last element positions to determine scroll distance
          const firstElement = allStepElements[0];
          const lastElement = allStepElements[allStepElements.length - 1];
          
          if (firstElement && lastElement) {
            // Use the last element position for the end point, but start from the top of the page
            const lastRect = lastElement.getBoundingClientRect();
            const scrollStart = 0; // Start from the top of the page
            const scrollEnd = lastRect.top + window.scrollY;
            const scrollDistance = scrollEnd - scrollStart;
            
            // Define the animation function for smooth scrolling
            let startTime: number | null = null;
            const smoothScroll = (currentTime: number) => {
              if (startTime === null) startTime = currentTime;
              const elapsedTime = currentTime - startTime;
              
              // Calculate progress ratio (0 to 1)
              const progress = Math.min(elapsedTime / scrollDuration, 1);
              
              // Easing function for smooth animation
              const easeInOutQuad = (t: number): number => 
                t < 0.5 ? 2 * t * t : -1 + (4 - 2 * t) * t;
              
              // Calculate the new scroll position
              const scrollPosition = scrollStart + scrollDistance * easeInOutQuad(progress);
              window.scrollTo(0, scrollPosition);
              
              // Continue animation if not complete
              if (progress < 1) {
                requestAnimationFrame(smoothScroll);
              }
            };
            
            // Start the smooth scroll animation
            requestAnimationFrame(smoothScroll);
          }
        }
      }, 500); // Short delay to ensure DOM is ready
    }
  }, [expanded, orderedDates.length, orderedDates]);

  // Get status color
  const getStatusColor = (status: TravelPlanStatus) => {
    switch (status) {
      case TravelPlanStatus.CONFIRMED:
        return 'success.light';
      case TravelPlanStatus.DRAFT:
      case TravelPlanStatus.PLANNING:
        return 'warning.light';
      case TravelPlanStatus.CANCELLED:
        return 'error.light';
      case TravelPlanStatus.COMPLETED:
        return 'info.light';
      default:
        return 'grey.300';
    }
  };

  // Get icon for activity type
  const getActivityIcon = (activity: Activity) => {
    const name = activity.name.toLowerCase();
    if (name.includes('restaurant') || 
        name.includes('dining') || 
        name.includes('cafe') || 
        name.includes('food')) {
      return <RestaurantIcon fontSize="small" />;
    }
    return <AttractionsIcon fontSize="small" />;
  };

  return (
    <Paper 
      ref={itemRef}
      elevation={2}
      sx={{ 
        mb: 2, 
        borderRadius: '12px',
        overflow: 'hidden',
        border: `1px solid ${theme.palette.divider}`,
        transition: 'all 0.3s ease',
        '&:hover': {
          boxShadow: 3
        }
      }}
    >
      {/* Header section - always visible */}
      <Box
        sx={{
          display: 'flex',
          flexDirection: 'column',
          bgcolor: 'background.paper',
          borderBottom: expanded ? `1px solid ${theme.palette.divider}` : 'none',
          borderTopLeftRadius: '12px',
          borderTopRightRadius: '12px',
          overflow: 'hidden'
        }}
      >
        {/* Destination hero image/gradient background */}
        <Box
          sx={{
            position: 'relative',
            height: 120,
            display: 'flex',
            alignItems: 'flex-end',
            justifyContent: 'flex-start',
            p: 2,
            background: `linear-gradient(45deg, ${theme.palette.primary.main} 0%, ${theme.palette.secondary.main} 100%)`,
            color: 'white',
            '&::before': {
              content: '""',
              position: 'absolute',
              top: 0,
              left: 0,
              right: 0,
              bottom: 0,
              background: 'rgba(0, 0, 0, 0.3)',
              zIndex: 1
            }
          }}
          onClick={() => setExpanded(!expanded)}
        >
          <Box sx={{ position: 'relative', zIndex: 2 }}>
            <Typography variant="h5" fontWeight="bold" sx={{ textShadow: '1px 1px 3px rgba(0,0,0,0.6)' }}>
              {travelPlan.title}
            </Typography>
            <Box sx={{ display: 'flex', alignItems: 'center', gap: 1 }}>
              <MapIcon fontSize="small" />
              <Typography variant="subtitle1">
                {travelPlan.destination.name}, {travelPlan.destination.country}
              </Typography>
            </Box>
          </Box>
        </Box>
        
        {/* Info bar */}
        <Box
          sx={{
            p: 2,
            display: 'flex',
            justifyContent: 'space-between',
            alignItems: 'center',
            flexWrap: 'wrap',
            bgcolor: 'background.paper',
          }}
          onClick={() => setExpanded(!expanded)}
        >
          <Box sx={{ display: 'flex', alignItems: 'center', flexWrap: 'wrap', gap: 2 }}>
            {/* Trip dates */}
            <Box sx={{ display: 'flex', alignItems: 'center' }}>
              <CalendarTodayIcon fontSize="small" sx={{ mr: 0.5, color: theme.palette.primary.main }} />
              <Typography variant="body2">
                {formatDate(travelPlan.startDate)} - {formatDate(travelPlan.endDate)}
              </Typography>
            </Box>
            
            {/* Duration */}
            <Box sx={{ display: 'flex', alignItems: 'center' }}>
              <Typography variant="body2" sx={{ 
                px: 1.5, 
                py: 0.5, 
                borderRadius: 1, 
                bgcolor: theme.palette.grey[100],
                border: `1px solid ${theme.palette.divider}`,
                fontWeight: 500
              }}>
                {Math.ceil((new Date(travelPlan.endDate).getTime() - new Date(travelPlan.startDate).getTime()) / (1000 * 60 * 60 * 24))} Days
              </Typography>
            </Box>
            
            {/* Budget */}
            <Box sx={{ display: 'flex', alignItems: 'center' }}>
              <AccountBalanceWalletIcon fontSize="small" sx={{ mr: 0.5, color: theme.palette.success.main }} />
              <Typography variant="body2">
                {formatCurrency(travelPlan.budget.total, travelPlan.budget.currency)}
              </Typography>
            </Box>
            
            {/* Status chip */}
            <Chip 
              label={getStatusLabel(travelPlan.status)}
              size="small"
              sx={{ 
                bgcolor: getStatusColor(travelPlan.status),
                color: 'text.primary',
                fontWeight: 500
              }}
            />
          </Box>

          <Box sx={{ display: 'flex', alignItems: 'center', mt: { xs: 1, sm: 0 } }}>
            {/* Number of activities badge */}
            {travelPlan.activities && travelPlan.activities.length > 0 && (
              <Box 
                sx={{ 
                  display: 'flex', 
                  alignItems: 'center',
                  mr: 2,
                  py: 0.5,
                  px: 1.5,
                  bgcolor: 'rgba(0, 0, 0, 0.04)',
                  borderRadius: 1,
                  border: `1px solid ${theme.palette.divider}`
                }}
              >
                <AttractionsIcon fontSize="small" sx={{ mr: 0.5 }} />
                <Typography variant="body2">
                  {travelPlan.activities.length} Activities
                </Typography>
              </Box>
            )}
            
            {/* Expand button */}
            <IconButton
              onClick={(e) => {
                e.stopPropagation();
                setExpanded(!expanded);
              }}
              sx={{
                transform: expanded ? 'rotate(180deg)' : 'rotate(0deg)',
                transition: 'transform 0.3s ease-in-out'
              }}
              size="small"
            >
              <ExpandMoreIcon />
            </IconButton>
          </Box>
        </Box>
      </Box>

      {/* Expanded content */}
      <Collapse in={expanded} timeout="auto">
        <Box sx={{ p: 2, bgcolor: 'background.default' }}>
          {/* Description and main details */}
          {travelPlan.description && (
            <Box sx={{ mb: 2 }}>
              <Typography variant="body2" color="text.secondary">
                {travelPlan.description}
              </Typography>
            </Box>
          )}
          
          <Grid container spacing={2} sx={{ mb: 2 }}>
            {/* Destination section */}
            <Grid item xs={12} sm={6}>
              <Box sx={{ display: 'flex', alignItems: 'center', mb: 1 }}>
                <MapIcon color="primary" sx={{ mr: 1 }} fontSize="small" />
                <Typography variant="subtitle2">Destination</Typography>
              </Box>
              <Typography variant="body2">
                {travelPlan.destination.name}, {travelPlan.destination.country}
                {travelPlan.destination.city && ` (${travelPlan.destination.city})`}
              </Typography>
            </Grid>
            
            {/* Date section */}
            <Grid item xs={12} sm={6}>
              <Box sx={{ display: 'flex', alignItems: 'center', mb: 1 }}>
                <CalendarTodayIcon color="primary" sx={{ mr: 1 }} fontSize="small" />
                <Typography variant="subtitle2">Dates</Typography>
              </Box>
              <Typography variant="body2">
                {formatDate(travelPlan.startDate)} - {formatDate(travelPlan.endDate)}
              </Typography>
            </Grid>
          </Grid>
          
          {/* Budget section */}
          <Box sx={{ mb: 2 }}>
            <Box sx={{ display: 'flex', alignItems: 'center', mb: 1 }}>
              <AccountBalanceWalletIcon color="primary" sx={{ mr: 1 }} fontSize="small" />
              <Typography variant="subtitle2">Budget</Typography>
            </Box>
            <Typography variant="body2">
              Total: {formatCurrency(travelPlan.budget.total, travelPlan.budget.currency)}
            </Typography>
            {travelPlan.budget.breakdown && (
              <Grid container spacing={1} sx={{ mt: 1 }}>
                {Object.entries(travelPlan.budget.breakdown).map(([category, amount]) => (
                  <Grid item key={category}>
                    <Chip 
                      label={`${category}: ${formatCurrency(amount, travelPlan.budget.currency)}`}
                      size="small"
                      sx={{ bgcolor: 'background.paper' }}
                    />
                  </Grid>
                ))}
              </Grid>
            )}
          </Box>

          <Divider sx={{ my: 2 }} />

          {/* Flights section */}
          {travelPlan.flights && travelPlan.flights.length > 0 && (
            <>
              <Typography variant="subtitle2" gutterBottom>
                Flights
              </Typography>
              <List dense sx={{ mb: 2 }}>
                {travelPlan.flights.map((flight, index) => (
                  <ListItem 
                    key={index} 
                    sx={{ 
                      bgcolor: 'background.paper', 
                      mb: 1, 
                      borderRadius: '8px',
                      '&:hover': { bgcolor: 'action.hover', cursor: 'pointer' }
                    }}
                    onClick={() => onViewDetails && onViewDetails('flight', flight.flightNumber)}
                  >
                    <ListItemIcon>
                      <FlightIcon color="primary" />
                    </ListItemIcon>
                    <ListItemText 
                      primary={`${flight.airline} ${flight.flightNumber}`}
                      secondary={`${flight.departure.airport} → ${flight.arrival.airport} • ${formatDate(flight.departure.date)}`}
                    />
                    <Chip 
                      label={getStatusLabel(flight.status)}
                      size="small"
                      sx={{ 
                        ml: 1,
                        minWidth: 80
                      }}
                    />
                  </ListItem>
                ))}
              </List>
              <Divider sx={{ my: 2 }} />
            </>
          )}

          {/* Accommodations section */}
          {travelPlan.accommodations && travelPlan.accommodations.length > 0 && (
            <>
              <Typography variant="subtitle2" gutterBottom>
                Accommodations
              </Typography>
              <List dense sx={{ mb: 2 }}>
                {travelPlan.accommodations.map((accommodation, index) => (
                  <ListItem 
                    key={index} 
                    sx={{ 
                      bgcolor: 'background.paper', 
                      mb: 1, 
                      borderRadius: '8px',
                      '&:hover': { bgcolor: 'action.hover', cursor: 'pointer' }
                    }}
                    onClick={() => onViewDetails && onViewDetails('accommodation', accommodation.bookingReference || index.toString())}
                  >
                    <ListItemIcon>
                      <HotelIcon color="primary" />
                    </ListItemIcon>
                    <ListItemText 
                      primary={accommodation.name}
                      secondary={`${accommodation.type} • ${formatDate(accommodation.checkIn.date)} - ${formatDate(accommodation.checkOut.date)}`}
                    />
                    <Chip 
                      label={getStatusLabel(accommodation.status)}
                      size="small"
                      sx={{ 
                        ml: 1,
                        minWidth: 80
                      }}
                    />
                  </ListItem>
                ))}
              </List>
              <Divider sx={{ my: 2 }} />
            </>
          )}

          {/* Transportation section */}
          {travelPlan.transportation && travelPlan.transportation.length > 0 && (
            <>
              <Typography variant="h6" sx={{ mb: 2 }}>
                Transportation
              </Typography>
              <Grid container spacing={2} sx={{ mb: 2 }}>
                {travelPlan.transportation.map((transport, index) => (
                  <Grid item xs={12} sm={6} key={index}>
                    <Paper 
                      elevation={1} 
                      sx={{ 
                        p: 2, 
                        display: 'flex', 
                        flexDirection: 'column',
                        borderRadius: '8px',
                        height: '100%',
                        border: `1px solid ${theme.palette.divider}`
                      }}
                    >
                      <Box sx={{ display: 'flex', alignItems: 'center', mb: 1 }}>
                        {transport.type.toLowerCase() === 'flight' ? (
                          <FlightIcon sx={{ mr: 1, color: theme.palette.info.main }} />
                        ) : transport.type.toLowerCase().includes('transfer') || transport.type.toLowerCase().includes('car') ? (
                          <DirectionsCarIcon sx={{ mr: 1, color: theme.palette.success.main }} />
                        ) : (
                          <FlightIcon sx={{ mr: 1, color: theme.palette.success.main }} />
                        )}
                        <Typography variant="subtitle2">{transport.type}</Typography>
                      </Box>
                      <Typography variant="body2" fontWeight="medium">
                        {transport.provider}
                      </Typography>
                      <Typography variant="body2" color="text.secondary" sx={{ mb: 1 }}>
                        {transport.details}
                      </Typography>
                      {transport.bookingReference && (
                        <Chip 
                          size="small" 
                          label={`Ref: ${transport.bookingReference}`} 
                          sx={{ alignSelf: 'flex-start' }}
                        />
                      )}
                    </Paper>
                  </Grid>
                ))}
              </Grid>
              <Divider sx={{ my: 2 }} />
            </>
          )}

          {/* Emergency contacts section */}
          {travelPlan.emergencyContacts && travelPlan.emergencyContacts.length > 0 && (
            <>
              <Typography variant="h6" sx={{ mb: 2 }}>
                Emergency Contacts
              </Typography>
              <Grid container spacing={2} sx={{ mb: 2 }}>
                {travelPlan.emergencyContacts.map((contact, index) => (
                  <Grid item xs={12} sm={6} md={4} key={index}>
                    <Paper
                      elevation={1}
                      sx={{ 
                        p: 2, 
                        display: 'flex', 
                        flexDirection: 'column',
                        borderRadius: '8px',
                        height: '100%',
                        border: `1px solid ${theme.palette.divider}`
                      }}
                    >
                      <Typography variant="subtitle2">{contact.name}</Typography>
                      <Typography variant="body2" sx={{ mb: 1 }}>
                        {contact.relationship && `${contact.relationship} • `}
                        {contact.phone}
                      </Typography>
                      {contact.email && (
                        <Typography variant="body2" color="text.secondary">
                          {contact.email}
                        </Typography>
                      )}
                    </Paper>
                  </Grid>
                ))}
              </Grid>
              <Divider sx={{ my: 2 }} />
            </>
          )}

          {/* Special requests section */}
          {travelPlan.specialRequests && travelPlan.specialRequests.length > 0 && (
            <>
              <Typography variant="h6" sx={{ mb: 2 }}>
                Special Requests
              </Typography>
              <Box sx={{ mb: 2 }}>
                <List dense>
                  {travelPlan.specialRequests.map((request, index) => (
                    <ListItem key={index}>
                      <ListItemIcon sx={{ minWidth: 32 }}>•</ListItemIcon>
                      <ListItemText primary={request} />
                    </ListItem>
                  ))}
                </List>
              </Box>
              <Divider sx={{ my: 2 }} />
            </>
          )}

          {/* Daily itinerary section */}
          {orderedDates.length > 0 && (
            <>
              <Typography variant="h6" sx={{ mb: 2 }}>
                Daily Itinerary
              </Typography>
              <Stepper orientation="vertical" sx={{ mb: 2 }}>
                {orderedDates.map((date, dateIndex) => {
                  // Get day of week
                  const dayOfWeek = new Date(date).toLocaleDateString('en-US', { weekday: 'long' });
                  // Get day number in trip (Day 1, Day 2, etc.)
                  const dayNumber = dateIndex + 1;
                  
                  // Special indicators for first/last day
                  const isFirstDay = dateIndex === 0;
                  const isLastDay = dateIndex === orderedDates.length - 1;
                  
                  // Count activities for the day
                  const dayActivities = activitiesByDate[date] || [];
                  
                  return (
                    <Step 
                      key={date} 
                      active={true} 
                      completed={false}
                      id={`itinerary-day-${dateIndex}`}
                    >
                      <StepLabel>
                        <Box sx={{ display: 'flex', alignItems: 'center' }}>
                          <Box 
                            sx={{ 
                              bgcolor: theme.palette.primary.main, 
                              color: 'white', 
                              borderRadius: '50%', 
                              width: 30, 
                              height: 30, 
                              display: 'flex', 
                              alignItems: 'center', 
                              justifyContent: 'center',
                              mr: 1,
                              fontWeight: 'bold'
                            }}
                          >
                            {dayNumber}
                          </Box>
                          <Box>
                            <Typography variant="subtitle1" sx={{ fontWeight: 'bold' }}>
                              {dayOfWeek} - {formatDate(date)}
                              {isFirstDay && <Chip size="small" label="Arrival" sx={{ ml: 1, bgcolor: theme.palette.info.light }} />}
                              {isLastDay && <Chip size="small" label="Departure" sx={{ ml: 1, bgcolor: theme.palette.warning.light }} />}
                            </Typography>
                          </Box>
                        </Box>
                      </StepLabel>
                      <StepContent>
                        {/* Flight or travel info for first/last day if applicable */}
                        {isFirstDay && travelPlan.flights && travelPlan.flights.some(f => f.arrival.date === date) && (
                          <Box sx={{ mb: 2, p: 1, bgcolor: 'rgba(3, 169, 244, 0.1)', borderRadius: 1 }}>
                            <Typography variant="subtitle2" sx={{ color: theme.palette.info.main, display: 'flex', alignItems: 'center' }}>
                              <FlightIcon fontSize="small" sx={{ mr: 1 }} /> Arrival Information
                            </Typography>
                            {travelPlan.flights.filter(f => f.arrival.date === date).map((flight, idx) => (
                              <Typography key={idx} variant="body2" sx={{ ml: 3, mt: 0.5 }}>
                                {flight.airline} {flight.flightNumber} arrives at {flight.arrival.time} ({flight.arrival.airport})
                              </Typography>
                            ))}
                          </Box>
                        )}
                        
                        {isLastDay && travelPlan.flights && travelPlan.flights.some(f => f.departure.date === date) && (
                          <Box sx={{ mb: 2, p: 1, bgcolor: 'rgba(255, 152, 0, 0.1)', borderRadius: 1 }}>
                            <Typography variant="subtitle2" sx={{ color: theme.palette.warning.main, display: 'flex', alignItems: 'center' }}>
                              <FlightIcon fontSize="small" sx={{ mr: 1 }} /> Departure Information
                            </Typography>
                            {travelPlan.flights.filter(f => f.departure.date === date).map((flight, idx) => (
                              <Typography key={idx} variant="body2" sx={{ ml: 3, mt: 0.5 }}>
                                {flight.airline} {flight.flightNumber} departs at {flight.departure.time} ({flight.departure.airport})
                              </Typography>
                            ))}
                          </Box>
                        )}
                        
                        {/* Accommodation for this day */}
                        {travelPlan.accommodations && travelPlan.accommodations.some(a => 
                          new Date(a.checkIn.date) <= new Date(date) && 
                          new Date(a.checkOut.date) > new Date(date)
                        ) && (
                          <Box sx={{ mb: 2, p: 1, bgcolor: 'rgba(76, 175, 80, 0.1)', borderRadius: 1 }}>
                            <Typography variant="subtitle2" sx={{ color: theme.palette.success.main, display: 'flex', alignItems: 'center' }}>
                              <HotelIcon fontSize="small" sx={{ mr: 1 }} /> Accommodation
                            </Typography>
                            {travelPlan.accommodations.filter(a => 
                              new Date(a.checkIn.date) <= new Date(date) && 
                              new Date(a.checkOut.date) > new Date(date)
                            ).map((acc, idx) => (
                              <Typography key={idx} variant="body2" sx={{ ml: 3, mt: 0.5 }}>
                                {acc.name} ({acc.type}) - {acc.address}
                              </Typography>
                            ))}
                          </Box>
                        )}
                        
                        {/* Check for detailed daily itinerary first */}
                        {travelPlan.dailyItinerary && travelPlan.dailyItinerary.some(day => day.date === date) ? (
                          <>
                            {travelPlan.dailyItinerary.filter(day => day.date === date).map(dayPlan => (
                              <Box key={dayPlan.day}>
                                <Typography variant="subtitle2" sx={{ mb: 1, mt: 2, color: theme.palette.primary.main }}>
                                  {dayPlan.title}
                                </Typography>
                                
                                {dayPlan.description && (
                                  <Typography variant="body2" sx={{ mb: 2, fontStyle: 'italic' }}>
                                    {dayPlan.description}
                                  </Typography>
                                )}
                                
                                {dayPlan.schedule && dayPlan.schedule.length > 0 ? (
                                  <List dense>
                                    {dayPlan.schedule.map((item, idx) => {
                                      // Different colors based on activity type
                                      const getTypeColor = (type: string) => {
                                        switch (type.toLowerCase()) {
                                          case 'transportation': return theme.palette.info.light;
                                          case 'accommodation': return theme.palette.success.light;
                                          case 'meal': return theme.palette.warning.light;
                                          case 'sightseeing': return theme.palette.primary.light;
                                          case 'cultural': return theme.palette.secondary.light;
                                          case 'adventure': return theme.palette.error.light;
                                          case 'logistics': return theme.palette.grey[300];
                                          default: return theme.palette.grey[200];
                                        }
                                      };
                                      
                                      // Different icons based on activity type
                                      const getTypeIcon = (type: string) => {
                                        switch (type.toLowerCase()) {
                                          case 'transportation': return <FlightIcon fontSize="small" />;
                                          case 'accommodation': return <HotelIcon fontSize="small" />;
                                          case 'meal': return <RestaurantIcon fontSize="small" />;
                                          case 'sightseeing': 
                                          case 'adventure':
                                          case 'cultural':
                                            return <AttractionsIcon fontSize="small" />;
                                          default: return <CalendarTodayIcon fontSize="small" />;
                                        }
                                      };
                                      
                                      return (
                                        <ListItem 
                                          key={idx} 
                                          sx={{ 
                                            bgcolor: 'background.paper', 
                                            mb: 1, 
                                            borderRadius: '8px',
                                            border: `1px solid ${theme.palette.divider}`,
                                            '&:hover': { bgcolor: 'action.hover' }
                                          }}
                                        >
                                          <ListItemIcon>
                                            {getTypeIcon(item.type || 'default')}
                                          </ListItemIcon>
                                          <ListItemText 
                                            primary={
                                              <Box sx={{ display: 'flex', alignItems: 'center' }}>
                                                {item.time && (
                                                  <Typography 
                                                    variant="caption" 
                                                    sx={{ 
                                                      mr: 1, 
                                                      bgcolor: getTypeColor(item.type || 'default'), 
                                                      px: 0.7, 
                                                      py: 0.3, 
                                                      borderRadius: 1,
                                                      fontWeight: 'bold'
                                                    }}
                                                  >
                                                    {item.time}
                                                  </Typography>
                                                )}
                                                <Typography variant="body2" sx={{ fontWeight: 'medium' }}>
                                                  {item.activity}
                                                </Typography>
                                              </Box>
                                            }
                                            secondary={
                                              <Box>
                                                <Typography variant="caption" component="div">
                                                  {item.location || 'No location'} 
                                                  {item.type && ` • ${item.type.charAt(0).toUpperCase() + item.type.slice(1)}`}
                                                </Typography>
                                                {item.description && (
                                                  <Typography variant="caption" color="text.secondary" component="div" sx={{ mt: 0.5 }}>
                                                    {item.description}
                                                  </Typography>
                                                )}
                                                {item.notes && (
                                                  <Typography variant="caption" color="info.main" component="div" sx={{ mt: 0.5, fontStyle: 'italic' }}>
                                                    Note: {item.notes}
                                                  </Typography>
                                                )}
                                              </Box>
                                            }
                                            secondaryTypographyProps={{ component: 'div' }}
                                          />
                                        </ListItem>
                                      );
                                    })}
                                  </List>
                                ) : (
                                  <Box sx={{ p: 2, bgcolor: theme.palette.grey[50], borderRadius: 1, textAlign: 'center' }}>
                                    <Typography variant="body2" color="text.secondary">
                                      No scheduled activities for this day.
                                    </Typography>
                                  </Box>
                                )}
                              </Box>
                            ))}
                          </>
                        ) : (
                          // Fallback to regular activities if no detailed itinerary is available
                          <>
                            {dayActivities.length > 0 ? (
                              <>
                                <Typography variant="subtitle2" sx={{ mb: 1, mt: 2 }}>
                                  Day Activities
                                </Typography>
                                <List dense>
                                  {dayActivities
                                    .sort((a, b) => { 
                                      const timeA = a.startTime || "23:59";
                                      const timeB = b.startTime || "23:59";
                                      return timeA.localeCompare(timeB);
                                    })
                                    .map((activity, actIndex) => (
                                    <ListItem 
                                      key={activity.id} 
                                      sx={{ 
                                        bgcolor: 'background.paper', 
                                        mb: 1, 
                                        borderRadius: '8px',
                                        '&:hover': { bgcolor: 'action.hover', cursor: 'pointer' }
                                      }}
                                      onClick={() => onViewDetails && onViewDetails('activity', activity.id)}
                                    >
                                      <ListItemIcon>
                                        {getActivityIcon(activity)}
                                      </ListItemIcon>
                                      <ListItemText 
                                        primary={
                                          <Box sx={{ display: 'flex', alignItems: 'center' }}>
                                            {activity.startTime && (
                                              <Typography 
                                                variant="caption" 
                                                sx={{ 
                                                  mr: 1, 
                                                  bgcolor: theme.palette.grey[200], 
                                                  px: 0.7, 
                                                  py: 0.3, 
                                                  borderRadius: 1,
                                                  fontWeight: 'bold'
                                                }}
                                              >
                                                {activity.startTime}
                                              </Typography>
                                            )}
                                            <Typography variant="body2" sx={{ fontWeight: 'medium' }}>
                                              {activity.name}
                                            </Typography>
                                          </Box>
                                        }
                                        secondary={
                                          <Box>
                                            <Typography variant="caption" component="div">
                                              {activity.location || 'No location'} 
                                              {activity.price && ` • ${formatCurrency(activity.price.amount, activity.price.currency)}`}
                                            </Typography>
                                            {activity.description && (
                                              <Typography variant="caption" color="text.secondary" component="div" sx={{ mt: 0.5 }}>
                                                {activity.description}
                                              </Typography>
                                            )}
                                          </Box>
                                        }
                                        secondaryTypographyProps={{ component: 'div' }}
                                      />
                                      {activity.status && (
                                        <Chip 
                                          label={getStatusLabel(activity.status)}
                                          size="small"
                                          sx={{ 
                                            ml: 1,
                                            minWidth: 80
                                          }}
                                        />
                                      )}
                                    </ListItem>
                                  ))}
                                </List>
                              </>
                            ) : (
                              <Box sx={{ p: 2, bgcolor: theme.palette.grey[50], borderRadius: 1, textAlign: 'center' }}>
                                <Typography variant="body2" color="text.secondary">
                                  {isFirstDay 
                                    ? "Arrival day - Rest and get settled in" 
                                    : isLastDay 
                                    ? "Departure day - Pack and prepare for your journey home"
                                    : "Free day - Explore at your leisure"}
                                </Typography>
                              </Box>
                            )}
                          </>
                        )}
                      </StepContent>
                    </Step>
                  );
                })}
              </Stepper>
            </>
          )}

          {/* Action buttons */}
          <Box sx={{ display: 'flex', justifyContent: 'flex-end', gap: 1, mt: 2 }}>
            {onShare && (
              <Button 
                size="small" 
                variant="outlined" 
                startIcon={<ShareIcon />}
                onClick={(e) => {
                  e.stopPropagation();
                  onShare();
                }}
              >
                Share Itinerary
              </Button>
            )}
            
            {onPrint && (
              <Button 
                size="small" 
                variant="contained" 
                startIcon={<PrintIcon />}
                onClick={(e) => {
                  e.stopPropagation();
                  onPrint();
                }}
              >
                Print Itinerary
              </Button>
            )}
          </Box>
        </Box>
      </Collapse>
    </Paper>
  );
};

export default ItineraryResultItem;