#!/usr/bin/env node

const { spawn } = require('child_process');
const os = require('os');

/**
 * Detect Tailscale IP address
 */
function getTailscaleIP() {
  const interfaces = os.networkInterfaces();
  
  for (const [name, addrs] of Object.entries(interfaces)) {
    if (name.includes('tailscale') || name.includes('utun')) {
      for (const addr of addrs || []) {
        if (addr.family === 'IPv4' && !addr.internal) {
          return addr.address;
        }
      }
    }
  }
  
  return null;
}

/**
 * Start Next.js server with Tailscale binding
 */
function startServer() {
  const tailscaleIP = getTailscaleIP();
  
  if (!tailscaleIP) {
    console.error('❌ Tailscale network not detected!');
    console.error('Please ensure Tailscale is running and connected.');
    process.exit(1);
  }
  
  console.log(`🔗 Tailscale IP detected: ${tailscaleIP}`);
  console.log(`🚀 Starting Melanie Web Interface on http://${tailscaleIP}:3000`);
  
  const env = {
    ...process.env,
    HOSTNAME: tailscaleIP,
    PORT: '3000',
  };
  
  const nextProcess = spawn('npm', ['run', 'dev'], {
    stdio: 'inherit',
    env,
    cwd: process.cwd(),
  });
  
  nextProcess.on('error', (error) => {
    console.error('❌ Failed to start server:', error);
    process.exit(1);
  });
  
  nextProcess.on('close', (code) => {
    console.log(`Server process exited with code ${code}`);
    process.exit(code);
  });
  
  // Graceful shutdown
  process.on('SIGINT', () => {
    console.log('\n🛑 Shutting down server...');
    nextProcess.kill('SIGINT');
  });
  
  process.on('SIGTERM', () => {
    console.log('\n🛑 Shutting down server...');
    nextProcess.kill('SIGTERM');
  });
}

if (require.main === module) {
  startServer();
}

module.exports = { getTailscaleIP, startServer };