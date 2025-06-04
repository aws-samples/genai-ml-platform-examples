import React, { useState } from 'react';
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
  Grid
} from '@mui/material';
import HotelIcon from '@mui/icons-material/Hotel';
import ExpandMoreIcon from '@mui/icons-material/ExpandMore';
import ContentCopyIcon from '@mui/icons-material/ContentCopy';
import CheckCircleIcon from '@mui/icons-material/CheckCircle';
import PendingIcon from '@mui/icons-material/Pending';
import CancelIcon from '@mui/icons-material/Cancel';
import CalendarTodayIcon from '@mui/icons-material/CalendarToday';
import LocationOnIcon from '@mui/icons-material/LocationOn';
import { Accommodation, BookingStatus } from '../../../models/TravelPlan';
import { 
  formatDate, 
  formatTime, 
  formatCurrency,
  formatBookingReference, 
  getStatusLabel 
} from '../../../utils/formatters';

interface AccommodationResultItemProps {
  accommodation: Accommodation;
  onShare?: () => void;
  onPrint?: () => void;
}

/**
 * Component for displaying accommodation details in the results area
 */
const AccommodationResultItem: React.FC<AccommodationResultItemProps> = ({
  accommodation,
  onShare,
  onPrint
}) => {
  const [expanded, setExpanded] = useState(false);
  const theme = useTheme();

  // Get the appropriate status icon
  const getStatusIcon = (status: BookingStatus) => {
    switch (status) {
      case BookingStatus.CONFIRMED:
        return <CheckCircleIcon fontSize="small" sx={{ color: 'success.main' }} />;
      case BookingStatus.PENDING:
        return <PendingIcon fontSize="small" sx={{ color: 'warning.main' }} />;
      case BookingStatus.CANCELLED:
        return <CancelIcon fontSize="small" sx={{ color: 'error.main' }} />;
      default:
        return <></>;
    }
  };

  // Function to copy booking reference to clipboard
  const copyBookingReference = () => {
    if (accommodation.bookingReference) {
      navigator.clipboard.writeText(accommodation.bookingReference);
      // Could add a snackbar notification here
    }
  };

  // Calculate number of nights
  const calculateNights = () => {
    if (!accommodation?.checkIn?.date || !accommodation?.checkOut?.date) {
      return 0; // Return 0 or default value if dates are missing
    }
    const checkIn = new Date(accommodation.checkIn.date);
    const checkOut = new Date(accommodation.checkOut.date);
    const diffTime = Math.abs(checkOut.getTime() - checkIn.getTime());
    const diffDays = Math.ceil(diffTime / (1000 * 60 * 60 * 24));
    return diffDays;
  };

  const nights = calculateNights();

  return (
    <Paper 
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
          p: 2,
          display: 'flex',
          justifyContent: 'space-between',
          alignItems: 'center',
          bgcolor: 'background.paper',
          borderBottom: expanded ? `1px solid ${theme.palette.divider}` : 'none'
        }}
        onClick={() => setExpanded(!expanded)}
      >
        <Box sx={{ display: 'flex', alignItems: 'center' }}>
          <Box
            sx={{
              bgcolor: 'primary.main',
              color: 'primary.contrastText',
              borderRadius: '50%',
              width: 40,
              height: 40,
              display: 'flex',
              alignItems: 'center',
              justifyContent: 'center',
              mr: 2
            }}
          >
            <HotelIcon />
          </Box>
          <Box>
            <Typography variant="subtitle1" fontWeight="bold">
              {accommodation?.name || 'Unknown Accommodation'}
            </Typography>
            <Typography variant="body2" color="text.secondary">
              {accommodation?.type || 'Lodging'} • {formatDate(accommodation?.checkIn?.date || '')}
            </Typography>
          </Box>
        </Box>

        <Box sx={{ display: 'flex', alignItems: 'center' }}>
          <Chip 
            icon={getStatusIcon(accommodation.status)}
            label={getStatusLabel(accommodation.status)}
            size="small"
            sx={{ 
              mr: 2,
              bgcolor: 
                accommodation.status === BookingStatus.CONFIRMED ? 'success.light' :
                accommodation.status === BookingStatus.PENDING ? 'warning.light' : 'error.light',
              color: 'text.primary'
            }}
          />
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

      {/* Expanded content */}
      <Collapse in={expanded} timeout="auto">
        <Box sx={{ p: 2, bgcolor: 'background.default' }}>
          {/* Location section */}
          <Box sx={{ mb: 2 }}>
            <Box sx={{ display: 'flex', alignItems: 'center', mb: 1 }}>
              <LocationOnIcon color="primary" sx={{ mr: 1 }} fontSize="small" />
              <Typography variant="subtitle2">Location</Typography>
            </Box>
            <Typography variant="body2">
              {accommodation.address}
            </Typography>
          </Box>
          
          {/* Dates section */}
          <Grid container spacing={3} sx={{ mb: 2 }}>
            <Grid item xs={12} sm={5}>
              <Box sx={{ display: 'flex', flexDirection: 'column' }}>
                <Box sx={{ display: 'flex', alignItems: 'center', mb: 1 }}>
                  <CalendarTodayIcon color="primary" sx={{ mr: 1 }} fontSize="small" />
                  <Typography variant="subtitle2">Check-in</Typography>
                </Box>
                <Typography variant="body2" fontWeight="bold">
                  {formatDate(accommodation?.checkIn?.date || '')}
                </Typography>
                {accommodation?.checkIn?.time && (
                  <Typography variant="body2" color="text.secondary">
                    Time: {formatTime(accommodation.checkIn.time)}
                  </Typography>
                )}
              </Box>
            </Grid>
            
            <Grid item xs={12} sm={2} sx={{ display: 'flex', alignItems: 'center', justifyContent: 'center' }}>
              <Box sx={{ textAlign: 'center' }}>
                <Typography variant="body2" color="text.secondary">
                  {nights} {nights === 1 ? 'night' : 'nights'}
                </Typography>
              </Box>
            </Grid>
            
            <Grid item xs={12} sm={5}>
              <Box sx={{ display: 'flex', flexDirection: 'column' }}>
                <Box sx={{ display: 'flex', alignItems: 'center', mb: 1 }}>
                  <CalendarTodayIcon color="primary" sx={{ mr: 1 }} fontSize="small" />
                  <Typography variant="subtitle2">Check-out</Typography>
                </Box>
                <Typography variant="body2" fontWeight="bold">
                  {formatDate(accommodation?.checkOut?.date || '')}
                </Typography>
                {accommodation?.checkOut?.time && (
                  <Typography variant="body2" color="text.secondary">
                    Time: {formatTime(accommodation.checkOut.time)}
                  </Typography>
                )}
              </Box>
            </Grid>
          </Grid>

          <Divider sx={{ my: 2 }} />

          {/* Booking details section */}
          <Grid container spacing={2}>
            {accommodation.price && (
              <Grid item xs={12} sm={4}>
                <Typography variant="subtitle2" gutterBottom>
                  Price
                </Typography>
                <Typography variant="body2">
                  {formatCurrency(accommodation.price.amount, accommodation.price.currency)}
                  {accommodation.price.isTotal ? ' total' : ' per night'}
                </Typography>
              </Grid>
            )}
            
            <Grid item xs={12} sm={4}>
              <Typography variant="subtitle2" gutterBottom>
                Booking Reference
              </Typography>
              <Box sx={{ display: 'flex', alignItems: 'center' }}>
                <Typography variant="body2">
                  {formatBookingReference(accommodation.bookingReference)}
                </Typography>
                {accommodation.bookingReference && (
                  <IconButton size="small" onClick={copyBookingReference}>
                    <ContentCopyIcon fontSize="small" />
                  </IconButton>
                )}
              </Box>
            </Grid>
            
            <Grid item xs={12} sm={4}>
              <Typography variant="subtitle2" gutterBottom>
                Status
              </Typography>
              <Chip 
                icon={getStatusIcon(accommodation.status)}
                label={getStatusLabel(accommodation.status)}
                size="small"
                sx={{ 
                  bgcolor: 
                    accommodation.status === BookingStatus.CONFIRMED ? 'success.light' :
                    accommodation.status === BookingStatus.PENDING ? 'warning.light' : 'error.light',
                  color: 'text.primary'
                }}
              />
            </Grid>
          </Grid>

          <Divider sx={{ my: 2 }} />

          {/* Action buttons */}
          <Box sx={{ display: 'flex', justifyContent: 'flex-end', gap: 1 }}>
            {onShare && (
              <Button 
                size="small" 
                variant="outlined" 
                onClick={(e) => {
                  e.stopPropagation();
                  onShare();
                }}
              >
                Share
              </Button>
            )}
            
            {onPrint && (
              <Button 
                size="small" 
                variant="contained" 
                onClick={(e) => {
                  e.stopPropagation();
                  onPrint();
                }}
              >
                Print
              </Button>
            )}
          </Box>
        </Box>
      </Collapse>
    </Paper>
  );
};

export default AccommodationResultItem; 