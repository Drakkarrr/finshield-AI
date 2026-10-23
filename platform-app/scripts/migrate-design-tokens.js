#!/usr/bin/env node
/**
 * FinShield AI — Design Token Migration Script (S5.1)
 * Replaces hardcoded Tailwind color classes with design tokens
 * 
 * Usage: node scripts/migrate-design-tokens.js [--dry-run]
 */

const fs = require('fs');
const path = require('path');

// Color mapping: hardcoded → design token
const COLOR_MAP = {
  // Red → danger
  'bg-red-50': 'bg-danger-bg',
  'bg-red-100': 'bg-danger-light',
  'bg-red-300': 'bg-danger',
  'bg-red-400': 'bg-danger',
  'bg-red-500': 'bg-danger',
  'bg-red-600': 'bg-danger',
  'bg-red-700': 'bg-danger',
  'text-red-300': 'text-danger',
  'text-red-400': 'text-danger',
  'text-red-500': 'text-danger',
  'text-red-600': 'text-danger',
  'text-red-700': 'text-danger',
  'border-red-200': 'border-danger-light',
  'border-red-300': 'border-danger',
  'border-red-500': 'border-danger',
  
  // Emerald → success
  'bg-emerald-50': 'bg-success-bg',
  'bg-emerald-100': 'bg-success-light',
  'bg-emerald-300': 'bg-success',
  'bg-emerald-400': 'bg-success',
  'bg-emerald-500': 'bg-success',
  'bg-emerald-600': 'bg-success',
  'text-emerald-300': 'text-success',
  'text-emerald-400': 'text-success',
  'text-emerald-500': 'text-success',
  'text-emerald-600': 'text-success',
  'text-emerald-700': 'text-success',
  'border-emerald-300': 'border-success',
  'border-emerald-500': 'border-success',
  'border-emerald-500/30': 'border-success/30',
  
  // Gray → ink/border
  'bg-gray-50': 'bg-surface-hover',
  'bg-gray-100': 'bg-bg-alt',
  'bg-gray-200': 'bg-border',
  'bg-gray-300': 'bg-border-dark',
  'bg-gray-400': 'bg-ink-light',
  'bg-gray-500': 'bg-ink-muted',
  'bg-gray-600': 'bg-ink-secondary',
  'bg-gray-700': 'bg-ink',
  'bg-gray-800': 'bg-ink',
  'bg-gray-900': 'bg-ink',
  'text-gray-300': 'text-ink-light',
  'text-gray-400': 'text-ink-light',
  'text-gray-500': 'text-ink-muted',
  'text-gray-600': 'text-ink-secondary',
  'text-gray-700': 'text-ink',
  'text-gray-800': 'text-ink',
  'text-gray-900': 'text-ink',
  'border-gray-200': 'border-border',
  'border-gray-300': 'border-border',
  'border-gray-400': 'border-border-dark',
  
  // Blue → info
  'bg-blue-50': 'bg-info-bg',
  'bg-blue-100': 'bg-info-light',
  'bg-blue-300': 'bg-info',
  'bg-blue-400': 'bg-info',
  'bg-blue-500': 'bg-info',
  'bg-blue-600': 'bg-info',
  'bg-blue-700': 'bg-info',
  'text-blue-300': 'text-info',
  'text-blue-400': 'text-info',
  'text-blue-500': 'text-info',
  'text-blue-600': 'text-info',
  'text-blue-700': 'text-info',
  'border-blue-200': 'border-info-light',
  'border-blue-300': 'border-info',
  'border-blue-500': 'border-info',
  
  // Amber → warning
  'bg-amber-50': 'bg-warning-bg',
  'bg-amber-100': 'bg-warning-light',
  'bg-amber-300': 'bg-warning',
  'bg-amber-400': 'bg-warning',
  'bg-amber-500': 'bg-warning',
  'bg-amber-600': 'bg-warning',
  'bg-amber-700': 'bg-warning',
  'text-amber-300': 'text-warning',
  'text-amber-400': 'text-warning',
  'text-amber-500': 'text-warning',
  'text-amber-600': 'text-warning',
  'text-amber-700': 'text-warning',
  'border-amber-200': 'border-warning-light',
  'border-amber-300': 'border-warning',
  'border-amber-500': 'border-warning',
};

const DRY_RUN = process.argv.includes('--dry-run');

function migrateFile(filePath) {
  let content = fs.readFileSync(filePath, 'utf8');
  let originalContent = content;
  let changes = [];
  
  // Replace color classes
  for (const [hardcoded, token] of Object.entries(COLOR_MAP)) {
    const regex = new RegExp(`\\b${hardcoded}\\b`, 'g');
    const matches = content.match(regex);
    if (matches) {
      changes.push({
        from: hardcoded,
        to: token,
        count: matches.length
      });
      content = content.replace(regex, token);
    }
  }
  
  if (changes.length > 0) {
    if (!DRY_RUN) {
      fs.writeFileSync(filePath, content, 'utf8');
    }
    
    console.log(`\n${filePath}:`);
    changes.forEach(change => {
      console.log(`  ${change.from} → ${change.to} (${change.count}x)`);
    });
  }
  
  return changes.length;
}

function findFiles(dir, pattern = /\.(tsx?|jsx?)$/) {
  const files = [];
  
  function walk(currentPath) {
    const entries = fs.readdirSync(currentPath, { withFileTypes: true });
    
    for (const entry of entries) {
      const fullPath = path.join(currentPath, entry.name);
      
      // Skip node_modules and .next
      if (entry.name === 'node_modules' || entry.name === '.next') {
        continue;
      }
      
      if (entry.isDirectory()) {
        walk(fullPath);
      } else if (pattern.test(entry.name)) {
        files.push(fullPath);
      }
    }
  }
  
  walk(dir);
  return files;
}

function main() {
  const srcDir = path.join(__dirname, '..', 'src');
  
  console.log('FinShield AI — Design Token Migration');
  console.log('=====================================');
  console.log(`Mode: ${DRY_RUN ? 'DRY RUN (no changes)' : 'LIVE (will modify files)'}`);
  console.log(`Source: ${srcDir}\n`);
  
  const files = findFiles(srcDir);
  console.log(`Found ${files.length} files to scan\n`);
  
  let totalChanges = 0;
  let filesChanged = 0;
  
  for (const file of files) {
    const changes = migrateFile(file);
    if (changes > 0) {
      filesChanged++;
      totalChanges += changes;
    }
  }
  
  console.log('\n=====================================');
  console.log(`Files scanned: ${files.length}`);
  console.log(`Files changed: ${filesChanged}`);
  console.log(`Total replacements: ${totalChanges}`);
  
  if (DRY_RUN) {
    console.log('\n✓ Dry run complete. Run without --dry-run to apply changes.');
  } else {
    console.log('\n✓ Migration complete!');
  }
}

main();
