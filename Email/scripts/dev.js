#!/usr/bin/env node

const { spawn } = require('child_process');
const path = require('path');

console.log('Starting Melanie Email in development mode...');

// Ensure we're in the Email directory
process.chdir(path.join(__dirname, '..'));

// Start the development server
const devProcess = spawn('npm', ['run', 'tauri:dev'], {
  stdio: 'inherit',
  shell: true
});

devProcess.on('close', (code) => {
  console.log(`Development server exited with code ${code}`);
});

devProcess.on('error', (error) => {
  console.error('Failed to start development server:', error);
});