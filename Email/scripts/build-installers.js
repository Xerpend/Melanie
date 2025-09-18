#!/usr/bin/env node
/**
 * Cross-platform installer builder for Melanie Email Client
 * Creates MSI (Windows), DMG (macOS), and DEB (Linux) packages
 */

const { execSync } = require('child_process');
const fs = require('fs');
const path = require('path');
const os = require('os');

const PLATFORMS = {
  win32: { target: 'nsis', ext: 'exe' },
  darwin: { target: 'dmg', ext: 'dmg' },
  linux: { target: 'deb', ext: 'deb' }
};

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

function installDependencies() {
  console.log('Installing build dependencies...');
  
  // Install Tauri CLI if not present
  try {
    execSync('cargo tauri --version', { stdio: 'ignore' });
  } catch {
    console.log('Installing Tauri CLI...');
    runCommand('cargo install tauri-cli');
  }
  
  // Install Node dependencies
  runCommand('npm install');
}

function buildForPlatform(platform) {
  console.log(`Building for ${platform}...`);
  
  const config = PLATFORMS[platform];
  if (!config) {
    console.error(`Unsupported platform: ${platform}`);
    return;
  }
  
  // Build the application
  runCommand(`cargo tauri build --target ${config.target}`);
  
  console.log(`Build completed for ${platform}`);
}

function createInstallerConfig() {
  console.log('Creating installer configurations...');
  
  // Windows NSIS installer config
  const nsisConfig = `
!define APPNAME "Melanie Email Client"
!define COMPANYNAME "Melanie AI"
!define DESCRIPTION "AI-Enhanced Email Client"
!define VERSIONMAJOR 1
!define VERSIONMINOR 0
!define VERSIONBUILD 0

RequestExecutionLevel admin

InstallDir "$PROGRAMFILES\\${APPNAME}"

Page directory
Page instfiles

Section "install"
    SetOutPath $INSTDIR
    File "src-tauri\\target\\release\\melanie-email.exe"
    
    # Create uninstaller
    WriteUninstaller "$INSTDIR\\uninstall.exe"
    
    # Add to Add/Remove Programs
    WriteRegStr HKLM "Software\\Microsoft\\Windows\\CurrentVersion\\Uninstall\\${APPNAME}" "DisplayName" "${APPNAME}"
    WriteRegStr HKLM "Software\\Microsoft\\Windows\\CurrentVersion\\Uninstall\\${APPNAME}" "UninstallString" "$INSTDIR\\uninstall.exe"
    WriteRegStr HKLM "Software\\Microsoft\\Windows\\CurrentVersion\\Uninstall\\${APPNAME}" "InstallLocation" "$INSTDIR"
    WriteRegStr HKLM "Software\\Microsoft\\Windows\\CurrentVersion\\Uninstall\\${APPNAME}" "Publisher" "${COMPANYNAME}"
    WriteRegDWORD HKLM "Software\\Microsoft\\Windows\\CurrentVersion\\Uninstall\\${APPNAME}" "VersionMajor" ${VERSIONMAJOR}
    WriteRegDWORD HKLM "Software\\Microsoft\\Windows\\CurrentVersion\\Uninstall\\${APPNAME}" "VersionMinor" ${VERSIONMINOR}
    WriteRegDWORD HKLM "Software\\Microsoft\\Windows\\CurrentVersion\\Uninstall\\${APPNAME}" "NoModify" 1
    WriteRegDWORD HKLM "Software\\Microsoft\\Windows\\CurrentVersion\\Uninstall\\${APPNAME}" "NoRepair" 1
    
    # Create desktop shortcut
    CreateShortcut "$DESKTOP\\${APPNAME}.lnk" "$INSTDIR\\melanie-email.exe"
    
    # Create start menu shortcut
    CreateDirectory "$SMPROGRAMS\\${APPNAME}"
    CreateShortcut "$SMPROGRAMS\\${APPNAME}\\${APPNAME}.lnk" "$INSTDIR\\melanie-email.exe"
SectionEnd

Section "uninstall"
    Delete "$INSTDIR\\melanie-email.exe"
    Delete "$INSTDIR\\uninstall.exe"
    Delete "$DESKTOP\\${APPNAME}.lnk"
    Delete "$SMPROGRAMS\\${APPNAME}\\${APPNAME}.lnk"
    RMDir "$SMPROGRAMS\\${APPNAME}"
    RMDir $INSTDIR
    
    DeleteRegKey HKLM "Software\\Microsoft\\Windows\\CurrentVersion\\Uninstall\\${APPNAME}"
SectionEnd
`;
  
  fs.writeFileSync('installer.nsi', nsisConfig);
  
  // macOS DMG creation script
  const dmgScript = `#!/bin/bash
# Create DMG for macOS

APP_NAME="Melanie Email Client"
DMG_NAME="melanie-email-installer"
SOURCE_DIR="src-tauri/target/release/bundle/macos"
TEMP_DIR="temp_dmg"

# Clean up previous builds
rm -rf "$TEMP_DIR"
rm -f "$DMG_NAME.dmg"

# Create temporary directory
mkdir "$TEMP_DIR"

# Copy app bundle
cp -R "$SOURCE_DIR/Melanie Email Client.app" "$TEMP_DIR/"

# Create Applications symlink
ln -s /Applications "$TEMP_DIR/Applications"

# Create DMG
hdiutil create -volname "$APP_NAME" -srcfolder "$TEMP_DIR" -ov -format UDZO "$DMG_NAME.dmg"

# Clean up
rm -rf "$TEMP_DIR"

echo "DMG created: $DMG_NAME.dmg"
`;
  
  fs.writeFileSync('create-dmg.sh', dmgScript);
  fs.chmodSync('create-dmg.sh', 0o755);
  
  // Linux DEB control file
  const debControl = `Package: melanie-email-client
Version: 1.0.0
Section: mail
Priority: optional
Architecture: amd64
Depends: libwebkit2gtk-4.0-37, libgtk-3-0
Maintainer: Melanie AI <support@melanie-ai.com>
Description: AI-Enhanced Email Client
 Melanie Email Client provides AI-powered email management
 with features like thread summarization, smart replies,
 and intelligent email analysis.
`;
  
  // Create debian package structure
  const debDir = 'debian-package';
  if (!fs.existsSync(debDir)) {
    fs.mkdirSync(debDir, { recursive: true });
    fs.mkdirSync(`${debDir}/DEBIAN`);
    fs.mkdirSync(`${debDir}/usr/bin`, { recursive: true });
    fs.mkdirSync(`${debDir}/usr/share/applications`);
    fs.mkdirSync(`${debDir}/usr/share/pixmaps`);
  }
  
  fs.writeFileSync(`${debDir}/DEBIAN/control`, debControl);
  
  // Desktop entry for Linux
  const desktopEntry = `[Desktop Entry]
Name=Melanie Email Client
Comment=AI-Enhanced Email Client
Exec=/usr/bin/melanie-email
Icon=melanie-email
Terminal=false
Type=Application
Categories=Office;Email;
`;
  
  fs.writeFileSync(`${debDir}/usr/share/applications/melanie-email.desktop`, desktopEntry);
  
  console.log('Installer configurations created');
}

function packageInstallers() {
  console.log('Creating installer packages...');
  
  const platform = os.platform();
  
  if (platform === 'win32') {
    // Create Windows installer using NSIS
    try {
      runCommand('makensis installer.nsi');
      console.log('Windows installer created');
    } catch (error) {
      console.log('NSIS not found, skipping Windows installer creation');
    }
  } else if (platform === 'darwin') {
    // Create macOS DMG
    runCommand('./create-dmg.sh');
    console.log('macOS DMG created');
  } else if (platform === 'linux') {
    // Create Linux DEB package
    const debDir = 'debian-package';
    
    // Copy binary
    runCommand(`cp src-tauri/target/release/melanie-email ${debDir}/usr/bin/`);
    runCommand(`chmod +x ${debDir}/usr/bin/melanie-email`);
    
    // Build DEB package
    runCommand(`dpkg-deb --build ${debDir} melanie-email-client_1.0.0_amd64.deb`);
    console.log('Linux DEB package created');
  }
}

function createDistributionPackage() {
  console.log('Creating distribution package...');
  
  const distDir = 'dist-installers';
  if (!fs.existsSync(distDir)) {
    fs.mkdirSync(distDir);
  }
  
  // Copy installers to dist directory
  const files = fs.readdirSync('.');
  files.forEach(file => {
    if (file.endsWith('.exe') || file.endsWith('.dmg') || file.endsWith('.deb')) {
      fs.copyFileSync(file, path.join(distDir, file));
    }
  });
  
  // Create README
  const readme = `# Melanie Email Client Installers

## Windows
- Run \`melanie-email-installer.exe\` as Administrator
- Follow the installation wizard
- Launch from Start Menu or Desktop shortcut

## macOS
- Open \`melanie-email-installer.dmg\`
- Drag Melanie Email Client to Applications folder
- Launch from Applications or Launchpad

## Linux (Ubuntu/Debian)
- Install with: \`sudo dpkg -i melanie-email-client_1.0.0_amd64.deb\`
- Launch from Applications menu or run \`melanie-email\`

## System Requirements
- Windows 10/11 (64-bit)
- macOS 10.15+ (Catalina or later)
- Ubuntu 18.04+ / Debian 10+ (64-bit)

## Features
- AI-powered email summarization
- Smart reply generation
- Intelligent email analysis
- IMAP synchronization
- Dark blue theme
- Cross-platform compatibility

## Support
For issues and documentation, visit: https://github.com/your-org/melanie-ai
`;
  
  fs.writeFileSync(path.join(distDir, 'README.md'), readme);
  
  console.log(`Distribution package created in: ${path.resolve(distDir)}`);
}

function main() {
  console.log('Melanie Email Client Installer Builder');
  console.log('=====================================');
  
  try {
    installDependencies();
    createInstallerConfig();
    
    const platform = os.platform();
    buildForPlatform(platform);
    packageInstallers();
    createDistributionPackage();
    
    console.log('\nInstaller build completed successfully!');
  } catch (error) {
    console.error('Build failed:', error.message);
    process.exit(1);
  }
}

if (require.main === module) {
  main();
}

module.exports = { main, buildForPlatform, createInstallerConfig };