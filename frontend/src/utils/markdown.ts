/**
 * Markdown parser for template preview with variable highlighting
 * Supports: headers, bold, italic, code blocks, inline code, lists, tables, horizontal rules
 */

/**
 * Helper to process markdown tables
 */
function processTable(rows: string[]): string {
  if (rows.length < 2) return rows.join('\n');

  const headerRow = rows[0];
  const bodyRows = rows.slice(2); // Skip header and separator

  // Parse header cells
  const headers = headerRow.split('|').filter(c => c.trim()).map(c =>
    `<th class="border px-3 py-2 bg-gray-50 text-left font-semibold">${c.trim()}</th>`
  ).join('');

  // Parse body cells
  const body = bodyRows.map(row => {
    const cells = row.split('|').filter(c => c.trim()).map(c =>
      `<td class="border px-3 py-2">${c.trim()}</td>`
    ).join('');
    return `<tr>${cells}</tr>`;
  }).join('');

  return `<table class="w-full border-collapse my-4 text-sm"><thead><tr>${headers}</tr></thead><tbody>${body}</tbody></table>`;
}

/**
 * Parse markdown text to HTML with variable highlighting
 * Highlights [variables] and {variables} with special styling
 */
export function parseMarkdown(text: string): string {
  if (!text) return '';

  // Process in order: escape HTML first, then handle variables, then markdown
  let processed = text
    // Escape HTML to prevent XSS but preserve newlines
    .replace(/&/g, '&amp;')
    .replace(/</g, '&lt;')
    .replace(/>/g, '&gt;');

  // Highlight template variables FIRST (before markdown processing)
  // Square bracket variables like [蛋白质名称], [UniProt ID]
  processed = processed.replace(
    /\[([^\]]+)\]/g,
    '<span class="bg-blue-100 text-blue-800 px-1.5 py-0.5 rounded font-mono text-sm border border-blue-300">[$1]</span>'
  );
  // Curly brace variables like {target_id}, {uniprot_id}
  processed = processed.replace(
    /\{([^}]+)\}/g,
    '<span class="bg-purple-100 text-purple-800 px-1.5 py-0.5 rounded font-mono text-sm border border-purple-300">{$1}</span>'
  );

  // Split into lines for processing
  const lines = processed.split('\n');
  const result: string[] = [];
  let inCodeBlock = false;
  let tableRows: string[] = [];

  for (let i = 0; i < lines.length; i++) {
    const line = lines[i];

    // Code blocks (must be processed before other regex)
    if (line.startsWith('```')) {
      if (!inCodeBlock) {
        inCodeBlock = true;
        result.push('<pre class="bg-gray-800 text-gray-100 p-4 rounded-lg overflow-x-auto my-4"><code>');
      } else {
        inCodeBlock = false;
        result.push('</code></pre>');
      }
      continue;
    }
    if (inCodeBlock) {
      result.push(line);
      continue;
    }

    // Headers
    if (line.startsWith('### ')) {
      result.push(`<h3 class="text-lg font-semibold text-gray-900 mt-4 mb-2">${line.substring(4)}</h3>`);
      continue;
    }
    if (line.startsWith('## ')) {
      result.push(`<h2 class="text-xl font-bold text-gray-900 mt-6 mb-3">${line.substring(3)}</h2>`);
      continue;
    }
    if (line.startsWith('# ')) {
      result.push(`<h1 class="text-2xl font-bold text-gray-900 mt-6 mb-4">${line.substring(2)}</h1>`);
      continue;
    }

    // Horizontal rule
    if (line.match(/^---+$/)) {
      result.push('<hr class="my-6 border-gray-300" />');
      continue;
    }

    // Table detection
    if (line.startsWith('|')) {
      tableRows.push(line);
      // Check if next line is table separator
      if (i + 1 < lines.length && lines[i + 1].match(/^\|[\s-|:]+\|$/)) {
        // It's a table, process accumulated rows
        const tableHtml = processTable(tableRows);
        result.push(tableHtml);
        tableRows = [];
        i++; // Skip separator line
      }
      continue;
    } else if (tableRows.length > 0) {
      // Flush any pending table rows (wasn't actually a table)
      result.push(...tableRows);
      tableRows = [];
    }

    // Unordered lists
    if (line.match(/^[\s]*[-*]\s/)) {
      const content = line.replace(/^[\s]*[-*]\s/, '');
      result.push(`<li class="ml-4 text-gray-700 list-disc">${content}</li>`);
      continue;
    }

    // Ordered lists
    if (line.match(/^[\s]*\d+\.\s/)) {
      const content = line.replace(/^[\s]*\d+\.\s/, '');
      result.push(`<li class="ml-4 text-gray-700 list-decimal">${content}</li>`);
      continue;
    }

    // Regular paragraph - apply inline formatting
    let formatted = line
      // Bold
      .replace(/\*\*(.*?)\*\*/g, '<strong class="font-semibold">$1</strong>')
      // Italic
      .replace(/\*(.*?)\*/g, '<em>$1</em>')
      // Inline code
      .replace(/`([^`]+)`/g, '<code class="bg-gray-100 text-gray-800 px-1.5 py-0.5 rounded text-sm font-mono">$1</code>');

    if (formatted.trim()) {
      result.push(`<p class="text-gray-700 mb-2">${formatted}</p>`);
    } else {
      result.push(''); // Empty line for spacing
    }
  }

  // Close any unclosed table
  if (tableRows.length > 0) {
    result.push(...tableRows);
  }

  return result.join('\n');
}
