#!/usr/bin/env node

const { execSync } = require('child_process');
const fs = require('fs');
const path = require('path');

const platform = process.platform;
const arch = process.arch;

console.log(`Building Melanie Email for ${platform}-${arch}...`);

// Ensure we're in the Email directory
process.chdir(path.join(__dirname, '..'));

try {
  // Install dependencies if needed
  if (!fs.existsSync('node_modules')) {
    console.log('Installing frontend dependencies...');
    execSync('npm install', { stdio: 'inherit' });
  }

  // Build the application
  console.log('Building application...');
  execSync('npm run tauri:build', { stdio: 'inherit' });

  console.log('Build completed successfully!');
  
  // Show output location
  const bundleDir = path.join('src-tauri', 'target', 'release', 'bundle');
  if (fs.existsSync(bundleDir)) {
    console.log('\nBuild artifacts created in:');
    const subdirs = fs.readdirSync(bundleDir);
    subdirs.forEach(subdir => {
      const fullPath = path.join(bundleDir, subdir);
      if (fs.statSync(fullPath).isDirectory()) {
        console.log(`  ${fullPath}/`);
        const files = fs.readdirSync(fullPath);
        files.forEach(file => {
          console.log(`    - ${file}`);
        });
      }
    });
  }

} catch (error) {
  console.error('Build failed:', error.message);
  process.exit(1);
}