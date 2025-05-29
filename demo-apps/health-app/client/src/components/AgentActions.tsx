/* eslint-disable @typescript-eslint/no-explicit-any */
import { useState, useEffect } from 'react';
import { Box, Paper, Typography, CircularProgress, Chip } from '@mui/material';
import { useRTVIClient } from '@pipecat-ai/client-react';
import { RTVIEvent } from '@pipecat-ai/client-js';

function DisplayParams(props: { args: Record<string, any> }) {
  return (
    <Box sx={{ display: 'flex', flexWrap: 'wrap', gap: 0.5 }}>
      {Object.entries(props.args).map(([key, value]) => {
        if (Array.isArray(value)) {
          return value.map((item, index) => (
            <Chip
              key={`${key}-${index}`}
              label={`${key}: ${item}`}
              size="small"
              color="primary"
              variant="outlined"
            />
          ));
        } else if (typeof value === 'object' && key == 'symptoms_summary') {
          return <Chip
            key={key}
            label={<>{key}: {value.symptoms.map((s: any) => `${s.symptom}`).join(', ')}</>}
            size="small"
            color="primary"
            variant="outlined"
          />
        }
        return (
          <Chip
            key={key}
            label={`${key}: ${value}`}
            size="small"
            color="primary"
            variant="outlined"
          />
        );
      })}
    </Box>
  )
}


export function AgentActions() {
  const [currentAction, setCurrentAction] = useState<{ function_name: string, args: any } | null>(null);
  const client = useRTVIClient();

  useEffect(() => {
    if (!client) return;

    const handleFunctionCall = (event: any) => {
      setCurrentAction({
        function_name: event.function_name.replace(/_/g, ' '),
        args: event.arguments
      });
    };

    const handleBotResponse = () => {
      setCurrentAction(null);
    };

    client.on(RTVIEvent.LLMFunctionCall, handleFunctionCall);
    client.on(RTVIEvent.BotTranscript, handleBotResponse);

    return () => {
      client.off(RTVIEvent.LLMFunctionCall, handleFunctionCall);
      client.off(RTVIEvent.BotTranscript, handleBotResponse);
    };
  }, [client]);

  if (!currentAction) return null;

  return (
    <Paper
      elevation={2}
      sx={{
        position: 'fixed',
        bottom: 80,
        right: 60,
        p: 2,
        display: 'flex',
        flexDirection: 'column',
        gap: 1,
        bgcolor: 'background.paper',
        borderRadius: 2,
        boxShadow: 3,
        zIndex: 1000,
        maxWidth: 480,
      }}
    >
      <div className='flex flex-row gap-2 w-auto'>
        <CircularProgress size={20} />
        <div>
          <Box sx={{ display: 'flex', alignItems: 'center', gap: 1, marginBottom: '12px' }}>

            <Typography variant="body1" color="text.secondary" fontSize={16}>
              <span className='font-semibold'>Performing: </span>{currentAction?.function_name}
            </Typography>
          </Box>

          {currentAction?.args && (
            <DisplayParams args={currentAction.args} />
          )}
        </div>
      </div>

    </Paper>
  );
} 
