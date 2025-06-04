import { TravelPlan, TravelPlanStatus, BookingStatus } from '../../models/TravelPlan';

/**
 * Sample travel plans for demo purposes
 * These can be used when real backend data is not available
 */
export const sampleTravelPlans: TravelPlan[] = [
  {
    planId: 'sample-plan-1',
    title: 'Amazing Japan Adventure',
    description: 'Discover the unique blend of ancient traditions and cutting-edge modernity in Japan. From Tokyo\'s neon-lit skyscrapers to Kyoto\'s serene temples, experience Japan\'s fascinating contrasts while enjoying world-class cuisine and legendary hospitality.',
    startDate: '2025-06-05',
    endDate: '2025-06-15',
    destination: {
      name: 'Japan',
      country: 'Japan',
      city: 'Tokyo',
      coordinates: {
        latitude: 35.6762,
        longitude: 139.6503
      }
    },
    budget: {
      total: 3500,
      currency: 'USD',
      breakdown: {
        'Flights': 1200,
        'Accommodations': 1100,
        'Activities': 600,
        'Food': 400,
        'Transportation': 200
      }
    },
    flights: [
      {
        bookingReference: 'NH123456',
        airline: 'ANA',
        flightNumber: 'NH7842',
        departure: {
          airport: 'SFO',
          terminal: '2',
          date: '2025-06-05',
          time: '11:40'
        },
        arrival: {
          airport: 'HND',
          terminal: '3',
          date: '2025-06-06',
          time: '14:30'
        },
        price: {
          amount: 750,
          currency: 'USD'
        },
        status: BookingStatus.CONFIRMED
      },
      {
        bookingReference: 'NH654321',
        airline: 'Japan Airlines',
        flightNumber: 'JL7015',
        departure: {
          airport: 'HND',
          terminal: '3',
          date: '2025-06-15',
          time: '16:05'
        },
        arrival: {
          airport: 'SFO',
          terminal: '2',
          date: '2025-06-15',
          time: '10:15'
        },
        price: {
          amount: 780,
          currency: 'USD'
        },
        status: BookingStatus.CONFIRMED
      }
    ],
    accommodations: [
      {
        bookingReference: 'HT78901',
        name: 'Cerulean Tower Tokyu Hotel',
        type: 'Luxury Hotel',
        address: '26-1 Sakuragaokacho, Shibuya City, Tokyo 150-8512, Japan',
        checkIn: {
          date: '2025-06-06',
          time: '15:00'
        },
        checkOut: {
          date: '2025-06-10',
          time: '11:00'
        },
        price: {
          amount: 1200,
          currency: 'USD',
          isTotal: true
        },
        status: BookingStatus.CONFIRMED
      },
      {
        bookingReference: 'HT12345',
        name: 'The Ritz-Carlton Kyoto',
        type: 'Luxury Hotel',
        address: 'Kamogawa Nijo-Ohashi Hotori, Nakagyo-ku, Kyoto, 604-0902, Japan',
        checkIn: {
          date: '2025-06-10',
          time: '15:00'
        },
        checkOut: {
          date: '2025-06-15',
          time: '11:00'
        },
        price: {
          amount: 1800,
          currency: 'USD',
          isTotal: true
        },
        status: BookingStatus.CONFIRMED
      }
    ],
    activities: [
      {
        id: 'act-123',
        name: 'Tokyo Tower & Skytree Tour',
        description: 'See Tokyo from above with visits to two of the city\'s most iconic towers. Compare the views and learn about the history of these architectural marvels.',
        date: "2025-06-07",
        startTime: '09:00',
        endTime: '14:00',
        location: 'Tokyo Tower & Tokyo Skytree',
        price: {
          amount: 85,
          currency: 'USD'
        },
        bookingReference: 'TK123456',
        status: BookingStatus.CONFIRMED
      },
      {
        id: 'act-124',
        name: 'Tsukiji Outer Market Food Tour',
        description: 'Sample the finest and freshest Japanese cuisine as you explore the famous outer market at Tsukiji. Your local guide will introduce you to hidden gems and explain the cultural significance of each dish.',
        date: "2025-06-07",
        startTime: '15:30',
        endTime: '18:30',
        location: 'Tsukiji Outer Market, Chuo City',
        price: {
          amount: 120,
          currency: 'USD'
        },
        bookingReference: 'FD456789',
        status: BookingStatus.CONFIRMED
      },
      {
        id: 'act-125',
        name: 'Meiji Shrine & Harajuku Walking Tour',
        description: 'Contrast the serene spirituality of Meiji Shrine with the vibrant youth culture of Harajuku. This tour showcases the fascinating contrasts that make Tokyo so unique.',
        date: "2025-06-08",
        startTime: '09:30',
        endTime: '13:30',
        location: 'Meiji Shrine, Shibuya',
        price: {
          amount: 65,
          currency: 'USD'
        },
        bookingReference: 'TK234567',
        status: BookingStatus.CONFIRMED
      },
      {
        id: 'act-126',
        name: 'Teamlab Borderless Digital Art Museum',
        description: 'Experience art like never before at this groundbreaking digital art museum where the exhibits move, respond to touch, and create an immersive wonderland.',
        date: "2025-06-08",
        startTime: '16:00',
        endTime: '19:00',
        location: 'Palette Town, Odaiba',
        price: {
          amount: 35,
          currency: 'USD'
        },
        bookingReference: 'TL345678',
        status: BookingStatus.CONFIRMED
      },
      {
        id: 'act-127',
        name: 'Mt. Fuji & Hakone Day Trip',
        description: 'Escape the city for a day trip to see Japan\'s most iconic mountain and the beautiful hot spring region of Hakone. Includes a lake cruise and cable car ride for spectacular views.',
        date: '2025-06-09',
        startTime: '08:00',
        endTime: '20:00',
        location: 'Mt. Fuji & Hakone',
        price: {
          amount: 145,
          currency: 'USD'
        },
        bookingReference: 'MF456789',
        status: BookingStatus.CONFIRMED
      },
      {
        id: 'act-128',
        name: 'Robot Restaurant Show',
        description: 'Experience the famous Robot Restaurant, an only-in-Japan spectacle combining robots, dancers, lasers, and music in a high-energy performance that defies description.',
        date: '2025-06-09',
        startTime: '21:30',
        endTime: '23:00',
        location: 'Shinjuku, Tokyo',
        price: {
          amount: 80,
          currency: 'USD'
        },
        bookingReference: 'RR567890',
        status: BookingStatus.CONFIRMED
      },
      {
        id: 'act-129',
        name: 'Fushimi Inari Shrine Morning Tour',
        description: 'Beat the crowds with an early morning visit to Kyoto\'s most photogenic shrine, famous for its thousands of vermilion torii gates winding up the mountainside.',
        date: '2025-06-11',
        startTime: '07:30',
        endTime: '10:30',
        location: 'Fushimi Inari Shrine, Kyoto',
        price: {
          amount: 55,
          currency: 'USD'
        },
        bookingReference: 'KY123456',
        status: BookingStatus.CONFIRMED
      },
      {
        id: 'act-130',
        name: 'Arashiyama Bamboo Grove & Temples',
        description: 'Explore the enchanting bamboo forest of Arashiyama and visit the beautiful temples and gardens in this scenic area of western Kyoto.',
        date: '2025-06-11',
        startTime: '13:00',
        endTime: '17:00',
        location: 'Arashiyama, Kyoto',
        price: {
          amount: 75,
          currency: 'USD'
        },
        bookingReference: 'KY234567',
        status: BookingStatus.CONFIRMED
      },
      {
        id: 'act-131',
        name: 'Traditional Tea Ceremony Experience',
        description: 'Learn about the ancient art of the Japanese tea ceremony from a tea master in an authentic setting. This hands-on experience includes matcha preparation and traditional sweets.',
        date: '2025-06-12',
        startTime: '10:00',
        endTime: '12:00',
        location: 'Camellia Tea Ceremony, Kyoto',
        price: {
          amount: 60,
          currency: 'USD'
        },
        bookingReference: 'TC345678',
        status: BookingStatus.CONFIRMED
      },
      {
        id: 'act-132',
        name: 'Gion Evening Walking Tour',
        description: 'Stroll through Kyoto\'s famous geisha district at dusk, when lanterns illuminate the traditional wooden buildings and you might glimpse geiko and maiko on their way to appointments.',
        date: '2025-06-12',
        startTime: '18:00',
        endTime: '20:30',
        location: 'Gion District, Kyoto',
        price: {
          amount: 85,
          currency: 'USD'
        },
        bookingReference: 'KY456789',
        status: BookingStatus.CONFIRMED
      },
      {
        id: 'act-133',
        name: 'Nara Day Trip & Deer Park Visit',
        description: 'Visit Japan\'s first capital city, home to impressive temples, the Great Buddha, and friendly sacred deer that bow for cookies.',
        date: '2025-06-13',
        startTime: '09:00',
        endTime: '17:00',
        location: 'Nara',
        price: {
          amount: 110,
          currency: 'USD'
        },
        bookingReference: 'KY567890',
        status: BookingStatus.CONFIRMED
      },
      {
        id: 'act-134',
        name: 'Kinkaku-ji (Golden Pavilion) & Ryoan-ji',
        description: 'Visit two of Kyoto\'s most famous Zen temples: the dazzling gold-leaf covered Golden Pavilion and Ryoan-ji with its enigmatic rock garden.',
        date: '2025-06-14',
        startTime: '09:30',
        endTime: '13:30',
        location: 'Northern Kyoto',
        price: {
          amount: 70,
          currency: 'USD'
        },
        bookingReference: 'KY678901',
        status: BookingStatus.CONFIRMED
      },
      {
        id: 'act-135',
        name: 'Kaiseki Dinner Experience',
        description: 'Enjoy an exquisite multi-course traditional Japanese dinner, showcasing seasonal ingredients prepared with meticulous attention to taste, texture, appearance, and colors.',
        date: '2025-06-14',
        startTime: '19:00',
        endTime: '21:30',
        location: 'Gion Karyo, Kyoto',
        price: {
          amount: 150,
          currency: 'USD'
        },
        bookingReference: 'KD789012',
        status: BookingStatus.CONFIRMED
      }
    ],
    status: TravelPlanStatus.CONFIRMED,
    createdAt: '2023-08-15T14:22:31Z',
    updatedAt: '2023-08-22T16:44:12Z'
  },
  {
    planId: 'sample-plan-2',
    title: 'Parisian Romance Getaway',
    description: 'Experience the magic of the City of Light with this romantic Paris getaway. Stroll along the Seine, savor exquisite French cuisine, and immerse yourself in world-class art and culture. The perfect blend of iconic landmarks and hidden gems awaits.',
    startDate: '2025-06-05',
    endDate: '2025-06-12',
    destination: {
      name: 'Paris',
      country: 'France',
      city: 'Paris',
      coordinates: {
        latitude: 48.8566,
        longitude: 2.3522
      }
    },
    budget: {
      total: 2800,
      currency: 'USD',
      breakdown: {
        'Flights': 900,
        'Accommodations': 1000,
        'Activities': 400,
        'Food': 400,
        'Transportation': 100
      }
    },
    flights: [
      {
        bookingReference: 'AF123456',
        airline: 'Air France',
        flightNumber: 'AF83',
        departure: {
          airport: 'JFK',
          terminal: '1',
          date: '2025-06-05',
          time: '18:30'
        },
        arrival: {
          airport: 'CDG',
          terminal: '2E',
          date: '2025-06-06',
          time: '08:00'
        },
        price: {
          amount: 450,
          currency: 'USD'
        },
        status: BookingStatus.CONFIRMED
      },
      {
        bookingReference: 'AF654321',
        airline: 'Air France',
        flightNumber: 'AF22',
        departure: {
          airport: 'CDG',
          terminal: '2E',
          date: '2025-06-12',
          time: '10:15'
        },
        arrival: {
          airport: 'JFK',
          terminal: '1',
          date: '2025-06-12',
          time: '12:40'
        },
        price: {
          amount: 480,
          currency: 'USD'
        },
        status: BookingStatus.CONFIRMED
      }
    ],
    accommodations: [
      {
        bookingReference: 'HTL123',
        name: 'Hôtel Le Relais Montmartre',
        type: 'Boutique Hotel',
        address: '6 Rue Constance, 75018 Paris, France',
        checkIn: {
          date: '2025-06-06',
          time: '15:00'
        },
        checkOut: {
          date: '2025-06-12',
          time: '11:00'
        },
        price: {
          amount: 1180,
          currency: 'USD',
          isTotal: true
        },
        status: BookingStatus.CONFIRMED
      }
    ],
    activities: [
      {
        id: 'act-201',
        name: 'Seine River Dinner Cruise',
        description: 'Enjoy a magical evening cruising down the Seine while savoring a gourmet 3-course French dinner. Take in the illuminated landmarks as you float past the Eiffel Tower, Notre-Dame, and more.',
        date: '2025-06-06',
        startTime: '19:30',
        endTime: '22:00',
        location: 'Port de la Conférence, Paris',
        price: {
          amount: 95,
          currency: 'USD'
        },
        bookingReference: 'SC123456',
        status: BookingStatus.CONFIRMED
      },
      {
        id: 'act-202',
        name: 'Skip-the-Line Louvre Museum Tour',
        description: 'Bypass the notoriously long lines and discover the world\'s largest art museum with an expert guide. See masterpieces including the Mona Lisa, Venus de Milo, and Winged Victory.',
        date: '2025-06-07',
        startTime: '09:30',
        endTime: '12:30',
        location: 'Louvre Museum, Paris',
        price: {
          amount: 65,
          currency: 'USD'
        },
        bookingReference: 'LV234567',
        status: BookingStatus.CONFIRMED
      },
      {
        id: 'act-203',
        name: 'Montmartre Walking Tour & Sacré-Cœur',
        description: 'Explore the artistic heart of Paris in the charming hilltop village of Montmartre. Visit the stunning Sacré-Cœur Basilica, see the artists at Place du Tertre, and discover hidden windmills and vineyards.',
        date: '2025-06-07',
        startTime: '14:30',
        endTime: '17:00',
        location: 'Montmartre, Paris',
        price: {
          amount: 45,
          currency: 'USD'
        },
        bookingReference: 'MM345678',
        status: BookingStatus.CONFIRMED
      },
      {
        id: 'act-204',
        name: 'Eiffel Tower Summit Access',
        description: 'Skip the lines and ascend to the summit of the iconic Eiffel Tower for breathtaking 360-degree views of Paris. Learn about the tower\'s fascinating history and construction.',
        date: '2025-06-08',
        startTime: '11:00',
        endTime: '13:30',
        location: 'Eiffel Tower, Paris',
        price: {
          amount: 75,
          currency: 'USD'
        },
        bookingReference: 'ET456789',
        status: BookingStatus.CONFIRMED
      },
      {
        id: 'act-205',
        name: 'Cooking Class: French Pastry Secrets',
        description: 'Learn to make perfect croissants, éclairs, and macarons from a professional French pastry chef in this hands-on cooking class. Take home recipes and the treats you make.',
        date: '2025-06-08',
        startTime: '15:00',
        endTime: '18:00',
        location: 'Le Foodist, Paris',
        price: {
          amount: 110,
          currency: 'USD'
        },
        bookingReference: 'CC567890',
        status: BookingStatus.CONFIRMED
      },
      {
        id: 'act-206',
        name: 'Versailles Palace & Gardens Day Trip',
        description: 'Visit the opulent UNESCO-listed Palace of Versailles with skip-the-line access. Explore the stunning State Apartments, Hall of Mirrors, and perfectly manicured gardens with musical fountains.',
        date: '2025-06-09',
        startTime: '08:30',
        endTime: '16:30',
        location: 'Palace of Versailles',
        price: {
          amount: 95,
          currency: 'USD'
        },
        bookingReference: 'VS678901',
        status: BookingStatus.CONFIRMED
      },
      {
        id: 'act-207',
        name: 'Paris Food & Wine Tasting Tour',
        description: 'Sample the finest French delicacies on this guided walking tour through Saint-Germain-des-Prés. Taste artisanal cheeses, freshly baked breads, chocolates, and wine from different regions.',
        date: '2025-06-10',
        startTime: '10:30',
        endTime: '13:30',
        location: 'Saint-Germain-des-Prés, Paris',
        price: {
          amount: 95,
          currency: 'USD'
        },
        bookingReference: 'FT789012',
        status: BookingStatus.CONFIRMED
      },
      {
        id: 'act-208',
        name: 'Musée d\'Orsay Impressionist Collection',
        description: 'Explore the world\'s largest collection of Impressionist masterpieces housed in the beautiful former Orsay railway station. See works by Monet, Renoir, Van Gogh, Degas, and more.',
        date: '2025-06-10',
        startTime: '14:30',
        endTime: '17:00',
        location: 'Musée d\'Orsay, Paris',
        price: {
          amount: 55,
          currency: 'USD'
        },
        bookingReference: 'MO890123',
        status: BookingStatus.CONFIRMED
      },
      {
        id: 'act-209',
        name: 'Le Marais Hidden Gems Tour',
        description: 'Discover one of Paris\'s most historic and trendy neighborhoods with a local guide. Explore medieval architecture, visit hidden courtyards, browse unique boutiques, and sample local delicacies.',
        date: '2025-06-11',
        startTime: '10:00',
        endTime: '13:00',
        location: 'Le Marais, Paris',
        price: {
          amount: 50,
          currency: 'USD'
        },
        bookingReference: 'LM901234',
        status: BookingStatus.CONFIRMED
      },
      {
        id: 'act-210',
        name: 'Paris Opera House After-Hours Tour',
        description: 'Enjoy an exclusive after-hours tour of the magnificent Palais Garnier, one of the world\'s most famous opera houses. Learn about its architecture, the Phantom of the Opera legend, and see the spectacular Grand Staircase and auditorium.',
        date: '2025-06-11',
        startTime: '18:30',
        endTime: '20:30',
        location: 'Palais Garnier, Paris',
        price: {
          amount: 70,
          currency: 'USD'
        },
        bookingReference: 'PG012345',
        status: BookingStatus.CONFIRMED
      }
    ],
    status: TravelPlanStatus.CONFIRMED,
    createdAt: '2023-07-20T10:15:42Z',
    updatedAt: '2023-07-29T11:33:05Z'
  }
];

/**
 * Get a sample travel plan by ID
 * @param planId The ID of the plan to retrieve
 * @returns The requested travel plan or undefined if not found
 */
export const getSampleTravelPlan = (planId: string): TravelPlan | undefined => {
  return sampleTravelPlans.find(plan => plan.planId === planId);
};

/**
 * Generate a simulated agent output for demo purposes
 * @param agentType The type of agent to generate output for
 * @param destination The destination to generate output for
 * @returns An object representing the agent's output
 */
export const generateAgentOutput = (agentType: string, destination: string): any => {
  // Find a sample plan with a matching destination
  const matchingPlan = sampleTravelPlans.find(
    plan => plan.destination.name.toLowerCase().includes(destination.toLowerCase()) ||
            plan.destination.country.toLowerCase().includes(destination.toLowerCase())
  );
  
  if (!matchingPlan) {
    return { error: 'No sample data available for this destination' };
  }
  
  // Return different data based on agent type
  switch (agentType) {
    case 'flight':
      return matchingPlan.flights || [];
    case 'hotel':
      return matchingPlan.accommodations || [];
    case 'attraction':
    case 'dining':
      // Filter activities based on type
      if (!matchingPlan.activities) {
        return [];
      }
      
      if (agentType === 'dining') {
        return matchingPlan.activities.filter(a => 
          a.name.toLowerCase().includes('food') || 
          a.name.toLowerCase().includes('dining') ||
          a.name.toLowerCase().includes('restaurant') ||
          a.name.toLowerCase().includes('cuisine') ||
          a.name.toLowerCase().includes('culinary')
        );
      } else {
        return matchingPlan.activities.filter(a => 
          !a.name.toLowerCase().includes('food') && 
          !a.name.toLowerCase().includes('dining') &&
          !a.name.toLowerCase().includes('restaurant')
        );
      }
    case 'transportation':
      return {
        localOptions: [
          {
            type: 'Public Transit',
            details: 'Extensive metro and bus system covering entire city',
            costPerDay: 12,
            currency: 'USD',
            recommended: true,
            notes: 'Purchase a multi-day transit pass for best value'
          },
          {
            type: 'Taxi/Rideshare',
            details: 'Uber, Lyft and local taxis readily available',
            costPerTrip: {
              min: 10,
              avg: 18,
              max: 35
            },
            currency: 'USD'
          },
          {
            type: 'Rental Car',
            details: 'Not recommended for city center travel',
            costPerDay: 65,
            currency: 'USD',
            notes: 'Parking is limited and expensive in the city center'
          },
          {
            type: 'Walking',
            details: 'Many attractions within walking distance',
            recommended: true,
            notes: 'Most scenic way to experience the city'
          }
        ],
        airportTransfers: {
          options: [
            {
              type: 'Airport Express Train',
              duration: '30 min',
              cost: 22,
              currency: 'USD',
              frequency: 'Every 15 minutes',
              recommended: true
            },
            {
              type: 'Shuttle Bus',
              duration: '45-60 min',
              cost: 18,
              currency: 'USD',
              frequency: 'Every 30 minutes'
            },
            {
              type: 'Taxi',
              duration: '35-60 min',
              cost: 65,
              currency: 'USD',
              notes: 'Subject to traffic conditions'
            }
          ]
        }
      };
    case 'weather':
      // Generate sample weather data for the travel dates
      const startDate = new Date(matchingPlan.startDate);
      const endDate = new Date(matchingPlan.endDate);
      const weatherData: {
        destination: string;
        forecast: Array<{
          date: string;
          conditions: string;
          tempMin: number;
          tempMax: number;
          tempUnit: string;
          precipitation: {
            chance: number;
            amount: number;
            unit: string;
          };
          humidity: number;
          wind: {
            speed: number;
            unit: string;
            direction: string;
          };
        }>;
        seasonalNotes: string;
        packingRecommendations: string[];
      } = {
        destination: matchingPlan.destination.name,
        forecast: [],
        seasonalNotes: 'Pack layers as evenings can be cool. Rain is possible, so bring a light raincoat or umbrella.',
        packingRecommendations: [
          'Light, breathable clothing for daytime',
          'One warm layer for evenings',
          'Comfortable walking shoes',
          'Small umbrella',
          'Sunscreen and sunglasses'
        ]
      };
      
      // Generate daily forecasts
      for (let d = new Date(startDate); d <= endDate; d.setDate(d.getDate() + 1)) {
        const tempMin = Math.round(15 + Math.random() * 8);
        const tempMax = tempMin + 5 + Math.round(Math.random() * 5);
        const weatherConditions = ['Sunny', 'Partly Cloudy', 'Mostly Cloudy', 'Light Rain', 'Sunny'];
        const windDirections = ['N', 'NE', 'E', 'SE', 'S', 'SW', 'W', 'NW'];
        
        weatherData.forecast.push({
          date: d.toISOString().split('T')[0],
          conditions: weatherConditions[Math.floor(Math.random() * weatherConditions.length)],
          tempMin: tempMin,
          tempMax: tempMax,
          tempUnit: 'C',
          precipitation: {
            chance: Math.round(Math.random() * 50),
            amount: Math.round(Math.random() * 10) / 10,
            unit: 'mm'
          },
          humidity: 40 + Math.round(Math.random() * 30),
          wind: {
            speed: 5 + Math.round(Math.random() * 15),
            unit: 'km/h',
            direction: windDirections[Math.floor(Math.random() * windDirections.length)]
          }
        });
      }
      
      return weatherData;
    case 'pricing':
      // Calculate budget totals safely
      const budgetBreakdown = matchingPlan.budget.breakdown || {};
      const committedSpend = Object.values(budgetBreakdown).reduce((sum, val) => sum + val, 0);
      
      return {
        summary: {
          totalBudget: matchingPlan.budget.total,
          currency: matchingPlan.budget.currency,
          breakdown: budgetBreakdown,
          spendTracking: {
            allocated: matchingPlan.budget.total,
            committed: committedSpend,
            remaining: matchingPlan.budget.total - committedSpend
          },
          savingsSuggestions: [
            'Consider a multi-attraction city pass for potential savings of up to $85',
            'Several museums offer free entry on the first Sunday of the month',
            'Many restaurants offer fixed-price lunch menus that are more affordable than dinner',
            'Public transit passes offer significant savings over individual tickets'
          ]
        },
        valueAnalysis: {
          bestValues: [
            {
              category: 'Accommodation',
              option: matchingPlan.accommodations && matchingPlan.accommodations.length > 0 
                ? matchingPlan.accommodations[0].name 
                : 'Best-value hotel options',
              reasoning: 'Excellent location with high ratings at competitive price point'
            },
            {
              category: 'Transportation',
              option: 'Multi-day transit pass',
              reasoning: 'Unlimited access to all public transportation for a fraction of individual ticket costs'
            },
            {
              category: 'Dining',
              option: 'Mix of fine dining and local cafes',
              reasoning: 'Experience gourmet cuisine without breaking budget by balancing with affordable local options'
            }
          ],
          splurgeRecommendations: [
            {
              experience: 'Dinner at Michelin-starred restaurant',
              reasoning: 'Once-in-a-lifetime culinary experience unique to this destination'
            },
            {
              experience: 'Skip-the-line guided museum tour',
              reasoning: 'Maximizes limited time and provides deeper understanding of world-class art'
            }
          ]
        }
      };
    case 'scheduling':
      // Return the full itinerary with day-by-day breakdown
      // Handle case where activities might be undefined
      if (!matchingPlan.activities || matchingPlan.activities.length === 0) {
        return {
          summary: {
            destination: matchingPlan.destination.name,
            tripDuration: Math.ceil((new Date(matchingPlan.endDate).getTime() - new Date(matchingPlan.startDate).getTime()) / (1000 * 60 * 60 * 24)),
            activityPace: 'Moderate',
            highlights: []
          },
          itinerary: {},
          recommendations: {
            paceNotes: 'Trip schedule not yet available',
            restBreaks: [],
            transportationTips: []
          }
        };
      }
      
      // Get highlight activities
      const highlightActivities = matchingPlan.activities.slice(0, 3).map(a => a.name);
      
      // Create itinerary by day
      const itineraryByDay: Record<string, {
        date: string;
        dayNumber: number;
        activities: Array<{
          name: string;
          startTime?: string;
          endTime?: string;
          location?: string;
          notes?: string;
        }>;
      }> = {};
      
      // Group activities by day
      matchingPlan.activities.forEach(activity => {
        const date = activity.date;
        if (!itineraryByDay[date]) {
          // Create a new day entry
          itineraryByDay[date] = {
            date: date,
            dayNumber: Math.ceil((new Date(date).getTime() - new Date(matchingPlan.startDate).getTime()) / (1000 * 60 * 60 * 24)) + 1,
            activities: []
          };
        }
        
        // Add activity to the day
        itineraryByDay[date].activities.push({
          name: activity.name,
          startTime: activity.startTime,
          endTime: activity.endTime,
          location: activity.location,
          notes: activity.description
        });
      });
      
      // Sort activities by start time for each day
      Object.keys(itineraryByDay).forEach(date => {
        itineraryByDay[date].activities.sort((a, b) => {
          const timeA = a.startTime || '23:59';
          const timeB = b.startTime || '23:59';
          return timeA.localeCompare(timeB);
        });
      });
      
      return {
        summary: {
          destination: matchingPlan.destination.name,
          tripDuration: Math.ceil((new Date(matchingPlan.endDate).getTime() - new Date(matchingPlan.startDate).getTime()) / (1000 * 60 * 60 * 24)),
          activityPace: 'Moderate',
          highlights: highlightActivities
        },
        itinerary: itineraryByDay,
        recommendations: {
          paceNotes: 'Schedule includes a good balance of guided tours and free time',
          restBreaks: [
            'Afternoon break recommended on day 3 due to morning walking tour',
            'Free morning scheduled on day 5 for flexibility or relaxation'
          ],
          transportationTips: [
            'Pre-book airport transfers to save time',
            'Consider walking between nearby attractions to experience local atmosphere'
          ]
        }
      };
    default:
      return { error: 'Unknown agent type' };
  }
};