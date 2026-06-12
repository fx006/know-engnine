export type SseEventKind =
  | "progress"
  | "answer_delta"
  | "reference"
  | "card"
  | "card_choice"
  | "warning"
  | "error"
  | "done";

export interface SseEvent<T = unknown> {
  kind: SseEventKind;
  payload: string;
  eventType?: string;
  data?: T;
  conversationId?: string;
}

export interface SseErrorPayload {
  code: string;
  message: string;
}

export function parseSseText(text: string): SseEvent[] {
  const events: SseEvent[] = [];
  let dataLines: string[] = [];

  for (const rawLine of text.split(/\r?\n/)) {
    if (rawLine === "") {
      if (dataLines.length > 0) {
        events.push(parseSsePayload(dataLines.join("\n")));
        dataLines = [];
      }
      continue;
    }

    if (rawLine.startsWith("data: ")) {
      dataLines.push(rawLine.slice("data: ".length));
    } else if (rawLine.startsWith("data:")) {
      dataLines.push(rawLine.slice("data:".length));
    }
  }

  if (dataLines.length > 0) {
    events.push(parseSsePayload(dataLines.join("\n")));
  }

  return events;
}

export function parseSsePayload(payload: string): SseEvent {
  if (payload.startsWith("[PROGRESS]:")) {
    return {
      kind: "progress",
      eventType: "PROGRESS",
      payload: payload.slice("[PROGRESS]:".length),
    };
  }

  if (payload.startsWith("[REFERENCE]:")) {
    const raw = payload.slice("[REFERENCE]:".length);
    return {
      kind: "reference",
      eventType: "REFERENCE",
      payload: raw,
      data: safeJsonParse(raw, []),
    };
  }

  if (payload.startsWith("[CARD]:")) {
    return {
      kind: "card",
      eventType: "CARD",
      payload: payload.slice("[CARD]:".length),
    };
  }

  if (payload.startsWith("[CARD_CHOICE_")) {
    const [prefix, raw] = splitPrefixedPayload(payload);
    return {
      kind: "card_choice",
      eventType: prefix,
      payload: raw,
      data: safeJsonParse(raw, []),
    };
  }

  if (payload.startsWith("[WARN]:")) {
    return {
      kind: "warning",
      eventType: "WARN",
      payload: payload.slice("[WARN]:".length),
    };
  }

  if (payload.startsWith("[ERROR]:")) {
    const raw = payload.slice("[ERROR]:".length);
    return {
      kind: "error",
      eventType: "ERROR",
      payload: raw,
      data: safeJsonParse(raw, { code: "UNKNOWN", message: raw }),
    };
  }

  if (payload.startsWith("[DONE]:")) {
    const conversationId = payload.slice("[DONE]:".length).trim();
    return {
      kind: "done",
      eventType: "DONE",
      payload: conversationId,
      conversationId,
    };
  }

  return {
    kind: "answer_delta",
    payload,
  };
}

export function extractSseFrames(buffer: string): {
  frames: string[];
  rest: string;
} {
  const frames: string[] = [];
  let rest = buffer;
  let separatorIndex = findFrameSeparator(rest);

  while (separatorIndex >= 0) {
    frames.push(rest.slice(0, separatorIndex));
    const separatorLength = rest.startsWith("\r\n\r\n", separatorIndex) ? 4 : 2;
    rest = rest.slice(separatorIndex + separatorLength);
    separatorIndex = findFrameSeparator(rest);
  }

  return { frames, rest };
}

function findFrameSeparator(text: string): number {
  const lf = text.indexOf("\n\n");
  const crlf = text.indexOf("\r\n\r\n");

  if (lf < 0) {
    return crlf;
  }
  if (crlf < 0) {
    return lf;
  }
  return Math.min(lf, crlf);
}

function splitPrefixedPayload(payload: string): [string, string] {
  const separatorIndex = payload.indexOf(":");
  if (separatorIndex < 0) {
    return [payload.replace(/^\[|\]$/g, ""), ""];
  }

  return [
    payload.slice(0, separatorIndex).replace(/^\[|\]$/g, ""),
    payload.slice(separatorIndex + 1),
  ];
}

function safeJsonParse<T>(raw: string, fallback: T): T {
  try {
    return JSON.parse(raw) as T;
  } catch {
    return fallback;
  }
}
