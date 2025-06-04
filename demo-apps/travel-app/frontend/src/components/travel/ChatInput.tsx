import React, { useState } from 'react';
import { TextField, Button, Box, CircularProgress } from '@mui/material';
import SendIcon from '@mui/icons-material/Send';

interface ChatInputProps {
  onSubmit: (message: string) => void;
  isProcessing?: boolean;
  placeholder?: string;
  initialValue?: string;
  value?: string;
  onChange?: (value: string) => void;
}

const ChatInput: React.FC<ChatInputProps> = ({ 
  onSubmit, 
  isProcessing = false,
  placeholder = "I'm looking to plan a trip to...",
  initialValue = '',
  value,
  onChange
}) => {
  const [internalMessage, setInternalMessage] = useState(initialValue);
  const message = value !== undefined ? value : internalMessage;
  const setMessage = onChange || setInternalMessage;
  
  const handleSubmit = (e: React.FormEvent) => {
    e.preventDefault();
    if (message.trim() && !isProcessing) {
      onSubmit(message);
      // Don't clear the message - keep it for reference
      // setMessage('');
    }
  };

  return (
    <Box 
      component="form" 
      onSubmit={handleSubmit} 
      sx={{ 
        display: 'flex', 
        flexDirection: { xs: 'column', sm: 'row' },
        gap: 2,
        width: '100%',
      }}
    >
      <TextField
        fullWidth
        value={message}
        onChange={(e) => setMessage(e.target.value)}
        placeholder={placeholder}
        disabled={isProcessing}
        variant="outlined"
        multiline
        minRows={2}
        maxRows={4}
        aria-label="Enter your travel request"
        sx={{ 
          '& .MuiOutlinedInput-root': {
            borderRadius: '8px',
          }
        }}
      />
      <Button 
        type="submit" 
        variant="contained" 
        color="primary"
        disabled={!message.trim() || isProcessing}
        sx={{ 
          height: { xs: '40px', sm: '56px' }, 
          alignSelf: { xs: 'flex-end', sm: 'flex-start' },
          minWidth: '120px',
          borderRadius: '8px'
        }}
        aria-label={isProcessing ? "Processing request" : "Start planning"}
      >
        {isProcessing ? (
          <>
            <CircularProgress size={20} color="inherit" sx={{ mr: 1 }} /> 
            Processing...
          </>
        ) : (
          <>
            <SendIcon sx={{ mr: 1 }} /> 
            Plan
          </>
        )}
      </Button>
    </Box>
  );
};

export default ChatInput; 