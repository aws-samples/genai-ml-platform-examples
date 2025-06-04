import React from 'react';
import { Routes, Route } from 'react-router-dom';
import Box from '@mui/material/Box';
import { ThemeProvider } from '@mui/material/styles';
import CssBaseline from '@mui/material/CssBaseline';
import Header from './components/common/Header';
import Footer from './components/common/Footer';
import HomePage from './pages/HomePage';
import DemoPage from './pages/DemoPage';
import AboutPage from './pages/AboutPage';
import { ChatProvider } from './context/ChatContext';
import { Notifications, WebSocketStatus } from './components/common';
import theme from './theme';

const App: React.FC = () => {
  return (
    <ThemeProvider theme={theme}>
      <CssBaseline />
      <ChatProvider>
        <Box className="app-container">
          <Header />
          <Box className="main-content">
            <Routes>
              <Route path="/" element={<HomePage />} />
              <Route path="/demo" element={<DemoPage />} />
              <Route path="/about" element={<AboutPage />} />
            </Routes>
          </Box>
          <Footer />
          
          {/* Real-time features from task 7.5 */}
          <Notifications position="top-right" maxVisible={3} />
          <WebSocketStatus className="fixed bottom-4 right-4 z-50 bg-white p-2 rounded-full shadow-md" />
        </Box>
      </ChatProvider>
    </ThemeProvider>
  );
};

export default App; 