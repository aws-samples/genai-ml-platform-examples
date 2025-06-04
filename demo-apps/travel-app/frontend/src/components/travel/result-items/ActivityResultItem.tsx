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
import AttractionsIcon from '@mui/icons-material/Attractions';
import RestaurantIcon from '@mui/icons-material/Restaurant';
import ExpandMoreIcon from '@mui/icons-material/ExpandMore';
import ContentCopyIcon from '@mui/icons-material/ContentCopy';
import CheckCircleIcon from '@mui/icons-material/CheckCircle';
import PendingIcon from '@mui/icons-material/Pending';
import CancelIcon from '@mui/icons-material/Cancel';
import AccessTimeIcon from '@mui/icons-material/AccessTime';
import LocationOnIcon from '@mui/icons-material/LocationOn';
import { Activity, BookingStatus } from '../../../models/TravelPlan';
import { 
  formatDate, 
  formatTime, 
  formatCurrency,
  formatBookingReference, 
  getStatusLabel 
} from '../../../utils/formatters';

interface ActivityResultItemProps {
  activity: Activity;
  onShare?: () => void;
  onPrint?: () => void;
}

/**
 * Component for displaying activity details in the results area
 */
const ActivityResultItem: React.FC<ActivityResultItemProps> = ({
  activity,
  onShare,
  onPrint
}) => {
  const [expanded, setExpanded] = useState(false);
  const theme = useTheme();

  // Get the appropriate icon based on name/type
  const getActivityIcon = () => {
    const name = activity.name.toLowerCase();
    if (name.includes('restaurant') || 
        name.includes('dining') || 
        name.includes('cafe') || 
        name.includes('food')) {
      return <RestaurantIcon />;
    }
    return <AttractionsIcon />;
  };

  // Get the appropriate status icon
  const getStatusIcon = (status?: BookingStatus) => {
    if (!status) return <></>;
    
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
    if (activity.bookingReference) {
      navigator.clipboard.writeText(activity.bookingReference);
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
            {getActivityIcon()}
          </Box>
          <Box>
            <Typography variant="subtitle1" fontWeight="bold">
              {activity.name}
            </Typography>
            <Typography variant="body2" color="text.secondary">
              {formatDate(activity.date)} {activity.startTime ? `• ${formatTime(activity.startTime)}` : ''}
            </Typography>
          </Box>
        </Box>

        <Box sx={{ display: 'flex', alignItems: 'center' }}>
          {activity.status && (
            <Chip 
              icon={getStatusIcon(activity.status)}
              label={getStatusLabel(activity.status)}
              size="small"
              sx={{ 
                mr: 2,
                bgcolor: 
                  activity.status === BookingStatus.CONFIRMED ? 'success.light' :
                  activity.status === BookingStatus.PENDING ? 'warning.light' : 'error.light',
                color: 'text.primary'
              }}
            />
          )}
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
          {/* Description section */}
          {activity.description && (
            <Box sx={{ mb: 2 }}>
              <Typography variant="body2">
                {activity.description}
              </Typography>
            </Box>
          )}
          
          <Grid container spacing={2} sx={{ mb: 2 }}>
            {/* Time section */}
            <Grid item xs={12} sm={6}>
              <Box sx={{ display: 'flex', flexDirection: 'column' }}>
                <Box sx={{ display: 'flex', alignItems: 'center', mb: 1 }}>
                  <AccessTimeIcon color="primary" sx={{ mr: 1 }} fontSize="small" />
                  <Typography variant="subtitle2">Time</Typography>
                </Box>
                <Typography variant="body2">
                  {formatDate(activity.date)}
                </Typography>
                {activity.startTime && (
                  <Typography variant="body2">
                    {formatTime(activity.startTime)}
                    {activity.endTime ? ` - ${formatTime(activity.endTime)}` : ''}
                  </Typography>
                )}
              </Box>
            </Grid>
            
            {/* Location section */}
            {activity.location && (
              <Grid item xs={12} sm={6}>
                <Box sx={{ display: 'flex', flexDirection: 'column' }}>
                  <Box sx={{ display: 'flex', alignItems: 'center', mb: 1 }}>
                    <LocationOnIcon color="primary" sx={{ mr: 1 }} fontSize="small" />
                    <Typography variant="subtitle2">Location</Typography>
                  </Box>
                  <Typography variant="body2">
                    {activity.location}
                  </Typography>
                </Box>
              </Grid>
            )}
          </Grid>

          <Divider sx={{ my: 2 }} />

          {/* Booking details section */}
          <Grid container spacing={2}>
            {activity.price && (
              <Grid item xs={12} sm={4}>
                <Typography variant="subtitle2" gutterBottom>
                  Price
                </Typography>
                <Typography variant="body2">
                  {formatCurrency(activity.price.amount, activity.price.currency)}
                </Typography>
              </Grid>
            )}
            
            {activity.bookingReference && (
              <Grid item xs={12} sm={4}>
                <Typography variant="subtitle2" gutterBottom>
                  Booking Reference
                </Typography>
                <Box sx={{ display: 'flex', alignItems: 'center' }}>
                  <Typography variant="body2">
                    {formatBookingReference(activity.bookingReference)}
                  </Typography>
                  <IconButton size="small" onClick={copyBookingReference}>
                    <ContentCopyIcon fontSize="small" />
                  </IconButton>
                </Box>
              </Grid>
            )}
            
            {activity.status && (
              <Grid item xs={12} sm={4}>
                <Typography variant="subtitle2" gutterBottom>
                  Status
                </Typography>
                <Chip 
                  icon={getStatusIcon(activity.status)}
                  label={getStatusLabel(activity.status)}
                  size="small"
                  sx={{ 
                    bgcolor: 
                      activity.status === BookingStatus.CONFIRMED ? 'success.light' :
                      activity.status === BookingStatus.PENDING ? 'warning.light' : 'error.light',
                    color: 'text.primary'
                  }}
                />
              </Grid>
            )}
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

export default ActivityResultItem; 