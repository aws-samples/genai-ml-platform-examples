import { createTheme } from '@mui/material/styles';

// Create a custom theme for the travel planning application with AWS branding
const theme = createTheme({
  palette: {
    primary: {
      main: '#252F3E', // AWS Navy Blue
      light: '#475675',
      dark: '#1A212C',
      contrastText: '#ffffff',
    },
    secondary: {
      main: '#FF9900', // AWS Orange
      light: '#FFAC31',
      dark: '#E68A00',
      contrastText: '#000000',
    },
    background: {
      default: '#fafafa',
      paper: '#ffffff',
    },
    error: {
      main: '#D13212', // AWS-style red
    },
    warning: {
      main: '#FF9900', // Same as secondary for consistency
    },
    info: {
      main: '#1E88E5', // AWS-compatible blue
    },
    success: {
      main: '#2E7D32', // AWS-compatible green
    },
  },
  typography: {
    fontFamily: [
      'Amazon Ember',
      'Roboto',
      '-apple-system',
      'BlinkMacSystemFont',
      '"Segoe UI"',
      '"Helvetica Neue"',
      'Arial',
      'sans-serif',
    ].join(','),
    h1: {
      fontSize: '2.5rem',
      fontWeight: 300, // Amazon Ember Display Light for headings
    },
    h2: {
      fontSize: '2rem',
      fontWeight: 300,
    },
    h3: {
      fontSize: '1.75rem',
      fontWeight: 300,
    },
    h4: {
      fontSize: '1.5rem',
      fontWeight: 300,
    },
    h5: {
      fontSize: '1.25rem',
      fontWeight: 500, // Medium weight for smaller headings
    },
    h6: {
      fontSize: '1rem',
      fontWeight: 500,
    },
  },
  shape: {
    borderRadius: 2, // AWS tends to use more squared corners
  },
  components: {
    MuiButton: {
      styleOverrides: {
        root: {
          textTransform: 'none',
          borderRadius: 2,
          padding: '8px 16px',
          fontWeight: 500,
        },
        contained: {
          boxShadow: 'none',
          '&:hover': {
            boxShadow: '0px 1px 3px rgba(0, 0, 0, 0.2)',
          },
        },
        containedPrimary: {
          backgroundColor: '#252F3E', // AWS Navy Blue
          '&:hover': {
            backgroundColor: '#1A212C', // Darker shade
          },
        },
        containedSecondary: {
          backgroundColor: '#FF9900', // AWS Orange
          color: '#000000', // Black text on orange background
          '&:hover': {
            backgroundColor: '#E68A00', // Darker shade
          },
        },
        outlined: {
          borderWidth: '1px',
          '&:hover': {
            borderWidth: '1px',
          },
        },
        outlinedPrimary: {
          borderColor: '#252F3E',
          '&:hover': {
            backgroundColor: 'rgba(37, 47, 62, 0.04)',
          },
        },
        outlinedSecondary: {
          borderColor: '#FF9900',
          color: '#000000',
          '&:hover': {
            backgroundColor: 'rgba(255, 153, 0, 0.04)',
            borderColor: '#E68A00',
          },
        },
      },
    },
    MuiCard: {
      styleOverrides: {
        root: {
          borderRadius: 2,
          boxShadow: '0px 1px 3px rgba(0, 0, 0, 0.1)',
          border: '1px solid #E5E5E5',
        },
      },
    },
    MuiAppBar: {
      styleOverrides: {
        root: {
          boxShadow: '0px 1px 3px rgba(0, 0, 0, 0.1)',
          backgroundColor: '#252F3E', // AWS Navy Blue
        },
      },
    },
    MuiChip: {
      styleOverrides: {
        root: {
          borderRadius: 2,
        },
      },
    },
    MuiPaper: {
      styleOverrides: {
        root: {
          borderRadius: 2,
        },
      },
    },
  },
});

export default theme; 