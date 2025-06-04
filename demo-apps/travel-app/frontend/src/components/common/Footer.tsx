import React from 'react';
import Box from '@mui/material/Box';
import Typography from '@mui/material/Typography';
import Container from '@mui/material/Container';
import Link from '@mui/material/Link';

const Footer: React.FC = () => {
  return (
    <Box
      component="footer"
      sx={{
        py: 3,
        px: 2,
        mt: 'auto',
        backgroundColor: (theme) => theme.palette.primary.main,
        color: 'white',
      }}
    >
      <Container maxWidth="lg">
        <Typography variant="body2" color="white" align="center" fontWeight={300}>
          {'AWS Travel Planning Demo - Powered by '}
          <Link color="secondary" href="https://aws.amazon.com/bedrock/" underline="hover" sx={{ fontWeight: 400 }}>
            Amazon Bedrock
          </Link>{', '}
          <Link color="secondary" href="https://aws.amazon.com/rds/aurora/dsql/" underline="hover" sx={{ fontWeight: 400 }}>
            Amazon DSQL
          </Link>{', and '}
          <Link color="secondary" href="https://aws.amazon.com/blogs/opensource/introducing-strands-agents-an-open-source-ai-agents-sdk/" underline="hover" sx={{ fontWeight: 400 }}>
            AWS Strands Agents
          </Link>
          {' - '}
          {new Date().getFullYear()}
        </Typography>
        <Typography variant="body2" color="white" align="center" sx={{ mt: 1, opacity: 0.9, fontWeight: 300 }}>
          This demo showcases model-driven AI agent orchestration with serverless scalability.
        </Typography>
      </Container>
    </Box>
  );
};

export default Footer; 