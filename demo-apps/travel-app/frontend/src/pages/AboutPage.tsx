import React from 'react';
import Container from '@mui/material/Container';
import Typography from '@mui/material/Typography';
import Box from '@mui/material/Box';
import Paper from '@mui/material/Paper';
import Divider from '@mui/material/Divider';
import List from '@mui/material/List';
import ListItem from '@mui/material/ListItem';
import ListItemIcon from '@mui/material/ListItemIcon';
import ListItemText from '@mui/material/ListItemText';
import Grid from '@mui/material/Grid';
import Card from '@mui/material/Card';
import CardContent from '@mui/material/CardContent';
import BedrockIcon from '@mui/icons-material/Cloud';
import LambdaIcon from '@mui/icons-material/Code';
import StrandsIcon from '@mui/icons-material/AccountTree';
import ApiGatewayIcon from '@mui/icons-material/Api';
import DynamoDBIcon from '@mui/icons-material/Storage';
import PsychologyIcon from '@mui/icons-material/Psychology';
import SmartToyIcon from '@mui/icons-material/SmartToy';
import CheckCircleIcon from '@mui/icons-material/CheckCircle';

const AboutPage: React.FC = () => {
  return (
    <Container maxWidth="lg">
      <Box sx={{ my: 4 }}>
        <Typography variant="h3" component="h1" gutterBottom>
          About This Demo
        </Typography>
        <Typography variant="body1" paragraph>
          This AWS Travel Planning Demo showcases a multi-agent system that collaboratively plans travel itineraries.
          Built on AWS services, it demonstrates how multiple specialized AI agents can work together using
          AWS Strands Agents SDK for orchestration, Amazon DSQL for serverless data management, and AWS KnowledgeBases
          for intelligent information retrieval, creating a flexible and powerful travel planning experience.
        </Typography>

        <Paper sx={{ p: 3, mb: 4 }}>
          <Typography variant="h5" component="h2" gutterBottom>
            Architecture Overview
          </Typography>
          <Divider sx={{ mb: 2 }} />
          <Grid container spacing={3}>
            <Grid item xs={12} md={6}>
              <List>
                <ListItem>
                  <ListItemIcon>
                    <PsychologyIcon color="primary" />
                  </ListItemIcon>
                  <ListItemText 
                    primary="Planner Brain" 
                    secondary="Central orchestrator that uses Amazon Bedrock to determine the next best action"
                  />
                </ListItem>
                <ListItem>
                  <ListItemIcon>
                    <SmartToyIcon color="primary" />
                  </ListItemIcon>
                  <ListItemText 
                    primary="Specialist Agents" 
                    secondary="Focused Lambda functions that perform specific travel tasks"
                  />
                </ListItem>
                <ListItem>
                  <ListItemIcon>
                    <StrandsIcon color="primary" />
                  </ListItemIcon>
                  <ListItemText 
                    primary="Strands Agents Orchestration" 
                    secondary="AWS Strands Agents SDK provides model-driven orchestration with minimal code"
                  />
                </ListItem>
              </List>
            </Grid>
            <Grid item xs={12} md={6}>
              <List>
                <ListItem>
                  <ListItemIcon>
                    <ApiGatewayIcon color="primary" />
                  </ListItemIcon>
                  <ListItemText 
                    primary="API Gateway" 
                    secondary="Provides REST endpoints for frontend interaction"
                  />
                </ListItem>
                <ListItem>
                  <ListItemIcon>
                    <DynamoDBIcon color="primary" />
                  </ListItemIcon>
                  <ListItemText 
                    primary="Amazon DSQL" 
                    secondary="Serverless distributed SQL database with virtually unlimited scale and 99.999% availability"
                  />
                </ListItem>
                <ListItem>
                  <ListItemIcon>
                    <BedrockIcon color="primary" />
                  </ListItemIcon>
                  <ListItemText 
                    primary="Amazon Bedrock & KnowledgeBases" 
                    secondary="Powers AI models with natural language understanding and retrieval-augmented generation"
                  />
                </ListItem>
              </List>
            </Grid>
          </Grid>
        </Paper>

        <Paper sx={{ p: 3, mb: 4 }}>
          <Typography variant="h5" component="h2" gutterBottom>
            Powered by Modern AWS Technologies
          </Typography>
          <Divider sx={{ mb: 2 }} />
          <Grid container spacing={3}>
            <Grid item xs={12} md={6}>
              <Typography variant="h6" gutterBottom color="primary">
                AWS Strands Agents
              </Typography>
              <Typography variant="body2" paragraph>
                An open-source SDK that revolutionizes AI agent development with a model-driven approach. 
                Instead of complex orchestration logic, Strands leverages the native reasoning capabilities 
                of modern LLMs, connecting models and tools with minimal code. This enables rapid development 
                of sophisticated multi-agent systems that can dynamically collaborate and adapt to user needs.
              </Typography>
            </Grid>
            <Grid item xs={12} md={6}>
              <Typography variant="h6" gutterBottom color="primary">
                Amazon Aurora DSQL
              </Typography>
              <Typography variant="body2" paragraph>
                The fastest serverless distributed SQL database offering virtually unlimited scale with 
                99.999% multi-Region availability. DSQL's PostgreSQL-compatible interface and automatic 
                scaling make it ideal for our travel planning workloads, handling everything from user 
                preferences to complex itinerary data without any infrastructure management.
              </Typography>
            </Grid>
          </Grid>
        </Paper>

        <Typography variant="h5" component="h2" gutterBottom>
          Key Concepts Demonstrated
        </Typography>
        <Grid container spacing={3} sx={{ mb: 4 }}>
          <Grid item xs={12} md={4}>
            <Card sx={{ height: '100%' }}>
              <CardContent>
                <Typography variant="h6" component="h3" gutterBottom>
                  Model-Driven Orchestration
                </Typography>
                <Typography variant="body2" color="text.secondary">
                  Using AWS Strands Agents, the system relies on LLM reasoning to dynamically orchestrate 
                  agents based on context and goals, eliminating the need for complex workflow definitions.
                </Typography>
                <List dense>
                  <ListItem>
                    <ListItemIcon>
                      <CheckCircleIcon color="success" fontSize="small" />
                    </ListItemIcon>
                    <ListItemText primary="Adaptive to user needs" />
                  </ListItem>
                  <ListItem>
                    <ListItemIcon>
                      <CheckCircleIcon color="success" fontSize="small" />
                    </ListItemIcon>
                    <ListItemText primary="Flexible decision paths" />
                  </ListItem>
                </List>
              </CardContent>
            </Card>
          </Grid>
          
          <Grid item xs={12} md={4}>
            <Card sx={{ height: '100%' }}>
              <CardContent>
                <Typography variant="h6" component="h3" gutterBottom>
                  Specialist AI Agents
                </Typography>
                <Typography variant="body2" color="text.secondary">
                  Each agent focuses on a specific domain of expertise, allowing for modular development
                  and optimization of individual capabilities.
                </Typography>
                <List dense>
                  <ListItem>
                    <ListItemIcon>
                      <CheckCircleIcon color="success" fontSize="small" />
                    </ListItemIcon>
                    <ListItemText primary="Expert-level capabilities" />
                  </ListItem>
                  <ListItem>
                    <ListItemIcon>
                      <CheckCircleIcon color="success" fontSize="small" />
                    </ListItemIcon>
                    <ListItemText primary="Modular architecture" />
                  </ListItem>
                </List>
              </CardContent>
            </Card>
          </Grid>
          
          <Grid item xs={12} md={4}>
            <Card sx={{ height: '100%' }}>
              <CardContent>
                <Typography variant="h6" component="h3" gutterBottom>
                  Serverless Implementation
                </Typography>
                <Typography variant="body2" color="text.secondary">
                  The entire system is built on serverless components, enabling cost efficiency
                  and automatic scaling based on usage.
                </Typography>
                <List dense>
                  <ListItem>
                    <ListItemIcon>
                      <CheckCircleIcon color="success" fontSize="small" />
                    </ListItemIcon>
                    <ListItemText primary="Cost-effective" />
                  </ListItem>
                  <ListItem>
                    <ListItemIcon>
                      <CheckCircleIcon color="success" fontSize="small" />
                    </ListItemIcon>
                    <ListItemText primary="Highly scalable" />
                  </ListItem>
                </List>
              </CardContent>
            </Card>
          </Grid>
        </Grid>
      </Box>
    </Container>
  );
};

export default AboutPage; 