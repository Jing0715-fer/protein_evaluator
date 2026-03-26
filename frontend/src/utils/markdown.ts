/**
 * Markdown parser for template preview with variable highlighting
 * Supports: headers, bold, italic, code blocks, inline code, lists, tables, horizontal rules
 */

/**
 * Apply inline formatting to text (bold, italic, code)
 */
export function applyInlineFormatting(text: string): string {
  return text
    // Bold: **text** or __text__
    .replace(/\*\*(.+?)\*\*/g, '<strong>$1</strong>')
    .replace(/__(.+?)__/g, '<strong>$1</strong>')
    // Italic: *text* or _text_
    .replace(/\*(.+?)\*/g, '<em>$1</em>')
    .replace(/_(.+?)_/g, '<em>$1</em>')
    // Inline code: `code`
    .replace(/`([^`]+)`/g, '<code class="bg-gray-100 text-gray-800 px-1 py-0.5 rounded text-xs font-mono">$1</code>');
}

/**
 * Helper to process markdown tables
 */
function processTable(rows: string[]): string {
  if (rows.length < 2) return rows.join('\n');

  const headerRow = rows[0];
  const bodyRows = rows.slice(2); // Skip header and separator

  // Parse header cells - apply inline formatting
  const headers = headerRow.split('|').filter(c => c.trim()).map(c => {
    const content = applyInlineFormatting(c.trim());
    return `<th class="border border-gray-200 px-4 py-3 bg-gradient-to-b from-gray-50 to-gray-100 text-left font-semibold text-gray-700 text-sm">${content}</th>`;
  }).join('');

  // Parse body cells - apply inline formatting with alternating row colors
  const body = bodyRows.map((row, rowIndex) => {
    const bgClass = rowIndex % 2 === 0 ? 'bg-white' : 'bg-gray-50';
    const cells = row.split('|').filter(c => c.trim()).map(c => {
      const content = applyInlineFormatting(c.trim());
      return `<td class="border border-gray-200 px-4 py-3 text-gray-600 text-sm ${bgClass}">${content}</td>`;
    }).join('');
    return `<tr class="hover:bg-blue-50 transition-colors duration-150">${cells}</tr>`;
  }).join('');

  return `<table class="w-full border-collapse my-4 text-sm rounded-lg overflow-hidden shadow-sm border border-gray-200">
    <thead>
      <tr class="bg-gradient-to-r from-gray-100 to-gray-50">${headers}</tr>
    </thead>
    <tbody>${body}</tbody>
  </table>`;
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

  // Split into lines for processing
  const lines = processed.split('\n');
  const result: string[] = [];
  let inCodeBlock = false;

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

    // Headers - apply inline formatting to header text
    if (line.startsWith('### ')) {
      const headerText = applyInlineFormatting(line.substring(4));
      result.push(`<h3 class="text-lg font-semibold text-gray-900 mt-4 mb-2">${headerText}</h3>`);
      continue;
    }
    if (line.startsWith('## ')) {
      const headerText = applyInlineFormatting(line.substring(3));
      result.push(`<h2 class="text-xl font-bold text-gray-900 mt-6 mb-3">${headerText}</h2>`);
      continue;
    }
    if (line.startsWith('# ')) {
      const headerText = applyInlineFormatting(line.substring(2));
      result.push(`<h1 class="text-2xl font-bold text-gray-900 mt-6 mb-4">${headerText}</h1>`);
      continue;
    }

    // Horizontal rule
    if (line.match(/^---+$/)) {
      result.push('<hr class="my-6 border-gray-300" />');
      continue;
    }

    // Table detection - markdown table structure: header, separator, then data rows
    if (line.startsWith('|')) {
      // Check if the next line is a table separator
      if (i + 1 < lines.length && lines[i + 1].match(/^\|[\s\-:]+\|([\s\-:]+\|)*[\s\-:]*$/)) {
        // It's a table - collect header (current line)
        const tableLines: string[] = [line];
        let rowIndex = i + 1; // separator index
        tableLines.push(lines[rowIndex]); // add separator

        // Collect all data rows (consecutive lines starting with | after separator)
        rowIndex++;
        while (rowIndex < lines.length && lines[rowIndex].startsWith('|')) {
          tableLines.push(lines[rowIndex]);
          rowIndex++;
        }

        // Process the table
        const tableHtml = processTable(tableLines);
        result.push(tableHtml);
        i = rowIndex - 1; // Set i to last data row index, for loop will increment
      } else {
        // Not a table, output as raw text
        result.push(line);
      }
      continue;
    }

    // Unordered lists
    if (line.match(/^[\s]*[-*]\s/)) {
      const content = applyInlineFormatting(line.replace(/^[\s]*[-*]\s/, ''));
      result.push(`<li class="ml-4 text-gray-700 list-disc">${content}</li>`);
      continue;
    }

    // Ordered lists
    if (line.match(/^[\s]*\d+\.\s/)) {
      const content = applyInlineFormatting(line.replace(/^[\s]*\d+\.\s/, ''));
      result.push(`<li class="ml-4 text-gray-700 list-decimal">${content}</li>`);
      continue;
    }

    // Regular paragraph - apply inline formatting
    const formatted = applyInlineFormatting(line);

    if (formatted.trim()) {
      result.push(`<p class="text-gray-700 mb-2">${formatted}</p>`);
    } else {
      result.push(''); // Empty line for spacing
    }
  }

  return result.join('\n');
}
