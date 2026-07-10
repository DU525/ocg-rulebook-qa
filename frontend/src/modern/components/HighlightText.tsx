import React from 'react';
import { splitTextForHighlight } from '../utils/highlightUtils';

interface HighlightTextProps {
  text: string;
  query: string;
  highlightClass?: string;
}

export function HighlightText({
  text,
  query,
  highlightClass = 'bg-yellow-200 text-yellow-800 px-0.5 rounded',
}: HighlightTextProps) {
  const parts = splitTextForHighlight(text, query);

  return (
    <>
      {parts.map((part, index) =>
        part.isHighlight ? (
          <mark key={index} className={highlightClass}>
            {part.text}
          </mark>
        ) : (
          part.text
        )
      )}
    </>
  );
}
