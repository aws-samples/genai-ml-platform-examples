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
import FlightTakeoffIcon from '@mui/icons-material/FlightTakeoff';
import FlightLandIcon from '@mui/icons-material/FlightLand';
import ExpandMoreIcon from '@mui/icons-material/ExpandMore';
import ContentCopyIcon from '@mui/icons-material/ContentCopy';
import ArrowRightAltIcon from '@mui/icons-material/ArrowRightAlt';
import CheckCircleIcon from '@mui/icons-material/CheckCircle';
import PendingIcon from '@mui/icons-material/Pending';
import CancelIcon from '@mui/icons-material/Cancel';
import { Flight, BookingStatus } from '../../../models/TravelPlan';
import { 
  formatDate, 
  formatTime, 
  formatCurrency,
  formatBookingReference, 
  getStatusLabel 
} from '../../../utils/formatters';

interface FlightResultItemProps {
  flight: Flight;
  onShare?: () => void;
  onPrint?: () => void;
}

/**
 * Component for displaying flight details in the results area
 */
const FlightResultItem: React.FC<FlightResultItemProps> = ({
  flight,
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
    if (flight.bookingReference) {
      navigator.clipboard.writeText(flight.bookingReference);
      // Could add a snackbar notification here
    }
  };

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
            <FlightTakeoffIcon />
          </Box>
          <Box>
            <Typography variant="subtitle1" fontWeight="bold">
              {flight?.airline || 'Unknown Airline'} • {flight?.flightNumber || 'N/A'}
            </Typography>
            <Typography variant="body2" color="text.secondary">
              {formatDate(flight?.departure?.date || '')} • {formatTime(flight?.departure?.time || '')}
            </Typography>
          </Box>
        </Box>

        <Box sx={{ display: 'flex', alignItems: 'center' }}>
          <Chip 
            icon={getStatusIcon(flight.status)}
            label={getStatusLabel(flight.status)}
            size="small"
            sx={{ 
              mr: 2,
              bgcolor: 
                flight.status === BookingStatus.CONFIRMED ? 'success.light' :
                flight.status === BookingStatus.PENDING ? 'warning.light' : 'error.light',
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
          {/* Flight route section */}
          <Grid container spacing={2} sx={{ mb: 2 }}>
            <Grid item xs={5}>
              <Box sx={{ display: 'flex', flexDirection: 'column', alignItems: 'flex-start' }}>
                <Box sx={{ display: 'flex', alignItems: 'center', mb: 1 }}>
                  <FlightTakeoffIcon color="primary" sx={{ mr: 1 }} />
                  <Typography variant="subtitle2">Departure</Typography>
                </Box>
                <Typography variant="body2" fontWeight="bold">
                  {flight?.departure?.airport || 'N/A'}
                </Typography>
                <Typography variant="body2" color="text.secondary">
                  {formatDate(flight?.departure?.date || '')}
                </Typography>
                <Typography variant="body2" color="text.secondary">
                  {formatTime(flight?.departure?.time || '')}
                </Typography>
                {flight?.departure?.terminal && (
                  <Typography variant="body2" color="text.secondary">
                    Terminal: {flight.departure.terminal}
                  </Typography>
                )}
              </Box>
            </Grid>
            
            <Grid item xs={2} sx={{ display: 'flex', alignItems: 'center', justifyContent: 'center' }}>
              <ArrowRightAltIcon sx={{ fontSize: 30, color: 'text.secondary' }} />
            </Grid>
            
            <Grid item xs={5}>
              <Box sx={{ display: 'flex', flexDirection: 'column', alignItems: 'flex-start' }}>
                <Box sx={{ display: 'flex', alignItems: 'center', mb: 1 }}>
                  <FlightLandIcon color="primary" sx={{ mr: 1 }} />
                  <Typography variant="subtitle2">Arrival</Typography>
                </Box>
                <Typography variant="body2" fontWeight="bold">
                  {flight?.arrival?.airport || 'N/A'}
                </Typography>
                <Typography variant="body2" color="text.secondary">
                  {formatDate(flight?.arrival?.date || '')}
                </Typography>
                <Typography variant="body2" color="text.secondary">
                  {formatTime(flight?.arrival?.time || '')}
                </Typography>
                {flight?.arrival?.terminal && (
                  <Typography variant="body2" color="text.secondary">
                    Terminal: {flight.arrival.terminal}
                  </Typography>
                )}
              </Box>
            </Grid>
          </Grid>

          <Divider sx={{ my: 2 }} />

          {/* Booking details section */}
          <Grid container spacing={2}>
            {flight.price && (
              <Grid item xs={12} sm={4}>
                <Typography variant="subtitle2" gutterBottom>
                  Price
                </Typography>
                <Typography variant="body2">
                  {formatCurrency(flight.price.amount, flight.price.currency)}
                </Typography>
              </Grid>
            )}
            
            <Grid item xs={12} sm={4}>
              <Typography variant="subtitle2" gutterBottom>
                Booking Reference
              </Typography>
              <Box sx={{ display: 'flex', alignItems: 'center' }}>
                <Typography variant="body2">
                  {formatBookingReference(flight.bookingReference)}
                </Typography>
                {flight.bookingReference && (
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
                icon={getStatusIcon(flight.status)}
                label={getStatusLabel(flight.status)}
                size="small"
                sx={{ 
                  bgcolor: 
                    flight.status === BookingStatus.CONFIRMED ? 'success.light' :
                    flight.status === BookingStatus.PENDING ? 'warning.light' : 'error.light',
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

export default FlightResultItem; 