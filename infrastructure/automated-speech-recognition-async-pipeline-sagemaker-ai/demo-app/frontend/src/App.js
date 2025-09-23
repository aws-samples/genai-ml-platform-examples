import React, { useState, useEffect, useRef } from 'react';
import ReactMarkdown from 'react-markdown';
import { AppConfig as ProdConfig } from './config/AppConfig';
import { AppConfig as DevConfig } from './config/AppConfigDev';

const AppConfig = process.env.NODE_ENV === 'development' ? DevConfig : ProdConfig;

function App() {
  const [audioFile, setAudioFile] = useState('');
  const [audioFiles, setAudioFiles] = useState([]);
  const [style, setStyle] = useState('');
  const [summary, setSummary] = useState('Waiting for transcription...');
  const [isProcessing, setIsProcessing] = useState(false);
  const [sessionState, setSessionState] = useState(false);
  const audioRef = useRef(null);
  const wsRef = useRef(null);

  useEffect(() => {
    connectWebSocket();
    loadAudioFiles();
    return () => {
      if (wsRef.current) {
        wsRef.current.close();
      }
    };
  }, []);

  const loadAudioFiles = async () => {
    try {
      const response = await fetch('/audio/manifest.json');
      const files = await response.json();
      setAudioFiles(files);
    } catch (error) {
      console.error('Error loading audio files:', error);
    }
  };

  const connectWebSocket = () => {
    wsRef.current = new WebSocket(AppConfig.websocket_url);

    wsRef.current.onopen = () => {
      console.log('WebSocket connection established');
      setSessionState(true);
      // The connection ID is not directly available in the frontend
      // You need to send a message to get it back from the server
      wsRef.current.send(JSON.stringify({ action: 'getConnectionId' }));
    }
    
    wsRef.current.onmessage = (event) => {
      const data = JSON.parse(event.data);
      console.log(data);
      
      if (data.text) {
        // Handle streaming text from Bedrock
        setSummary(prev => prev === 'Processing transcription...' ? data.text : prev + data.text);
      } else if (data.complete) {
        // Streaming completed, re-enable buttons
        setIsProcessing(false);
      } else if (data.error) {
        setSummary(`Error: ${data.error}`);
        setIsProcessing(false);
      } else if (data.type === 'summary') {
        setSummary(data.content);
        setIsProcessing(false);
      } else if (data.type === 'progress') {
        setSummary(`Processing: ${data.message}`);
      } else if (data.connectionId) {
        console.log('Connection ID:', data.connectionId);
        localStorage.setItem('connectionId', data.connectionId);
      }
    };

    wsRef.current.onerror = (error) => {
      console.error('WebSocket error:', error);
      setSessionState(false);
    };

    wsRef.current.onclose = () => {      
      console.log('WebSocket connection closed');
      setSessionState(false);
      setTimeout(function() {
        console.log('Retrying connection')
        connectWebSocket();
      }, 1000);;
    };
  };

  const handleAudioChange = (e) => {
    const file = e.target.value;
    setAudioFile(file);
    if (file && audioRef.current) {
      audioRef.current.src = `audio/${file}`;
      audioRef.current.load();
    }
  };

  const startTranscription = async (mode) => {
    if (!audioFile || !style) {
      alert('Please select both an audio file and summarization style');
      return;
    }

    setIsProcessing(true);
    setSummary('Processing transcription...');

    try {
      const audioResponse = await fetch(`audio/${audioFile}`);
      const audioBlob = await audioResponse.blob();
      const audioBase64 = await new Promise((resolve) => {
        const reader = new FileReader();
        reader.onloadend = () => resolve(reader.result.split(',')[1]);
        reader.readAsDataURL(audioBlob);
      });

      const response = await fetch(AppConfig.api_url+'/transcribe', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ 
          audio: audioBase64, 
          style, 
          endpoint_name: mode,
          session_id: localStorage.getItem('connectionId')
        })
      });

      if (!response.ok) throw new Error(`HTTP error! status: ${response.status}`);
      
      // Don't set isProcessing to false here - let the streaming complete first
      
    } catch (error) {
      console.error('Error:', error);
      setSummary('Error starting transcription. Please try again.');
      setIsProcessing(false);
    }
  };

  return (
    <div className="container">
      <h1>Audio Transcription & Summarization</h1>
      
      <div className="controls">
        <div className="selector-group">
          <label>Select Audio File:</label>
          <select value={audioFile} onChange={handleAudioChange}>
            <option value="">Choose audio file...</option>
            {audioFiles.map(file => (
              <option key={file} value={file}>{file}</option>
            ))}
          </select>
        </div>

        <div className="selector-group">
          <label>Summarization Style:</label>
          <select value={style} onChange={(e) => setStyle(e.target.value)}>
            <option value="">Choose style...</option>
            <option value="brief">Brief</option>
            <option value="detailed">Detailed</option>
            <option value="bullet-points">Bullet Points</option>
          </select>
        </div>
      </div>

      <div className="audio-player">
        <audio ref={audioRef} controls>
          Your browser does not support the audio element.
        </audio>
      </div>

      <div className="transcription-buttons">
        <button 
          className="transcribe-btn placeholder1" 
          onClick={() => startTranscription('nim')}
          disabled={isProcessing}
        >
          Real-time
        </button>
        <button 
          className="transcribe-btn placeholder2" 
          onClick={() => startTranscription('parakeet')}
          disabled={isProcessing}
        >
          Async
        </button>
      </div>

      <div className="output">
        <h3>Summary Output:</h3>
        <div className="summary-box">
          <ReactMarkdown>{summary}</ReactMarkdown>
        </div>
      </div>
    </div>
  );
}

export default App;
