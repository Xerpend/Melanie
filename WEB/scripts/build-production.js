#!/usr/bin/env node
/**
 * Production build and deployment script for Melanie Web Interface
 * Handles building, optimization, and deployment preparation
 */

const { execSync } = require('child_process');
const fs = require('fs');
const path = require('path');

function runCommand(cmd, options = {}) {
  console.log(`Running: ${cmd}`);
  try {
    const result = execSync(cmd, { 
      stdio: 'inherit', 
      encoding: 'utf8',
      ...options 
    });
    return result;
  } catch (error) {
    console.error(`Error running command: ${cmd}`);
    console.error(error.message);
    process.exit(1);
  }
}

function checkEnvironment() {
  console.log('Checking build environment...');
  
  // Check Node.js version
  const nodeVersion = process.version;
  console.log(`Node.js version: ${nodeVersion}`);
  
  if (parseInt(nodeVersion.slice(1)) < 18) {
    console.error('Error: Node.js 18 or higher is required');
    process.exit(1);
  }
  
  // Check if package.json exists
  if (!fs.existsSync('package.json')) {
    console.error('Error: package.json not found');
    process.exit(1);
  }
  
  console.log('Environment check passed');
}

function installDependencies() {
  console.log('Installing dependencies...');
  runCommand('npm ci --only=production');
}

function runTests() {
  console.log('Running tests...');
  try {
    runCommand('npm test -- --run --coverage');
    console.log('All tests passed');
  } catch (error) {
    console.error('Tests failed. Aborting build.');
    process.exit(1);
  }
}

function buildApplication() {
  console.log('Building application...');
  
  // Set production environment
  process.env.NODE_ENV = 'production';
  
  // Build the Next.js application
  runCommand('npm run build');
  
  console.log('Build completed successfully');
}

function optimizeBuild() {
  console.log('Optimizing build...');
  
  // Check build size
  const buildDir = '.next';
  if (fs.existsSync(buildDir)) {
    const stats = fs.statSync(buildDir);
    console.log(`Build directory size: ${(stats.size / 1024 / 1024).toFixed(2)} MB`);
  }
  
  // Generate build report
  if (fs.existsSync('.next/analyze')) {
    console.log('Bundle analysis available at .next/analyze/');
  }
}

function createDeploymentPackage() {
  console.log('Creating deployment package...');
  
  const deployDir = 'deploy';
  
  // Clean previous deployment
  if (fs.existsSync(deployDir)) {
    fs.rmSync(deployDir, { recursive: true });
  }
  
  fs.mkdirSync(deployDir);
  
  // Copy necessary files for deployment
  const filesToCopy = [
    '.next',
    'public',
    'package.json',
    'package-lock.json',
    'next.config.ts'
  ];
  
  filesToCopy.forEach(file => {
    if (fs.existsSync(file)) {
      const stats = fs.statSync(file);
      if (stats.isDirectory()) {
        fs.cpSync(file, path.join(deployDir, file), { recursive: true });
      } else {
        fs.copyFileSync(file, path.join(deployDir, file));
      }
      console.log(`Copied: ${file}`);
    }
  });
  
  // Create deployment README
  const deployReadme = `# Melanie Web Interface Deployment

## Quick Start

1. Install dependencies:
   \`\`\`bash
   npm ci --only=production
   \`\`\`

2. Start the application:
   \`\`\`bash
   npm start
   \`\`\`

## Environment Variables

Create a \`.env.local\` file with:

\`\`\`
NEXT_PUBLIC_API_URL=http://your-api-server:8000
NODE_ENV=production
\`\`\`

## Docker Deployment

Build and run with Docker:

\`\`\`bash
docker build -t melanie-web .
docker run -p 3000:3000 melanie-web
\`\`\`

## Reverse Proxy Configuration

### Nginx
\`\`\`nginx
server {
    listen 80;
    server_name your-domain.com;
    
    location / {
        proxy_pass http://localhost:3000;
        proxy_http_version 1.1;
        proxy_set_header Upgrade $http_upgrade;
        proxy_set_header Connection 'upgrade';
        proxy_set_header Host $host;
        proxy_cache_bypass $http_upgrade;
    }
}
\`\`\`

### Apache
\`\`\`apache
<VirtualHost *:80>
    ServerName your-domain.com
    ProxyPreserveHost On
    ProxyPass / http://localhost:3000/
    ProxyPassReverse / http://localhost:3000/
</VirtualHost>
\`\`\`

## Performance Optimization

- Enable gzip compression
- Set up CDN for static assets
- Configure caching headers
- Monitor with performance tools

## Security

- Use HTTPS in production
- Set secure headers
- Configure CORS properly
- Regular security updates

## Monitoring

- Check application logs
- Monitor response times
- Track error rates
- Set up health checks
`;
  
  fs.writeFileSync(path.join(deployDir, 'DEPLOYMENT.md'), deployReadme);
  
  // Create production start script
  const startScript = `#!/bin/bash
# Production start script for Melanie Web Interface

echo "Starting Melanie Web Interface..."

# Check if .env.local exists
if [ ! -f .env.local ]; then
    echo "Warning: .env.local not found. Creating from template..."
    cat > .env.local << EOF
NEXT_PUBLIC_API_URL=http://localhost:8000
NODE_ENV=production
EOF
fi

# Install dependencies if node_modules doesn't exist
if [ ! -d node_modules ]; then
    echo "Installing dependencies..."
    npm ci --only=production
fi

# Start the application
echo "Starting application on port 3000..."
npm start
`;
  
  fs.writeFileSync(path.join(deployDir, 'start.sh'), startScript);
  fs.chmodSync(path.join(deployDir, 'start.sh'), 0o755);
  
  console.log(`Deployment package created in: ${path.resolve(deployDir)}`);
}

function generateBuildReport() {
  console.log('Generating build report...');
  
  const report = {
    timestamp: new Date().toISOString(),
    nodeVersion: process.version,
    platform: process.platform,
    buildSize: 0,
    files: []
  };
  
  // Calculate build size
  if (fs.existsSync('.next')) {
    const calculateSize = (dir) => {
      let size = 0;
      const files = fs.readdirSync(dir);
      
      files.forEach(file => {
        const filePath = path.join(dir, file);
        const stats = fs.statSync(filePath);
        
        if (stats.isDirectory()) {
          size += calculateSize(filePath);
        } else {
          size += stats.size;
          report.files.push({
            path: filePath,
            size: stats.size
          });
        }
      });
      
      return size;
    };
    
    report.buildSize = calculateSize('.next');
  }
  
  fs.writeFileSync('build-report.json', JSON.stringify(report, null, 2));
  
  console.log(`Build size: ${(report.buildSize / 1024 / 1024).toFixed(2)} MB`);
  console.log(`Total files: ${report.files.length}`);
  console.log('Build report saved to build-report.json');
}

function main() {
  console.log('Melanie Web Interface Production Builder');
  console.log('=======================================');
  
  try {
    checkEnvironment();
    installDependencies();
    runTests();
    buildApplication();
    optimizeBuild();
    createDeploymentPackage();
    generateBuildReport();
    
    console.log('\nProduction build completed successfully!');
    console.log('Deployment package available in ./deploy/');
  } catch (error) {
    console.error('Build failed:', error.message);
    process.exit(1);
  }
}

if (require.main === module) {
  main();
}

module.exports = { main, buildApplication, createDeploymentPackage };