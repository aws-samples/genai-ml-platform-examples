const fs = require('fs');
const path = require('path');

const audioDir = path.join(__dirname, '../public/audio');
const manifestPath = path.join(audioDir, 'manifest.json');

const files = fs.readdirSync(audioDir)
  .filter(file => /\.(wav|mp3|m4a)$/i.test(file));

fs.writeFileSync(manifestPath, JSON.stringify(files, null, 2));
console.log('Audio manifest updated with', files.length, 'files');
