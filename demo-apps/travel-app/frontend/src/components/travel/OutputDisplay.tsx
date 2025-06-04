import React, { useEffect } from 'react';
import { 
  Box, 
  Paper, 
  Typography, 
  useTheme,
  Alert
} from '@mui/material';
import { useChatContext } from '../../context/ChatContext';
import FlightResultItem from './result-items/FlightResultItem';
import AccommodationResultItem from './result-items/AccommodationResultItem';
import ActivityResultItem from './result-items/ActivityResultItem';
import ItineraryResultItem from './result-items/ItineraryResultItem';
import TravelPlanRenderer from './TravelPlanRenderer';
import { 
  TravelPlan, 
  Flight, 
  Accommodation, 
  Activity
} from '../../models/TravelPlan';
import sharePrintService from '../../services/SharePrintService';
import { config } from '../../services/common/config';
import { dataTransformationService, DataValidationError } from '../../services/data/DataTransformationService';

interface OutputDisplayProps {
  isActive?: boolean;
  results?: any[];
}


/**
 * OutputDisplay component for showing the travel plan results
 */
const OutputDisplay: React.FC<OutputDisplayProps> = ({ 
  isActive = false,
  results = []
}) => {
  const theme = useTheme();
  const { state } = useChatContext();
  
  // Add CSS keyframes for animations
  useEffect(() => {
    // Create style element
    const styleEl = document.createElement('style');
    // Define the keyframes
    const keyframes = `
      @keyframes fadeInUp {
        from {
          opacity: 0;
          transform: translateY(20px);
        }
        to {
          opacity: 1;
          transform: translateY(0);
        }
      }
      
      @keyframes fadeOut {
        from {
          opacity: 1;
          transform: translateY(0);
        }
        to {
          opacity: 0;
          transform: translateY(-20px);
        }
      }
    `;
    styleEl.innerHTML = keyframes;
    document.head.appendChild(styleEl);
    
    return () => {
      // Clean up the style element on unmount
      document.head.removeChild(styleEl);
    };
  }, []);
  
  
  // Function to handle sharing
  const handleShare = (item: any, type: string) => {
    try {
      switch (type) {
        case 'flight':
          sharePrintService.shareFlight(item as Flight);
          break;
        case 'accommodation':
          sharePrintService.shareAccommodation(item as Accommodation);
          break;
        case 'activity':
          sharePrintService.shareActivity(item as Activity);
          break;
        case 'itinerary':
          sharePrintService.shareItinerary(item as TravelPlan);
          break;
        default:
          console.error('Cannot share this item type');
      }
    } catch (error) {
      console.error('Error sharing:', error);
      console.error('Failed to share. Try again later.');
    }
  };
  
  // Function to handle printing
  const handlePrint = (item: any, type: string) => {
    try {
      switch (type) {
        case 'flight':
          sharePrintService.printFlight(item as Flight);
          break;
        case 'accommodation':
          sharePrintService.printAccommodation(item as Accommodation);
          break;
        case 'activity':
          sharePrintService.printActivity(item as Activity);
          break;
        case 'itinerary':
          sharePrintService.printItinerary(item as TravelPlan);
          break;
        default:
          console.error('Cannot print this item type');
      }
    } catch (error) {
      console.error('Error printing:', error);
      console.error('Failed to print. Try again later.');
    }
  };
  
  // Function to view details of an item
  const handleViewDetails = (itemType: string, itemId: string) => {
    console.log(`Viewing details for ${itemType} ${itemId}`);
    // This would typically navigate to a detailed view or show a modal
  };
  
  // Get display results - no need for markdown check here since results 
  // will be processed by renderResults which already handles markdown
  const currentResults = results || state.results || [];
  
  // Debug logging
  console.log('OutputDisplay render:', {
    isActive,
    resultsFromProps: results,
    resultsFromState: state.results,
    currentResults,
    currentResultsLength: currentResults.length
  });

  
  // Detect if we have backend-strands text response using configuration
  const isBackendStrandsResponse = (results: any[]) => {
    if (!results || results.length === 0) return false;
    
    // Use configuration-based detection instead of string heuristics
    if (config.useBackendStrands) {
      // Check if we have a single text result (standardized format)
      if (results.length === 1 && results[0] && typeof results[0] === 'object') {
        const result = results[0];
        return result.type === 'text' && result.content;
      }
    }
    
    return false;
  };

  // Convert results to appropriate components
  const renderResults = (results: any[]) => {
    if (!results || results.length === 0) return null;
    
    // Log results for debugging
    console.log('Rendering results:', results);
    
    // Check if we have markdown content
    if (results.length === 1 && results[0].type === 'markdown') {
      return (
        <Box
          key="travel-plan-markdown"
          sx={{
            opacity: 0,
            animation: 'fadeInUp 0.8s ease-out forwards',
          }}
        >
          <TravelPlanRenderer
            content={results[0].content}
            isActive={isActive}
          />
        </Box>
      );
    }
    
    // Check if this is a backend-strands text response
    if (config.useBackendStrands && isBackendStrandsResponse(results)) {
      console.log('Detected backend-strands text response, using TravelPlanRenderer');
      
      let textContent = '';
      if (typeof results[0] === 'string') {
        textContent = results[0];
      } else if (results[0] && typeof results[0] === 'object') {
        textContent = results[0].content || results[0].response || results[0].text || '';
      }
      
      return (
        <Box
          key="travel-plan-text"
          sx={{
            opacity: 0,
            animation: 'fadeInUp 0.8s ease-out forwards',
          }}
        >
          <TravelPlanRenderer
            content={textContent}
            isActive={isActive}
          />
        </Box>
      );
    }
    
    return results.map((result, index) => {
      // Stagger animation delay based on index
      const animationDelay = index * 0.3; // 300ms delay between each item
      
      // Determine animation based on whether the result is fading out
      const animationStyle = result.fadeOut
        ? { opacity: 1, animation: 'fadeOut 0.8s ease-out forwards' }
        : { opacity: 0, animation: `fadeInUp 0.6s ease-out ${animationDelay}s forwards` };
      // Handle different types of results with validation
      try {
        if (result.type === 'flight' && result.data) {
          console.log('Rendering flight result:', result.data);
          
          // Validate flight data
          try {
            dataTransformationService.validateFlightData(result.data);
          } catch (validationError) {
            console.error('Flight data validation failed:', validationError);
            return renderErrorResult(`flight-error-${index}`, 'Flight data is invalid', validationError, animationStyle);
          }
          
          return (
            <Box
              key={`flight-${index}`}
              sx={animationStyle}
            >
              <FlightResultItem 
                flight={result.data}
                onShare={() => handleShare(result.data, 'flight')}
                onPrint={() => handlePrint(result.data, 'flight')}
              />
            </Box>
          );
        } else if (result.type === 'accommodation' && result.data) {
          // Validate accommodation data
          try {
            dataTransformationService.validateAccommodationData(result.data);
          } catch (validationError) {
            console.error('Accommodation data validation failed:', validationError);
            return renderErrorResult(`accommodation-error-${index}`, 'Accommodation data is invalid', validationError, animationStyle);
          }
          
          return (
            <Box
              key={`accommodation-${index}`}
              sx={animationStyle}
            >
              <AccommodationResultItem 
                accommodation={result.data}
                onShare={() => handleShare(result.data, 'accommodation')}
                onPrint={() => handlePrint(result.data, 'accommodation')}
              />
            </Box>
          );
        } else if (result.type === 'activity' && result.data) {
          // Validate activity data
          try {
            dataTransformationService.validateActivityData(result.data);
          } catch (validationError) {
            console.error('Activity data validation failed:', validationError);
            return renderErrorResult(`activity-error-${index}`, 'Activity data is invalid', validationError, animationStyle);
          }
          
          return (
            <Box
              key={`activity-${index}`}
              sx={animationStyle}
            >
              <ActivityResultItem 
                activity={result.data}
                onShare={() => handleShare(result.data, 'activity')}
                onPrint={() => handlePrint(result.data, 'activity')}
              />
            </Box>
          );
        } else if (result.type === 'itinerary' && result.data) {
          return (
            <Box
              key={`itinerary-${index}`}
              sx={animationStyle}
            >
              <ItineraryResultItem 
                travelPlan={result.data}
                onShare={() => handleShare(result.data, 'itinerary')}
                onPrint={() => handlePrint(result.data, 'itinerary')}
                onViewDetails={handleViewDetails}
              />
            </Box>
          );
        }
      } catch (error) {
        console.error('Error rendering result:', error, result);
        return renderErrorResult(`render-error-${index}`, 'Error rendering result', error, animationStyle);
      }
      
      // Fallback for other result types
      return (
        <Box
          key={index}
          sx={animationStyle}
        >
          <Paper 
            elevation={1}
            sx={{ 
              p: 2, 
              mb: 2, 
              display: 'flex', 
              flexDirection: 'column',
              borderRadius: '8px'
            }}
          >
          <Typography variant="subtitle1" fontWeight="bold">
            {result.title || 'Untitled Item'}
          </Typography>
          {result.description && (
            <Typography variant="body2" color="text.secondary">
              {result.description}
            </Typography>
          )}
          </Paper>
        </Box>
      );
    });
  };

  // Render error result component
  const renderErrorResult = (key: string, message: string, error: any, animationStyle: any) => {
    const errorDetails = error instanceof DataValidationError ? 
      `Validation Error: ${error.message}` : 
      `${error.message || 'Unknown error'}`;
    
    return (
      <Box key={key} sx={animationStyle}>
        <Alert severity="error" variant="outlined" sx={{ mb: 2 }}>
          <Typography variant="subtitle1" gutterBottom>
            {message}
          </Typography>
          <Typography variant="body2" color="text.secondary">
            {errorDetails}
          </Typography>
          {process.env.NODE_ENV === 'development' && (
            <Typography variant="caption" component="pre" sx={{ mt: 1, fontSize: '0.75rem' }}>
              {JSON.stringify(error instanceof DataValidationError ? error.data : error, null, 2)}
            </Typography>
          )}
        </Alert>
      </Box>
    );
  };

  return (
    <Paper 
      elevation={isActive ? 4 : 3}
      sx={{ 
        p: 3, 
        height: '100%',
        minHeight: '600px', // Increased minimum height
        display: 'flex',
        flexDirection: 'column',
        borderRadius: '12px',
        border: isActive ? `2px solid ${theme.palette.primary.main}` : 'none',
        maxWidth: isActive ? '100%' : undefined,
        transform: isActive ? 'scale(1.01)' : 'scale(1)',
        transition: 'all 0.5s ease-in-out',
        boxShadow: isActive 
          ? `0 10px 30px -5px ${theme.palette.primary.main}20` 
          : undefined,
      }}
    >
      {/* Header */}
      <Box sx={{ borderBottom: 1, borderColor: 'divider', mb: 2, pb: 2 }}>
        <Typography 
          variant={isActive ? "h4" : "h5"} 
          component="h2" 
          sx={{ 
            fontWeight: isActive ? 'bold' : 'normal',
            color: isActive ? theme.palette.primary.main : 'inherit',
            position: 'relative',
            display: 'inline-block',
            '&::after': isActive ? {
              content: '""',
              position: 'absolute',
              bottom: -8,
              left: 0,
              width: '50%',
              height: 3,
              background: `linear-gradient(90deg, ${theme.palette.primary.main}, transparent)`,
              borderRadius: 4
            } : {}
          }}
        >
          {isActive ? "Your Travel Plan" : "Travel Plan Results"}
        </Typography>
      </Box>
      
      {/* Results content area */}
      <Box
        sx={{ 
          flex: 1,
          overflow: 'auto',
          position: 'relative',
          minHeight: '450px' // Set minimum height for content area
        }}
      >
        {currentResults.length > 0 ? (
          renderResults(currentResults)
        ) : (
          <Box
            sx={{
              flex: 1,
              display: 'flex',
              flexDirection: 'column',
              alignItems: 'center',
              justifyContent: 'center',
              bgcolor: 'background.paper',
              border: '1px dashed',
              borderColor: 'divider',
              borderRadius: '8px',
              p: 3,
              minHeight: 400
            }}
          >
            <Typography variant="body2" color="text.secondary" align="center">
              {isActive
                ? "Preparing your complete itinerary..."
                : "Enter your travel request to see your personalized travel plan"}
            </Typography>
          </Box>
        )}
      </Box>
    </Paper>
  );
};

export default OutputDisplay; 