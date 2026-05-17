import React from "react";

interface MarkdownProps {
  text: string;
}

export default function Markdown({ text }: MarkdownProps) {
  if (!text) return null;

  // Split text by lines
  const lines = text.split("\n");
  const elements: React.ReactNode[] = [];

  let inList = false;
  let listItems: React.ReactNode[] = [];
  let listType: "ul" | "ol" = "ul";

  const flushList = (key: string | number) => {
    if (listItems.length > 0) {
      if (listType === "ul") {
        elements.push(
          <ul
            key={`ul-${key}`}
            style={{
              marginLeft: "1.5rem",
              marginBottom: "1rem",
              listStyleType: "disc",
            }}
          >
            {listItems}
          </ul>
        );
      } else {
        elements.push(
          <ol
            key={`ol-${key}`}
            style={{
              marginLeft: "1.5rem",
              marginBottom: "1rem",
              listStyleType: "decimal",
            }}
          >
            {listItems}
          </ol>
        );
      }
      listItems = [];
      inList = false;
    }
  };

  const parseInline = (lineText: string): React.ReactNode => {
    // Inline parser for bold (**text**), italic (*text*), and links ([text](url))
    let parts: (string | React.JSX.Element)[] = [lineText];

    // 1. Bold: **bold**
    parts = parts.flatMap((part) => {
      if (typeof part !== "string") return [part];
      const subParts = part.split(/\*\*([^*]+)\*\*/g);
      return subParts.map((sub, idx) =>
        idx % 2 === 1 ? <strong key={`b-${idx}`}>{sub}</strong> : sub
      );
    });

    // 2. Bold: __bold__
    parts = parts.flatMap((part) => {
      if (typeof part !== "string") return [part];
      const subParts = part.split(/__([^_]+)__/g);
      return subParts.map((sub, idx) =>
        idx % 2 === 1 ? <strong key={`b2-${idx}`}>{sub}</strong> : sub
      );
    });

    // 3. Italic: *italic*
    parts = parts.flatMap((part) => {
      if (typeof part !== "string") return [part];
      const subParts = part.split(/\*([^*]+)\*/g);
      return subParts.map((sub, idx) =>
        idx % 2 === 1 ? <em key={`i-${idx}`}>{sub}</em> : sub
      );
    });

    // 4. Italic: _italic_
    parts = parts.flatMap((part) => {
      if (typeof part !== "string") return [part];
      const subParts = part.split(/_([^_]+)_/g);
      return subParts.map((sub, idx) =>
        idx % 2 === 1 ? <em key={`i2-${idx}`}>{sub}</em> : sub
      );
    });

    // 5. Links: [link text](url)
    parts = parts.flatMap((part) => {
      if (typeof part !== "string") return [part];
      const linkRegex = /\[([^\]]+)\]\(([^)]+)\)/g;
      const subParts: (string | React.JSX.Element)[] = [];
      let lastIndex = 0;
      let match;

      while ((match = linkRegex.exec(part)) !== null) {
        const [_, text, url] = match;
        const index = match.index;
        if (index > lastIndex) {
          subParts.push(part.substring(lastIndex, index));
        }
        subParts.push(
          <a
            key={`link-${index}`}
            href={url}
            target="_blank"
            rel="noopener noreferrer"
            style={{
              color: "var(--accent)",
              textDecoration: "underline",
              fontWeight: "600",
            }}
          >
            {text}
          </a>
        );
        lastIndex = linkRegex.lastIndex;
      }
      if (lastIndex < part.length) {
        subParts.push(part.substring(lastIndex));
      }
      return subParts.length > 0 ? subParts : [part];
    });

    return <React.Fragment>{parts}</React.Fragment>;
  };

  lines.forEach((line, index) => {
    const trimmed = line.trim();

    if (!trimmed) {
      flushList(index);
      return;
    }

    // Headers
    if (trimmed.startsWith("### ")) {
      flushList(index);
      elements.push(
        <h5
          key={index}
          style={{
            fontSize: "1rem",
            fontWeight: "700",
            marginTop: "1rem",
            marginBottom: "0.5rem",
            color: "var(--text-primary)",
          }}
        >
          {parseInline(trimmed.slice(4))}
        </h5>
      );
    } else if (trimmed.startsWith("## ")) {
      flushList(index);
      elements.push(
        <h4
          key={index}
          style={{
            fontSize: "1.1rem",
            fontWeight: "700",
            marginTop: "1.2rem",
            marginBottom: "0.6rem",
            color: "var(--text-primary)",
          }}
        >
          {parseInline(trimmed.slice(3))}
        </h4>
      );
    } else if (trimmed.startsWith("# ")) {
      flushList(index);
      elements.push(
        <h3
          key={index}
          style={{
            fontSize: "1.25rem",
            fontWeight: "800",
            marginTop: "1.5rem",
            marginBottom: "0.75rem",
            color: "var(--text-primary)",
          }}
        >
          {parseInline(trimmed.slice(2))}
        </h3>
      );
    }
    // Unordered list
    else if (trimmed.startsWith("- ") || trimmed.startsWith("* ")) {
      if (!inList || listType !== "ul") {
        flushList(index);
        inList = true;
        listType = "ul";
      }
      listItems.push(
        <li
          key={`li-${index}`}
          style={{
            marginBottom: "0.25rem",
            color: "var(--text-secondary)",
            fontSize: "0.9rem",
            lineHeight: "1.6",
          }}
        >
          {parseInline(trimmed.slice(2))}
        </li>
      );
    }
    // Ordered list
    else if (/^\d+\.\s/.test(trimmed)) {
      if (!inList || listType !== "ol") {
        flushList(index);
        inList = true;
        listType = "ol";
      }
      const match = trimmed.match(/^\d+\.\s/);
      const prefixLength = match ? match[0].length : 3;
      listItems.push(
        <li
          key={`li-${index}`}
          style={{
            marginBottom: "0.25rem",
            color: "var(--text-secondary)",
            fontSize: "0.9rem",
            lineHeight: "1.6",
          }}
        >
          {parseInline(trimmed.slice(prefixLength))}
        </li>
      );
    }
    // Normal paragraph
    else {
      flushList(index);
      elements.push(
        <p
          key={index}
          className="sheet-direction-step"
          style={{ marginBottom: "0.75rem" }}
        >
          {parseInline(trimmed)}
        </p>
      );
    }
  });

  flushList("final");

  return <div className="markdown-content">{elements}</div>;
}
