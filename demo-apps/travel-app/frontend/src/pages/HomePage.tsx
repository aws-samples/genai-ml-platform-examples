import React from 'react';
import { Link as RouterLink } from 'react-router-dom';
import Container from '@mui/material/Container';
import Typography from '@mui/material/Typography';
import Box from '@mui/material/Box';
import Button from '@mui/material/Button';
import Grid from '@mui/material/Grid';
import Card from '@mui/material/Card';
import CardContent from '@mui/material/CardContent';
import CardActions from '@mui/material/CardActions';
import TravelExploreIcon from '@mui/icons-material/TravelExplore';
import PsychologyIcon from '@mui/icons-material/Psychology';
import SmartToyIcon from '@mui/icons-material/SmartToy';

const HomePage: React.FC = () => {
  return (
    <Container maxWidth="lg">
      <Box sx={{ my: 4, textAlign: 'center' }}>
        <Typography variant="h2" component="h1" gutterBottom>
          Travel Planning with AI Agents
        </Typography>
        <Typography variant="h5" component="h2" color="text.secondary" gutterBottom>
          Explore a next-generation travel planning experience powered by collaborative AI agents
        </Typography>
        <Box sx={{ mt: 4 }}>
          <Button
            variant="contained"
            size="large"
            component={RouterLink}
            to="/demo"
            sx={{ mr: 2 }}
          >
            Try the Demo
          </Button>
          <Button
            variant="outlined"
            size="large"
            component={RouterLink}
            to="/about"
          >
            Learn More
          </Button>
        </Box>
      </Box>

      <Grid container spacing={4} sx={{ mt: 4 }}>
        <Grid item xs={12} md={4}>
          <Card sx={{ height: '100%', display: 'flex', flexDirection: 'column' }}>
            <CardContent sx={{ flexGrow: 1, textAlign: 'center' }}>
              <PsychologyIcon color="primary" sx={{ fontSize: 60, mb: 2 }} />
              <Typography gutterBottom variant="h5" component="h3">
                Dynamic Brain
              </Typography>
              <Typography>
                The Planner Brain directs the planning process, using Amazon Bedrock to intelligently 
                determine the next best action at each step.
              </Typography>
            </CardContent>
            <CardActions sx={{ justifyContent: 'center' }}>
              <Button size="small">Learn More</Button>
            </CardActions>
          </Card>
        </Grid>
        
        <Grid item xs={12} md={4}>
          <Card sx={{ height: '100%', display: 'flex', flexDirection: 'column' }}>
            <CardContent sx={{ flexGrow: 1, textAlign: 'center' }}>
              <SmartToyIcon color="primary" sx={{ fontSize: 60, mb: 2 }} />
              <Typography gutterBottom variant="h5" component="h3">
                Specialist Agents
              </Typography>
              <Typography>
                A team of specialized agents work together on specific tasks like flight search, 
                hotel booking, and local activities recommendation.
              </Typography>
            </CardContent>
            <CardActions sx={{ justifyContent: 'center' }}>
              <Button size="small">Learn More</Button>
            </CardActions>
          </Card>
        </Grid>
        
        <Grid item xs={12} md={4}>
          <Card sx={{ height: '100%', display: 'flex', flexDirection: 'column' }}>
            <CardContent sx={{ flexGrow: 1, textAlign: 'center' }}>
              <TravelExploreIcon color="primary" sx={{ fontSize: 60, mb: 2 }} />
              <Typography gutterBottom variant="h5" component="h3">
                Intelligent Orchestration
              </Typography>
              <Typography>
                AWS Step Functions orchestrates the collaborative workflow, dynamically adapting to your 
                specific travel needs and preferences.
              </Typography>
            </CardContent>
            <CardActions sx={{ justifyContent: 'center' }}>
              <Button size="small">Learn More</Button>
            </CardActions>
          </Card>
        </Grid>
      </Grid>
    </Container>
  );
};

export default HomePage; 