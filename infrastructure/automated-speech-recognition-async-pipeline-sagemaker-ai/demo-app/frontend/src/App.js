import React, { useState, useEffect, useRef } from 'react';
import ReactMarkdown from 'react-markdown';
import './App.css';
import { AppConfig as ProdConfig } from './config/AppConfig';
import { AppConfig as DevConfig } from './config/AppConfigDev';
import { Amplify, Auth } from 'aws-amplify';
import { Authenticator } from '@aws-amplify/ui-react';
import '@aws-amplify/ui-react/styles.css';

const AppConfig = process.env.NODE_ENV === 'development' ? DevConfig : ProdConfig;

Amplify.configure({
  Auth: {
    region: 'us-west-2',
    userPoolId: AppConfig.user_pool_id,
    userPoolWebClientId: AppConfig.user_pool_client_id
  }
});

function AudioApp({ signOut, user }) {
  const [audioFile, setAudioFile] = useState('');
  const [audioFiles, setAudioFiles] = useState([]);
  const [style, setStyle] = useState('');
  const [summary, setSummary] = useState('Waiting for summary...');
  const [transcription, setTranscription] = useState('Waiting for transcription...');
  const [activeTab, setActiveTab] = useState('transcription');
  const [isProcessing, setIsProcessing] = useState(false);
  const [processingStage, setProcessingStage] = useState(0);
  const [sessionState, setSessionState] = useState(false);
  const [inputMode, setInputMode] = useState('file');
  const [isRecording, setIsRecording] = useState(false);
  const [recordedBlob, setRecordedBlob] = useState(null);
  const [uploadedFile, setUploadedFile] = useState(null);
  const [fileSizeMB, setFileSizeMB] = useState(0);
  const [theme, setTheme] = useState('modern');
  const [authToken, setAuthToken] = useState(null);

  const audioRef = useRef(null);
  const wsRef = useRef(null);
  const mediaRecorderRef = useRef(null);
  const streamRef = useRef(null);

  useEffect(() => {
    getAuthToken();
    connectWebSocket();
    loadAudioFiles();
    return () => {
      if (wsRef.current) {
        wsRef.current.close();
      }
    };
  }, []);

  const getAuthToken = async () => {
    try {
      const session = await Auth.currentSession();
      setAuthToken(session.getIdToken().getJwtToken());
    } catch (error) {
      console.error('Error getting auth token:', error);
    }
  };





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
      wsRef.current.send(JSON.stringify({ action: 'getConnectionId' }));
    }
    
    wsRef.current.onmessage = (event) => {
      const data = JSON.parse(event.data);
      console.log(data);
      
      if (data.text) {
        // Handle streaming text from Bedrock
        setSummary(prev => prev === 'Processing transcription...' ? data.text : prev + data.text);
      } else if (data.transcription) {
        // Handle transcription data
        setTranscription(data.transcription);
      } else if (data.complete) {
        // Streaming completed, re-enable buttons
        setIsProcessing(false);
        setProcessingStage(0);
        if (window.processingLoop) clearInterval(window.processingLoop);
      } else if (data.error) {
        setSummary(`Error: ${data.error}`);
        setIsProcessing(false);
        setProcessingStage(0);
        if (window.processingLoop) clearInterval(window.processingLoop);
      } else if (data.type === 'summary') {
        setSummary(data.content);
        setIsProcessing(false);
        setProcessingStage(0);
        if (window.processingLoop) clearInterval(window.processingLoop);
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
      setTimeout(() => {
        console.log('Retrying connection');
        connectWebSocket();
      }, 1000);
    };
  };

  const handleAudioChange = async (e) => {
    const file = e.target.value;
    setAudioFile(file);
    if (file && audioRef.current) {
      audioRef.current.src = `audio/${file}`;
      audioRef.current.load();
      
      // Check file size for button disabling
      try {
        const response = await fetch(`audio/${file}`);
        const blob = await response.blob();
        setFileSizeMB(blob.size / (1024 * 1024));
      } catch (error) {
        console.error('Error checking file size:', error);
        setFileSizeMB(0);
      }
    } else {
      setFileSizeMB(0);
    }
  };

  const handleFileUpload = (e) => {
    const file = e.target.files[0];
    if (file && file.type === 'audio/wav') {
      setUploadedFile(file);
      setFileSizeMB(file.size / (1024 * 1024));
      if (audioRef.current) {
        audioRef.current.src = URL.createObjectURL(file);
        audioRef.current.load();
      }
    } else {
      alert('Please select a WAV file');
      setFileSizeMB(0);
    }
  };

  const startRecording = async () => {
    try {
      const stream = await navigator.mediaDevices.getUserMedia({ audio: true });
      streamRef.current = stream;
      
      const mediaRecorder = new MediaRecorder(stream);
      mediaRecorderRef.current = mediaRecorder;
      
      const chunks = [];
      mediaRecorder.ondataavailable = (e) => chunks.push(e.data);
      mediaRecorder.onstop = () => {
        const blob = new Blob(chunks, { type: 'audio/wav' });
        setRecordedBlob(blob);
        setFileSizeMB(blob.size / (1024 * 1024));
        if (audioRef.current) {
          audioRef.current.src = URL.createObjectURL(blob);
          audioRef.current.load();
        }
      };
      
      mediaRecorder.start();
      setIsRecording(true);
    } catch (error) {
      console.error('Error accessing microphone:', error);
      alert('Error accessing microphone. Please check permissions.');
    }
  };

  const stopRecording = () => {
    if (mediaRecorderRef.current && isRecording) {
      mediaRecorderRef.current.stop();
      streamRef.current.getTracks().forEach(track => track.stop());
      setIsRecording(false);
    }
  };

  const resetResults = () => {
    setSummary('Waiting for summary...');
    setTranscription('Waiting for transcription...');
    setProcessingStage(0);
    setAudioFile('');
    setStyle('');
    setUploadedFile(null);
    setRecordedBlob(null);
    setFileSizeMB(0);
    setActiveTab('transcription')
    if (window.processingLoop) clearInterval(window.processingLoop);
    if (audioRef.current) {
      audioRef.current.src = '';
    }
  };

  const uploadToS3 = async (audioBlob, fileName) => {
    // Get presigned URL
    const uploadResponse = await fetch(AppConfig.api_url + '/upload', {
      method: 'POST',
      headers: { 
        'Content-Type': 'application/json',
        'Authorization': `Bearer ${authToken}`
      },
      body: JSON.stringify({
        fileName: fileName,
        contentType: audioBlob.type || 'audio/wav'
      })
    });

    if (!uploadResponse.ok) throw new Error('Failed to get upload URL');
    
    const { uploadUrl, s3Uri } = await uploadResponse.json();

    // Upload file to S3
    const s3Response = await fetch(uploadUrl, {
      method: 'PUT',
      body: audioBlob,
      headers: {
        'Content-Type': audioBlob.type || 'audio/wav'
      }
    });

    if (!s3Response.ok) throw new Error('Failed to upload to S3');
    
    return s3Uri;
  };

  const startTranscription = async (mode) => {
    if (!style) {
      alert('Please select a summarization style');
      return;
    }

    if (inputMode === 'file' && !audioFile) {
      alert('Please select an audio file');
      return;
    }

    if (inputMode === 'record' && !recordedBlob) {
      alert('Please record audio first');
      return;
    }

    if (inputMode === 'upload' && !uploadedFile) {
      alert('Please upload a WAV file');
      return;
    }

    setIsProcessing(true);
    setProcessingStage(1);
    setSummary('Processing transcription...');
    setTranscription('Processing transcription...');

    // Progress through stages with consistent timing
    const loopInterval = setInterval(() => {
      setProcessingStage(prev => {
        if (prev >= 4) return 1;
        return prev + 1;
      });
    }, 2000);
    
    // Store interval to clear it later
    window.processingLoop = loopInterval;

    try {
      let audioBlob;
      let fileName;
      
      if (inputMode === 'file') {
        const audioResponse = await fetch(`audio/${audioFile}`);
        audioBlob = await audioResponse.blob();
        fileName = audioFile;
      } else if (inputMode === 'record') {
        audioBlob = recordedBlob;
        fileName = `recorded-${Date.now()}.wav`;
      } else {
        audioBlob = uploadedFile;
        fileName = uploadedFile.name;
      }

      const fileSizeMB = audioBlob.size / (1024 * 1024);
      setFileSizeMB(fileSizeMB);
      let requestBody;

      if (fileSizeMB > 6) {
        // Use S3 upload for large files
        setSummary('Uploading large file...');
        const s3Uri = await uploadToS3(audioBlob, fileName);
        requestBody = {
          s3Uri: s3Uri,
          style,
          endpoint_name: mode,
          session_id: localStorage.getItem('connectionId')
        };
      } else {
        // Use base64 for small files
        const audioBase64 = await new Promise((resolve) => {
          const reader = new FileReader();
          reader.onloadend = () => resolve(reader.result.split(',')[1]);
          reader.readAsDataURL(audioBlob);
        });
        requestBody = {
          audio: audioBase64,
          style,
          endpoint_name: mode,
          session_id: localStorage.getItem('connectionId')
        };
      }

      setSummary('Processing transcription...');
      const response = await fetch(AppConfig.api_url + '/transcribe', {
        method: 'POST',
        headers: { 
          'Content-Type': 'application/json',
          'Authorization': `Bearer ${authToken}`
        },
        body: JSON.stringify(requestBody)
      });

      if (!response.ok) throw new Error(`HTTP error! status: ${response.status}`);
      
    } catch (error) {
      console.error('Error:', error);
      setSummary('Error starting transcription. Please try again.');
      setIsProcessing(false);
      setProcessingStage(0);
      if (window.processingLoop) clearInterval(window.processingLoop);
    }
  };

  return (
    <div className={`container ${theme}`}>
      <div className="theme-toggle">
        <button 
          onClick={() => setTheme(theme === 'modern' ? 'cassette' : 'modern')}
          className={`theme-btn ${theme}`}
        >
          {theme === 'modern' ? '📼' : '💻'} {theme === 'modern' ? 'Cassette' : 'Modern'}
        </button>
        <button onClick={signOut} className="logout-btn">
          Logout
        </button>
      </div>
      <h1>Voice Analytics Studio</h1>
      <h2>From Speech to Insights</h2>
      
      <div className="controls">
        <div className="selector-group">
          <label>Input Mode:</label>
          <select value={inputMode} onChange={(e) => setInputMode(e.target.value)}>
            <option value="file">Select Audio File</option>
            <option value="record">Record Audio</option>
            <option value="upload">Upload WAV File</option>
          </select>
        </div>

        {inputMode === 'file' && (
          <div className="selector-group">
            <label>Select Audio File:</label>
            <select value={audioFile} onChange={handleAudioChange}>
              <option value="">Choose audio file...</option>
              {audioFiles.map(file => (
                <option key={file} value={file}>{file}</option>
              ))}
            </select>
          </div>
        )}

        {inputMode === 'record' && (
          <div className="selector-group">
            <label>Voice Recording:</label>
            <div className="recording-controls">
              <button 
                onClick={isRecording ? stopRecording : startRecording}
                disabled={isProcessing}
                className={`record-btn ${isRecording ? 'recording' : ''}`}
              >
                {isRecording ? 'Stop Recording' : 'Start Recording'}
              </button>
              {recordedBlob && <span className="recorded-indicator">✓ Audio recorded</span>}
            </div>
          </div>
        )}

        {inputMode === 'upload' && (
          <div className="selector-group">
            <label>Upload WAV File:</label>
            <div className="upload-controls">
              <input 
                type="file" 
                accept=".wav,audio/wav" 
                onChange={handleFileUpload}
                disabled={isProcessing}
                id="file-upload"
                style={{ display: 'none' }}
              />
              <label htmlFor="file-upload" className={`upload-btn ${isProcessing ? 'disabled' : ''}`}>
                📁 Choose WAV File
              </label>
              {uploadedFile && <span className="uploaded-indicator">✓ {uploadedFile.name}</span>}
            </div>
          </div>
        )}

        <div className="selector-group">
          <label>Summarization Style:</label>
          <select value={style} onChange={(e) => setStyle(e.target.value)}>
            <option value="">Choose style...</option>
            <option value="brief">Brief</option>
            <option value="detailed">Detailed</option>
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
          disabled={isProcessing || fileSizeMB > 15}
          title={fileSizeMB > 10 ? 'File too large for real-time processing (>15MB)' : ''}
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
        <button 
          className="reset-btn" 
          onClick={resetResults}
          disabled={isProcessing}
        >
          Reset
        </button>
      </div>

      <div className="pipeline-visualization">
        <div className="pipeline-icons">
          <div className={`pipeline-icon ${processingStage >= 1 ? 'active' : ''}`}>
            <img src="/images/audio.png" alt="Audio" />
            <span>Audio</span>
          </div>
          <div className={`pipeline-arrow ${processingStage >= 2 ? 'flowing' : ''}`}>→</div>
          <div className={`pipeline-icon ${processingStage >= 2 ? 'active' : ''}`}>
            <img src="/images/nim.png" alt="NIM" />
            <span>NIM</span>
          </div>
          <div className={`pipeline-arrow ${processingStage >= 3 ? 'flowing' : ''}`}>→</div>
          <div className={`pipeline-icon ${processingStage >= 3 ? 'active' : ''}`}>
            <img src="/images/amazon_bedrock.png" alt="Bedrock" />
            <span>Amazon Bedrock</span>
          </div>
          <div className={`pipeline-arrow ${processingStage >= 4 ? 'flowing' : ''}`}>→</div>
          <div className={`pipeline-icon ${processingStage >= 4 ? 'active' : ''}`}>
            <img src="/images/insight.png" alt="Insights" />
            <span>Insights</span>
          </div>
        </div>
        <div className="pipeline-commentary">
          {processingStage === 1 && "Processing audio input..."}
          {processingStage === 2 && "Transcribing audio to text with NVIDIA parakeet..."}
          {processingStage === 3 && "Summarising transcription with Anthropic Claude Sonnet 4.5..."}
          {processingStage === 4 && "Generating insights and analysis..."}
        </div>
      </div>

      <div className="output">
        <div className="tabs">
          <button 
            className={`tab ${activeTab === 'transcription' ? 'active' : ''}`}
            onClick={() => setActiveTab('transcription')}
          >
            Transcription
          </button>
          <button 
            className={`tab ${activeTab === 'summary' ? 'active' : ''}`}
            onClick={() => setActiveTab('summary')}
          >
            Summary
            {(summary === 'Processing transcription...' || summary.startsWith('Processing:')) && (
              <span className="processing-badge">processing</span>
            )}
            {summary !== 'Waiting for summary...' && summary !== 'Processing transcription...' && !summary.startsWith('Processing:') && !summary.startsWith('Error:') && (
              <span className="ready-badge">ready</span>
            )}
          </button>
        </div>
        <div className="tab-content">
          {activeTab === 'summary' && (
            <div className="summary-box">
              <ReactMarkdown>{summary}</ReactMarkdown>
            </div>
          )}
          {activeTab === 'transcription' && (
            <div className="transcription-box">
              <p>{transcription}</p>
            </div>
          )}
        </div>
      </div>
    </div>
  );
}

function App() {
  return (
    <Authenticator>
      {({ signOut, user }) => (
        <AudioApp signOut={signOut} user={user} />
      )}
    </Authenticator>
  );
}

export default App;
