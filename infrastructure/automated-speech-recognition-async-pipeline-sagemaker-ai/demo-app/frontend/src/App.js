import React, { useState, useEffect, useRef } from 'react';
import { AppConfig } from  './config/AppConfig' ;

function App() {
  const [audioFile, setAudioFile] = useState('');
  const [style, setStyle] = useState('');
  const [summary, setSummary] = useState('Waiting for transcription...');
  const [isProcessing, setIsProcessing] = useState(false);
  const audioRef = useRef(null);
  const wsRef = useRef(null);

  useEffect(() => {
    connectWebSocket();
    return () => {
      if (wsRef.current) {
        wsRef.current.close();
      }
    };
  }, []);

  const connectWebSocket = () => {
    wsRef.current = new WebSocket('ws://'+AppConfig.websocket_url+'/ws');
    
    wsRef.current.onmessage = (event) => {
      const data = JSON.parse(event.data);
      console.log(data);
      if (data.type === 'summary') {
        setSummary(data.content);
        setIsProcessing(false);
      } else if (data.type === 'progress') {
        setSummary(`Processing: ${data.message}`);
      }
    };

    wsRef.current.onclose = () => {
      setTimeout(connectWebSocket, 3000);
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
      const response = await fetch('/api/transcribe', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ audioFile, style, mode })
      });

      if (!response.ok) throw new Error(`HTTP error! status: ${response.status}`);
      
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
            <option value="audio1.mp3">Sample Audio 1 (17:21)</option>
            <option value="audio2.mp3">Sample Audio 2 (25:03)</option>
            <option value="audio3.mp3">Sample Audio 3 (14:59)</option>
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
          onClick={() => startTranscription('placeholder1')}
          disabled={isProcessing}
        >
          PLACEHOLDER 1
        </button>
        <button 
          className="transcribe-btn placeholder2" 
          onClick={() => startTranscription('placeholder2')}
          disabled={isProcessing}
        >
          PLACEHOLDER 2
        </button>
      </div>

      <div className="output">
        <h3>Summary Output:</h3>
        <div className="summary-box">{summary}</div>
      </div>
    </div>
  );
}

export default App;
