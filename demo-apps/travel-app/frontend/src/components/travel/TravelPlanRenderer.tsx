import React from 'react';
import {
  Box,
  Paper,
  Typography,
  useTheme,
  Table,
  TableBody,
  TableCell,
  TableContainer,
  TableHead,
  TableRow,
  Card,
  CardContent,
  List,
  ListItem,
  ListItemIcon,
  ListItemText,
} from '@mui/material';
import {
  FlightTakeoff as FlightIcon,
  Hotel as HotelIcon,
  LocalActivity as ActivityIcon,
  AttachMoney as MoneyIcon,
  Schedule as ScheduleIcon,
  CheckCircle as CheckIcon,
} from '@mui/icons-material';

interface TravelPlanRendererProps {
  content: string;
  isActive?: boolean;
}

interface ParsedSection {
  type: 'header' | 'subheader' | 'text' | 'table' | 'list' | 'budget' | 'itinerary';
  level?: number;
  content: string;
  data?: any;
}

/**
 * TravelPlanRenderer component for displaying rich narrative travel plans
 * from the backend-strands multi-agent system
 */
const TravelPlanRenderer: React.FC<TravelPlanRendererProps> = ({
  content,
  isActive = false,
}) => {
  const theme = useTheme();

  // Parse the markdown-style content into structured sections
  const parseContent = (text: string): ParsedSection[] => {
    const lines = text.split('\n');
    const sections: ParsedSection[] = [];
    let currentSection: ParsedSection | null = null;
    let tableRows: string[] = [];
    let inTable = false;

    for (let i = 0; i < lines.length; i++) {
      const line = lines[i].trim();
      
      if (!line || line === '---') {
        // Empty line or separator - finalize current section if exists
        if (currentSection) {
          sections.push(currentSection);
          currentSection = null;
        }
        if (inTable && tableRows.length > 0) {
          sections.push({
            type: 'table',
            content: '',
            data: tableRows,
          });
          tableRows = [];
          inTable = false;
        }
        continue;
      }

      // Headers
      if (line.startsWith('# ')) {
        if (currentSection) sections.push(currentSection);
        currentSection = {
          type: 'header',
          level: 1,
          content: line.replace('# ', '').replace(/[🌟💰📅✈️🏨]/g, '').trim(),
        };
      } else if (line.startsWith('## ')) {
        if (currentSection) sections.push(currentSection);
        currentSection = {
          type: 'subheader',
          level: 2,
          content: line.replace('## ', '').replace(/[🔹]/g, '').trim(),
        };
      } else if (line.startsWith('### ')) {
        if (currentSection) sections.push(currentSection);
        currentSection = {
          type: 'subheader',
          level: 3,
          content: line.replace('### ', '').trim(),
        };
      }
      // Table detection
      else if (line.includes('|') && line.split('|').length > 2) {
        if (currentSection) {
          sections.push(currentSection);
          currentSection = null;
        }
        inTable = true;
        tableRows.push(line);
      }
      // List items
      else if (line.match(/^[*-]\s+/) || line.match(/^\d+\.\s+/)) {
        if (currentSection && currentSection.type !== 'list') {
          sections.push(currentSection);
          currentSection = { type: 'list', content: '' };
        } else if (!currentSection) {
          currentSection = { type: 'list', content: '' };
        }
        currentSection.content += line + '\n';
      }
      // Regular text
      else {
        if (inTable) {
          tableRows.push(line);
        } else {
          if (currentSection && currentSection.type !== 'text') {
            sections.push(currentSection);
            currentSection = { type: 'text', content: '' };
          } else if (!currentSection) {
            currentSection = { type: 'text', content: '' };
          }
          currentSection.content += line + '\n';
        }
      }
    }

    // Add final section
    if (currentSection) sections.push(currentSection);
    if (inTable && tableRows.length > 0) {
      sections.push({
        type: 'table',
        content: '',
        data: tableRows,
      });
    }

    return sections;
  };


  // Render table from parsed data
  const renderTable = (tableData: string[]) => {
    const rows = tableData.filter(row => row.trim() && !row.match(/^[|-\s]+$/));
    if (rows.length < 2) return null;

    const headers = rows[0].split('|').map(h => h.trim()).filter(h => h);
    const dataRows = rows.slice(1).map(row => 
      row.split('|').map(cell => cell.trim()).filter(cell => cell)
    );

    return (
      <TableContainer component={Paper} variant="outlined" sx={{ mb: 2 }}>
        <Table size="small">
          <TableHead>
            <TableRow>
              {headers.map((header, index) => (
                <TableCell key={index} sx={{ fontWeight: 'bold', bgcolor: 'primary.50' }}>
                  {header}
                </TableCell>
              ))}
            </TableRow>
          </TableHead>
          <TableBody>
            {dataRows.map((row, rowIndex) => (
              <TableRow key={rowIndex} hover>
                {row.map((cell, cellIndex) => (
                  <TableCell key={cellIndex}>
                    {cell}
                  </TableCell>
                ))}
              </TableRow>
            ))}
          </TableBody>
        </Table>
      </TableContainer>
    );
  };

  // Render list from parsed content
  const renderList = (content: string) => {
    const items = content.split('\n').filter(line => line.trim());
    
    return (
      <List dense>
        {items.map((item, index) => {
          const cleanItem = item.replace(/^[*-]\s+/, '').replace(/^\d+\.\s+/, '');
          const icon = cleanItem.toLowerCase().includes('flight') ? <FlightIcon /> :
                      cleanItem.toLowerCase().includes('hotel') ? <HotelIcon /> :
                      cleanItem.toLowerCase().includes('activity') ? <ActivityIcon /> :
                      <CheckIcon />;
          
          // Parse bold text with **text**
          const parseBoldText = (text: string) => {
            const parts = text.split(/(\*\*[^*]+\*\*)/g);
            return parts.map((part, i) => {
              if (part.startsWith('**') && part.endsWith('**')) {
                return <strong key={i} style={{ color: theme.palette.primary.main, fontWeight: 700 }}>{part.slice(2, -2)}</strong>;
              }
              return part;
            });
          };
          
          return (
            <ListItem key={index}>
              <ListItemIcon sx={{ color: 'primary.main', minWidth: 36 }}>
                {icon}
              </ListItemIcon>
              <ListItemText 
                primary={parseBoldText(cleanItem)}
                primaryTypographyProps={{ variant: 'body2' }}
              />
            </ListItem>
          );
        })}
      </List>
    );
  };

  // Determine section key from content
  const getSectionKey = (section: ParsedSection): string => {
    const content = section.content.toLowerCase();
    if (content.includes('budget') || content.includes('financial')) return 'budget';
    if (content.includes('itinerary') || content.includes('day')) return 'itinerary';
    if (content.includes('flight')) return 'flights';
    if (content.includes('hotel') || content.includes('accommodation')) return 'hotels';
    if (content.includes('activity') || content.includes('activities')) return 'activities';
    return 'overview';
  };

  // Render individual section
  const renderSection = (section: ParsedSection, index: number) => {
    const sectionKey = getSectionKey(section);

    switch (section.type) {
      case 'header':
        return (
          <Box key={index} sx={{ mb: 4 }}>
            <Typography 
              variant="h4" 
              component="h1" 
              gutterBottom
              sx={{ 
                color: 'primary.main',
                fontWeight: 'bold',
                borderBottom: `3px solid ${theme.palette.primary.main}`,
                pb: 2,
                mb: 3,
                display: 'flex',
                alignItems: 'center',
                gap: 2,
              }}
            >
              <FlightIcon sx={{ fontSize: 32 }} />
              {section.content}
            </Typography>
          </Box>
        );

      case 'subheader':
        // Choose icon based on section
        const getIcon = () => {
          if (sectionKey === 'flights') return <FlightIcon />;
          if (sectionKey === 'hotels') return <HotelIcon />;
          if (sectionKey === 'activities') return <ActivityIcon />;
          if (sectionKey === 'budget') return <MoneyIcon />;
          if (sectionKey === 'itinerary') return <ScheduleIcon />;
          return <CheckIcon />;
        };
        
        return (
          <Box key={index} sx={{ mb: 3 }}>
            <Paper 
              sx={{ 
                display: 'flex', 
                alignItems: 'center', 
                borderRadius: 2,
                p: 2,
                bgcolor: theme.palette.mode === 'dark' ? 'grey.900' : 'grey.50',
              }}
              elevation={1}
            >
              <Box sx={{ 
                mr: 2, 
                color: 'primary.main',
                display: 'flex',
                alignItems: 'center',
              }}>
                {getIcon()}
              </Box>
              <Typography 
                variant={section.level === 2 ? "h5" : "h6"} 
                component={section.level === 2 ? "h2" : "h3"}
                sx={{ 
                  color: 'text.primary',
                  fontWeight: 600,
                  flex: 1,
                }}
              >
                {section.content}
              </Typography>
            </Paper>
          </Box>
        );

      case 'table':
        return (
          <Box key={index} sx={{ mb: 2, pl: 2 }}>
            {renderTable(section.data)}
          </Box>
        );

      case 'list':
        return (
          <Box key={index} sx={{ mb: 2, pl: 2 }}>
            {renderList(section.content)}
          </Box>
        );

      case 'text':
        return (
          <Box key={index} sx={{ mb: 2, pl: 2 }}>
            <Typography 
              variant="body1" 
              paragraph
              sx={{ 
                lineHeight: 1.8,
                color: 'text.secondary',
                '& strong': { 
                  fontWeight: 'bold',
                  color: 'text.primary' 
                },
              }}
            >
              {section.content.split('\n').map((line, lineIndex) => {
                // Parse bold text with **text**
                const parts = line.split(/(\*\*[^*]+\*\*)/g);
                return (
                  <span key={lineIndex}>
                    {parts.map((part, partIndex) => {
                      if (part.startsWith('**') && part.endsWith('**')) {
                        return (
                          <strong 
                            key={partIndex} 
                            style={{ 
                              color: theme.palette.primary.main, 
                              fontWeight: 700,
                              fontSize: '1.05em'
                            }}
                          >
                            {part.slice(2, -2)}
                          </strong>
                        );
                      }
                      return part;
                    })}
                    {lineIndex < section.content.split('\n').length - 1 && <br />}
                  </span>
                );
              })}
            </Typography>
          </Box>
        );

      default:
        return null;
    }
  };

  const sections = parseContent(content);

  return (
    <Card 
      elevation={isActive ? 4 : 1}
      sx={{ 
        maxWidth: '100%',
        transform: isActive ? 'scale(1.01)' : 'scale(1)',
        transition: 'all 0.3s ease-in-out',
        borderRadius: 3,
        bgcolor: theme.palette.background.paper,
        boxShadow: theme.shadows[2],
      }}
    >
      <CardContent sx={{ p: { xs: 2, sm: 3, md: 4 } }}>

        {/* Quick stats chips - removed hardcoded values */}

        {/* Rendered content */}
        <Box>
          {sections.map((section, index) => renderSection(section, index))}
        </Box>
      </CardContent>
    </Card>
  );
};

export default TravelPlanRenderer;