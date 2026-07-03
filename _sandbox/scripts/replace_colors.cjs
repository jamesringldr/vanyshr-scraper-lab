const fs = require('fs');
const path = require('path');

const directoriesToSearch = ['apps/app/src', 'packages/ui/src'];
const extensions = ['.ts', '.tsx', '.css'];

const simpleReplacements = [
  { regex: /#14ABFE/gi, replacement: '#00BFFF' },
  { regex: /#476B84/gi, replacement: '#B8C4CC' },
  { regex: /#A8BFD4/gi, replacement: '#B8C4CC' },
  { regex: /#0F2D45/gi, replacement: '#2D3847' },
  { regex: /#1A3A52/gi, replacement: '#2D3847' },
  { regex: /#CDD9E5/gi, replacement: '#4A5568' },
  { regex: /bg-\[#022136\]/g, replacement: 'bg-[#022136]' },
];

function processDirectory(directory) {
  try {
    const files = fs.readdirSync(directory);
    for (const file of files) {
      const fullPath = path.join(directory, file);
      const stat = fs.statSync(fullPath);

      if (stat.isDirectory()) {
        processDirectory(fullPath);
      } else if (extensions.includes(path.extname(fullPath))) {
        let content = fs.readFileSync(fullPath, 'utf8');
        let originalContent = content;

        for (const { regex, replacement } of simpleReplacements) {
          content = content.replace(regex, replacement);
        }

        if (content !== originalContent) {
          fs.writeFileSync(fullPath, content, 'utf8');
          console.log(`Updated: ${fullPath}`);
        }
      }
    }
  } catch (error) {
    console.error(`Error processing directory ${directory}:`, error);
  }
}

for (const dir of directoriesToSearch) {
  processDirectory(dir);
}
console.log('Finished color replacements.');
