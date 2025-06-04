/**
 * Helper functions for testing simulation behavior
 */

/**
 * Logs the current state of the simulation
 * @param stageActive Whether the workflow stage is not 'idle'
 * @param connectionActive Whether the connection is active
 * @param activeAgents List of active agents
 */
export const logSimulationState = (
  stageActive: boolean,
  connectionActive: boolean,
  activeAgents: string[]
): void => {
  console.log('---- Simulation State Check ----');
  console.log(`Workflow Active: ${stageActive ? 'YES' : 'NO'}`);
  console.log(`Connection Active: ${connectionActive ? 'YES' : 'NO'}`);
  console.log(`Active Agents: ${activeAgents.length ? activeAgents.join(', ') : 'None'}`);
  console.log('-------------------------------');
};

/**
 * Verifies that the simulation is in the correct state
 * 
 * Use in development to check if simulation only starts after user input
 */
export const verifySimulationBehavior = (): void => {
  // Check localStorage for our test flag
  const hasUserInput = localStorage.getItem('travelPlannerUserInput') === 'true';
  const simulationActive = localStorage.getItem('travelPlannerSimulationActive') === 'true';
  
  console.log('---- Simulation Behavior Check ----');
  console.log(`User Has Provided Input: ${hasUserInput ? 'YES' : 'NO'}`);
  console.log(`Simulation Is Active: ${simulationActive ? 'YES' : 'NO'}`);
  
  if (simulationActive && !hasUserInput) {
    console.error('ERROR: Simulation is active before user input!');
  } else if (simulationActive && hasUserInput) {
    console.log('CORRECT: Simulation started after user input');
  } else if (!simulationActive && !hasUserInput) {
    console.log('CORRECT: Simulation not active before user input');
  }
  console.log('----------------------------------');
};