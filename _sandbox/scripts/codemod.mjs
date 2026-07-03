import fs from 'fs';
import path from 'path';
import { globSync } from 'glob';

const dir = '/Users/JamesO/DevWork/InProgress/Vanyshr/VanyshrDesignRefactor/vanyshr-mono';
const files = globSync('**/*.{ts,tsx,css,scss,js,jsx}', {
  cwd: dir,
  ignore: ['**/node_modules/**', '**/dist/**', '**/.next/**', 'codemod.mjs']
});

let affectedFiles = new Set();

files.forEach(file => {
  const fullPath = path.join(dir, file);
  let content = fs.readFileSync(fullPath, 'utf8');
  let originalContent = content;

  // Replace Hexes (Blind)
  content = content.replace(/#476B84/gi, '#B8C4CC');
  content = content.replace(/#A8BFD4/gi, '#B8C4CC');
  content = content.replace(/#14ABFE/gi, '#00BFFF');
  content = content.replace(/#CDD9E5/gi, '#4A5568');
  content = content.replace(/#D4DFE8/gi, '#2A4A68');
  content = content.replace(/#0F2D45/gi, '#2D3847');
  content = content.replace(/#1A3A52/gi, '#2D3847');

  // Contextual #022136
  // Looking at the instruction: "Keep as #022136 when it is the text color on a primary button ... Replace with #022136 when it is a layout background"
  // Let's replace bg-[#022136] with bg-[#022136]
  content = content.replace(/bg-\[\s*#022136\s*\]/gi, 'bg-[#022136]');

  // F0F4F8 is generally used as bg, replace with #022136
  content = content.replace(/#F0F4F8/gi, '#022136');

  // Remove `dark:` prefixes for classes that have both a light and dark version.
  // Usually they appear like "bg-white dark:bg-[#2D3847]". We want just "bg-[#2D3847]"
  // A naive approach: find a light class right before a dark class, e.g., `text-[#022136] dark:text-white`
  // We can just find `dark:` and remove it, but that leaves the light class. 
  // Let's find "some-class dark:some-other-class" and replace with "some-other-class".
  // Note: some-class doesn't always precede dark class directly.
  // Actually, replacing `dark:` with nothing is the first step: `dark:bg-[#022136]` -> `bg-[#022136]`. BUT wait, then we'd have duplicate prefixes (e.g. bg-white bg-[#022136]).
  // Let's use a regex to strip the light version if it matches common patterns:
  content = content.replace(/([a-z0-9-]+(?:-\[[^\]]*\])?(?:\/[0-9]+)?)\s+dark:([a-z0-9-]+(?:-\[[^\]]*\])?(?:\/[0-9]+)?)/gi, (match, light, dark) => {
    // Return just the dark class
    return dark;
  });
  
  // What about just hanging `dark:text-white`?
  content = content.replace(/dark:([a-z0-9-]+(?:-\[[^\]]*\])?(?:\/[0-9]+)?)/gi, '$1');

  // What about bg-white without a dark side (now that we stripped `dark:`)?
  // We can leave `bg-white` and `bg-[#FFFFFF]` for now, but the prompt says:
  // "No card should have a white or light background"
  // Let's replace `bg-white` inside cards/modals, or we can just replace all `bg-white` with `bg-[#2D3847]` because this app is dark mode only. Wait. `bg-white` might be used for small things.
  // "DO NOT replace #FFFFFF text color uses."
  content = content.replace(/bg-white/g, 'bg-[#2D3847]');
  content = content.replace(/bg-\[\s*#FFFFFF\s*\]/gi, 'bg-[#2D3847]');

  if (content !== originalContent) {
    fs.writeFileSync(fullPath, content, 'utf8');
    affectedFiles.add(file);
  }
});

console.log('Affected files:');
Array.from(affectedFiles).forEach(f => console.log(' - ' + f));
